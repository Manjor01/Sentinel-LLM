from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import time

from src.detector.pipeline import SentinelPipeline

app = FastAPI(
    title="sentinel-llm",
    description="Behavioral prompt injection detector for LLM applications",
    version="1.0.0"
)

pipeline = SentinelPipeline()


class AnalyzeRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None


class AnalyzeResponse(BaseModel):
    is_anomaly: bool
    risk_score: float
    triggered_rules: list
    features: dict
    prompt: str
    response: str
    timestamp: float


@app.on_event("startup")
async def startup():
    if not pipeline.check_ollama():
        raise RuntimeError("Ollama is not running. Start Ollama first.")


@app.get("/")
def root():
    return {
        "service": "sentinel-llm",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
def health():
    ollama_ok = pipeline.check_ollama()
    return {
        "status": "healthy" if ollama_ok else "degraded",
        "ollama": "connected" if ollama_ok else "disconnected"
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    try:
        result = pipeline.process(request.prompt)
        return AnalyzeResponse(
            is_anomaly=result.is_anomaly,
            risk_score=result.risk_score,
            triggered_rules=result.triggered_rules,
            features=result.features,
            prompt=result.prompt,
            response=result.response,
            timestamp=result.timestamp
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
def stats():
    history = pipeline.analyzer.history
    total = len(history)
    return {
        "total_requests": total,
        "baseline_response_length": pipeline.analyzer.baseline_response_length
    }