from agents.base import BaseAgent
from services.knowledge_service import get_sgroup_answer


class SGroupKnowledgeAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return """
Ban la dai dien thong tin chinh thuc cua SGroup.

Quy tac bat buoc:
1. Uu tien su dung DU LIEU SGROUP CHINH THUC da duoc cung cap trong context.
2. Neu thong tin khong co trong context, noi ro la chua co du lieu xac thuc.
3. Khong tu bo sung thong tin noi bo khong co nguon.
4. Khi phu hop, dua link chinh thuc:
   - https://sgroupvn.org/
   - https://www.facebook.com/sgroupvn.org

Phong cach: than thien, ro rang, chinh xac, ngan gon.
"""

    async def fetch_data(self, message: str) -> str:
        return get_sgroup_answer(message)

    async def handle(
        self,
        message: str,
        history: list[dict],
        external_data: str = "",
    ) -> str:
        # Deterministic grounded output: avoid LLM rewriting into fabricated content.
        _ = (message, history)
        if external_data:
            return external_data
        return (
            "[DỮ LIỆU SGROUP CHÍNH THỨC]\n"
            "Chưa có dữ liệu xác thực cho câu hỏi này trong bộ tri thức hiện tại.\n"
            "Nguồn tham khảo: https://sgroupvn.org/"
        )
