import os
import time

import httpx
import ollama


class LLMClient:
    def __init__(self, model="qwen2.5:3b"):
        self.model = os.getenv("OLLAMA_MODEL", model)
        self.max_retries = int(os.getenv("OLLAMA_MAX_RETRIES", "2"))
        self.client = ollama.Client(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            timeout=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "300")),
        )

        self.system_prompt = """
You are an expert food-science information extraction system.
Extract only statements explicitly supported by the supplied research-paper
evidence. Never use general knowledge. Return valid JSON matching the supplied
schema. Use null for missing scalar values and [] when no record is supported.
""".strip()

    def generate(
        self,
        prompt: str,
        json_schema: dict | None = None,
        max_output_tokens: int = 512,
    ) -> str:
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    format=json_schema or "json",
                    options={
                        "temperature": 0,
                        "num_ctx": int(os.getenv("OLLAMA_NUM_CTX", "4096")),
                        "num_predict": max_output_tokens,
                    },
                    keep_alive=os.getenv("OLLAMA_KEEP_ALIVE", "10m"),
                )
                return response["message"]["content"]
            except httpx.ReadTimeout as exc:
                # Retrying the same large prompt wastes another full timeout.
                # The table extractor will retry with fewer evidence chunks.
                raise TimeoutError(
                    f"Ollama timed out after {os.getenv('OLLAMA_TIMEOUT_SECONDS', '300')} seconds"
                ) from exc
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 4))

        raise RuntimeError(
            f"Ollama generation failed after {self.max_retries + 1} attempts"
        ) from last_error
