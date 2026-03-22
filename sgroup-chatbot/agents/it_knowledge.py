import asyncio

from agents.base import BaseAgent
from config.settings import settings
from services.brave_service import brave_search
from services.exa_service import exa_search
from services.youtube_service import youtube_search_recent


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
        exa_task = exa_search(message, num=6) if settings.exa_api_key else None
        brave_task = brave_search(message, count=6) if settings.brave_api_key else None
        youtube_task = youtube_search_recent(message, limit=10)

        pending = [t for t in [exa_task, brave_task, youtube_task] if t is not None]
        if not pending:
            return ""

        gathered = await asyncio.gather(*pending, return_exceptions=True)

        exa_items: list[dict] = []
        brave_items: list[dict] = []
        youtube_items: list[dict] = []

        index = 0
        if exa_task is not None:
            value = gathered[index]
            if isinstance(value, list):
                exa_items = value
            index += 1
        if brave_task is not None:
            value = gathered[index]
            if isinstance(value, list):
                brave_items = value
            index += 1

        value = gathered[index]
        if isinstance(value, list):
            youtube_items = value

        sections: list[str] = ["[KET QUA IT DA NGUON]"]

        if youtube_items:
            yt_lines = ["YouTube (5-10 video gan nhat):"]
            for i, item in enumerate(youtube_items[:10], 1):
                yt_lines.append(
                    f"{i}. {item.get('title', '')}\n"
                    f"   Kenh: {item.get('channel', '')} | {item.get('publishedAt', '')[:10]}\n"
                    f"   URL: {item.get('url', '')}"
                )
            sections.append("\n".join(yt_lines))

        if exa_items:
            exa_lines = ["Exa semantic search:"]
            for i, item in enumerate(exa_items[:6], 1):
                exa_lines.append(
                    f"{i}. {item.get('title', '')}\n"
                    f"   {item.get('text', '')[:220]}\n"
                    f"   URL: {item.get('url', '')}"
                )
            sections.append("\n".join(exa_lines))

        if brave_items:
            brave_lines = ["Brave web search:"]
            for i, item in enumerate(brave_items[:6], 1):
                brave_lines.append(
                    f"{i}. {item.get('title', '')}\n"
                    f"   {item.get('description', '')[:220]}\n"
                    f"   URL: {item.get('url', '')}"
                )
            sections.append("\n".join(brave_lines))

        if len(sections) == 1:
            return ""

        return "\n\n".join(sections)
