from agents.base import BaseAgent
from services.knowledge_service import get_ai_team_answer


class AITeamAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return """
Ban la dai dien AI Team cua SGroup.

Hay tra loi dua tren DU LIEU AI TEAM duoc cung cap trong context.

Quy tac bat buoc:
1. Uu tien thong tin trong data (overview, modules, technical docs).
2. Tom tat co cau truc: tong quan -> du an lien quan -> cong nghe/chuc nang.
3. Neu cau hoi vuot qua du lieu hien co, noi ro pham vi va de xuat lien he team.

Giu giong dieu tich cuc, tu tin, ro rang.
"""

    async def fetch_data(self, message: str) -> str:
        return get_ai_team_answer(message)

    async def handle(
        self,
        message: str,
        history: list[dict],
        external_data: str = "",
    ) -> str:
        # Deterministic output to avoid noisy LLM rewrites for AI Team factual responses.
        _ = (message, history)
        if external_data:
            return external_data
        return "[DỮ LIỆU AI TEAM]\nChưa có dữ liệu AI Team phù hợp trong kho tri thức hiện tại."
