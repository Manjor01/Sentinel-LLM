import httpx
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_alert(result) -> bool:
    """
    Отправляет алерт в Telegram при обнаружении атаки.
    Возвращает True если успешно, False если нет.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    # Формируем красивое сообщение
    rules_text = "\n".join([f"  - {r}" for r in result.triggered_rules])

    message = (
        f"SENTINEL-LLM ALERT\n"
        f"{'='*30}\n"
        f"Status: ANOMALY DETECTED\n"
        f"Risk Score: {result.risk_score}\n\n"
        f"Prompt:\n{result.prompt[:200]}\n\n"
        f"Response:\n{result.response[:200]}\n\n"
        f"Triggered Rules:\n{rules_text}\n\n"
        f"Features:\n"
        f"  - injection_patterns: {result.features['injection_patterns_count']}\n"
        f"  - compromised_patterns: {result.features['compromised_patterns_count']}\n"
        f"  - length_deviation: {result.features['length_deviation']}\n"
        f"  - response_entropy: {result.features['response_entropy']}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            })
            return response.status_code == 200
    except Exception:
        return False