import httpx
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


class OllamaClient:
    """
    Клиент для работы с Ollama.
    Отправляем промпт — получаем ответ модели.
    """

    def __init__(self):
        self.base_url = OLLAMA_BASE_URL
        self.model = OLLAMA_MODEL

    def chat(self, prompt: str, system: str = None) -> str:
        """
        Отправляем запрос к Ollama и получаем ответ.
        
        prompt — вопрос пользователя
        system — системный промпт (роль модели)
        """
        messages = []

        if system:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data["message"]["content"]

        except httpx.TimeoutException:
            raise RuntimeError("Ollama не отвечает — превышен таймаут")
        except httpx.ConnectError:
            raise RuntimeError(
                f"Не могу подключиться к Ollama по адресу {self.base_url}. "
                "Убедись что Ollama запущена."
            )
        except Exception as e:
            raise RuntimeError(f"Ошибка при запросе к Ollama: {e}")

    def is_available(self) -> bool:
        """Проверяем что Ollama запущена и доступна."""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False