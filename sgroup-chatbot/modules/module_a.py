from agents.base import BaseAgent
from services.knowledge_service import get_module_context


class ModuleAAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return """
Ban la chuyen gia ve Module A cua SGroup (hien map voi module chatbot trong data).

Hay tra loi dua tren DU LIEU MODULE A duoc cung cap trong context.
Neu thieu du lieu, noi ro pham vi thay vi doan them.
Uu tien trinh bay: tong quan -> tinh nang -> huong dan su dung.
"""

    async def fetch_data(self, message: str) -> str:
        return get_module_context("module_a", message)
