import asyncio

from google import genai

from config.settings import settings


class GeminiService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.google_api_key)
        self.model_name = settings.google_model
        self.temperature = 0.7
        self.max_output_tokens = 1024
        self.timeout_s = max(1, settings.google_timeout_ms // 1000)

    async def chat(
        self,
        system: str,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        """
        Call Gemini with system prompt + chat history.
        Input history format: [{"role": "user"|"assistant", "content": "..."}]
        """
        gemini_history = []
        for item in history or []:
            role = "model" if item.get("role") == "assistant" else "user"
            gemini_history.append(
                {
                    "role": role,
                    "parts": [{"text": item.get("content", "")}],
                }
            )

        response = await asyncio.wait_for(
            asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=gemini_history
                + [{"role": "user", "parts": [{"text": message}]}],
                config={
                    "system_instruction": system,
                    "temperature": self.temperature,
                    "max_output_tokens": self.max_output_tokens,
                },
            ),
            timeout=self.timeout_s,
        )

        text = getattr(response, "text", "")
        if text:
            return text.strip()

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                part_text = getattr(part, "text", "")
                if part_text:
                    return part_text.strip()

        return ""
