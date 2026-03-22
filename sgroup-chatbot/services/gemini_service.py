import httpx

from config.settings import settings


class GeminiService:
    """Compatibility wrapper now backed by Groq with model fallback."""

    def __init__(self):
        self.api_key = settings.groq_api_key
        self.base_url = settings.groq_base_url.rstrip("/")
        self.temperature = 0.5
        self.max_output_tokens = 1024
        self.timeout_s = max(2, settings.llm_timeout_ms // 1000)

        configured_models = [m.strip() for m in settings.groq_models.split(",") if m.strip()]
        self.models = configured_models or [
            "allam-2-7b",
            "groq/compound",
            "groq/compound-mini",
            "llama-3.1-8b-instant",
            "llama-3.3-70b-versatile",
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "meta-llama/llama-prompt-guard-2-22m",
            "meta-llama/llama-prompt-guard-2-86m",
            "moonshotai/kimi-k2-instruct",
            "moonshotai/kimi-k2-instruct-0905",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "openai/gpt-oss-safeguard-20b",
            "qwen/qwen3-32b",
        ]

    async def chat(
        self,
        system: str,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is missing")

        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})

        for item in history or []:
            role = "assistant" if item.get("role") == "assistant" else "user"
            messages.append({"role": role, "content": item.get("content", "")})

        messages.append({"role": "user", "content": message})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            for model_name in self.models:
                payload = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_output_tokens,
                }

                try:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    choices = data.get("choices") or []
                    if not choices:
                        raise RuntimeError("Empty choices from Groq")

                    content = (choices[0].get("message") or {}).get("content", "")
                    if content and content.strip():
                        return content.strip()
                    raise RuntimeError(f"Model '{model_name}' returned empty content")
                except Exception as exc:
                    last_error = exc
                    continue

        raise RuntimeError(f"All Groq models failed: {last_error}")
