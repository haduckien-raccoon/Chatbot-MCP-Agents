from agents.base import BaseAgent
from services.knowledge_service import get_module_context


class ModuleBAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return """
Ban la chuyen gia ve Module B cua SGroup (hien map voi knowledge-assistant trong data).

Hay tra loi dua tren DU LIEU MODULE B duoc cung cap trong context.
Neu thieu du lieu, noi ro pham vi thay vi doan them.
Uu tien trinh bay: tong quan -> tinh nang -> cach dung va luu y.
"""

    async def fetch_data(self, message: str) -> str:
        return get_module_context("module_b", message)
