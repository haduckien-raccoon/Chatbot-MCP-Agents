from abc import ABC, abstractmethod

from services.gemini_service import GeminiService


class BaseAgent(ABC):
    """Base class for all agents using Gemini as LLM."""

    def __init__(self):
        self.llm = GeminiService()

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        raise NotImplementedError

    async def fetch_data(self, message: str) -> str:
        """Override in agents that need external APIs."""
        _ = message
        return ""

    async def handle(
        self,
        message: str,
        history: list[dict],
        external_data: str = "",
    ) -> str:
        """Merge external data into context and call LLM."""
        context = (
            f"{external_data}\n\nCau hoi nguoi dung: {message}"
            if external_data
            else message
        )

        language_instruction = (
            "\n\nYÊU CẦU ĐẦU RA BẮT BUỘC:\n"
            "- Luôn trả lời bằng tiếng Việt có dấu, rõ ràng, tự nhiên.\n"
            "- Không dùng tiếng Việt không dấu trừ khi người dùng yêu cầu riêng."
        )

        return await self.llm.chat(
            system=self.system_prompt + language_instruction,
            message=context,
            history=history,
        )
