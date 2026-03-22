from agents.base import BaseAgent
from config.settings import settings
from services.brave_service import brave_search
from services.exa_service import exa_search


class ITKnowledgeAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return """
Ban la chuyen gia IT cua SGroup.

Linh vuc: Python, FastAPI, LangChain, LangGraph, React, Docker,
Kubernetes, CI/CD, AWS/GCP, AI/ML, LLM, Database, Microservices, DevOps.

Khi co ket qua tim kiem:
1. Tong hop tu nguon uy tin
2. Giai thich ro, kem vi du code neu can
3. Neu best practices va luu y
4. Dan nguon tham khao

Tra loi chuyen nghiep nhung de hieu.
"""

    async def fetch_data(self, message: str) -> str:
        results: list[str] = []

        if settings.exa_api_key:
            try:
                items = await exa_search(message)
                for item in items:
                    results.append(
                        f"- {item.get('title', '')}\n"
                        f"  {item.get('text', '')[:200]}\n"
                        f"  URL: {item.get('url', '')}"
                    )
            except Exception:
                pass

        if not results and settings.brave_api_key:
            try:
                items = await brave_search(message)
                for item in items:
                    results.append(
                        f"- {item.get('title', '')}\n"
                        f"  {item.get('description', '')[:200]}\n"
                        f"  URL: {item.get('url', '')}"
                    )
            except Exception:
                pass

        if not results:
            return ""
        return "[KET QUA TIM KIEM]\n" + "\n\n".join(results)
