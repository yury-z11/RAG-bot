# llm_client.py
import requests
import time
import json

from config import config

class LLMClient:
    def __init__(self, model: str = "llama3"):
        self.model = model
        self.api_url = "http://localhost:11434/api/generate"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Вызов локальной модели через Ollama"""

        full_prompt = f"{system_prompt.strip()}\n\n{prompt.strip()}"

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False
        }

        try:
            start_time = time.time()
            response = requests.post(self.api_url, json=payload, timeout=900)
            duration = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Ответ получен от LLM за {duration:.2f} сек")
                return result.get("response", "").strip()
            else:
                print(f"❌ Ошибка LLM: {response.status_code}")
                return f"Ошибка LLM: {response.status_code}"

        except Exception as e:
            return f"⚠️ Ошибка вызова LLM: {e}"
