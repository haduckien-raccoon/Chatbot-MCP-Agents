import asyncio
import html
import re
from urllib.parse import parse_qs, urlparse

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
        brave_youtube_task = (
            brave_search(self._build_youtube_site_query(message), count=12)
            if settings.brave_api_key
            else None
        )
        youtube_queries = self._build_youtube_queries(message)
        youtube_tasks = [youtube_search_recent(query, limit=10) for query in youtube_queries]

        pending = [
            t
            for t in [exa_task, brave_task, brave_youtube_task, *youtube_tasks]
            if t is not None
        ]
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

        brave_youtube_items: list[dict] = []
        if brave_youtube_task is not None:
            value = gathered[index]
            if isinstance(value, list):
                brave_youtube_items = value
            index += 1

        youtube_batches: list[list[dict]] = []
        for value in gathered[index:]:
            if isinstance(value, list):
                youtube_batches.append(value)

        for batch in youtube_batches:
            youtube_items.extend(batch)

        if brave_youtube_items:
            youtube_items.extend(self._convert_brave_to_youtube_items(brave_youtube_items))

        youtube_items = self._dedupe_by_url(youtube_items)[:10]
        exa_items = self._dedupe_by_url(exa_items)[:6]
        brave_items = self._dedupe_by_url(brave_items)[:6]

        sections: list[str] = ["[KET QUA IT DA NGUON]"]

        if youtube_items:
            top_n = min(10, len(youtube_items))
            yt_lines = [f"YouTube Top {top_n} (IT / Lap trinh):"]
            for i, item in enumerate(youtube_items[:top_n], 1):
                title = self._clean_text(item.get("title", ""))
                if not title or self._looks_noisy(title):
                    continue

                channel = self._clean_text(item.get("channel", ""))
                date_str = str(item.get("publishedAt", ""))[:10]
                url = self._clean_text(item.get("url", ""))
                yt_lines.append(
                    f"{i}. {title}\n"
                    f"   Kenh: {channel} | {date_str}\n"
                    f"   URL: {url}"
                )
                embed_url = item.get("embed_url", "")
                if embed_url:
                    yt_lines.append(f"   EMBED: {embed_url}")
            if len(yt_lines) > 1:
                sections.append("\n".join(yt_lines))
            else:
                sections.append("YouTube: Chua loc duoc ket qua hop le tu RSS.")
        else:
            sections.append("YouTube: Chua tim thay ket qua phu hop voi tu khoa hien tai.")

        if exa_items:
            exa_lines = ["Exa semantic search:"]
            counter = 0
            for item in exa_items[:6]:
                title = self._clean_text(item.get("title", ""))
                snippet = self._clean_text(item.get("text", ""))[:220]
                url = self._clean_text(item.get("url", ""))
                if not title or self._looks_noisy(title):
                    continue
                if snippet and self._looks_noisy(snippet):
                    continue
                counter += 1
                exa_lines.append(
                    f"{counter}. {title}\n"
                    f"   {snippet}\n"
                    f"   URL: {url}"
                )
            if len(exa_lines) > 1:
                sections.append("\n".join(exa_lines))

        if brave_items:
            brave_lines = ["Brave web search:"]
            counter = 0
            for item in brave_items[:6]:
                title = self._clean_text(item.get("title", ""))
                snippet = self._clean_text(item.get("description", ""))[:220]
                url = self._clean_text(item.get("url", ""))
                if not title or self._looks_noisy(title):
                    continue
                if snippet and self._looks_noisy(snippet):
                    continue
                counter += 1
                brave_lines.append(
                    f"{counter}. {title}\n"
                    f"   {snippet}\n"
                    f"   URL: {url}"
                )
            if len(brave_lines) > 1:
                sections.append("\n".join(brave_lines))

        if len(sections) == 1:
            return ""

        return "\n\n".join(sections)

    def _build_youtube_queries(self, message: str) -> list[str]:
        query = self._clean_text(message)
        if not query:
            return ["lap trinh python co ban", "python tutorial vietnamese"]

        candidates = [
            f"{query} lap trinh IT",
            query,
            f"{query} tutorial",
            f"{query} huong dan",
        ]

        lowered = query.lower()
        if "python" in lowered:
            candidates.append("python co ban cho nguoi moi")

        if any(k in lowered for k in ["an toan thong tin", "attt", "bao mat", "cyber", "security"]):
            candidates.extend(
                [
                    f"{query} cyber security",
                    "an toan thong tin co ban",
                    "network security tutorial",
                ]
            )

        seen: set[str] = set()
        ordered: list[str] = []
        for item in candidates:
            key = item.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(item.strip())
        return ordered[:4]

    def _build_youtube_site_query(self, message: str) -> str:
        query = self._clean_text(message)
        if not query:
            query = "lap trinh"
        return f"site:youtube.com (watch OR shorts) {query} tutorial"

    def _extract_video_id(self, url: str) -> str:
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            if host.endswith("youtu.be"):
                return parsed.path.strip("/")
            if "youtube.com" in host:
                query = parse_qs(parsed.query)
                if "v" in query and query["v"]:
                    return query["v"][0]
                parts = [p for p in parsed.path.split("/") if p]
                if len(parts) >= 2 and parts[0] in {"shorts", "embed"}:
                    return parts[1]
        except Exception:
            return ""
        return ""

    def _convert_brave_to_youtube_items(self, brave_items: list[dict]) -> list[dict]:
        converted: list[dict] = []
        for item in brave_items or []:
            if not isinstance(item, dict):
                continue
            url = self._clean_text(item.get("url", ""))
            video_id = self._extract_video_id(url)
            if not video_id:
                continue

            converted.append(
                {
                    "title": self._clean_text(item.get("title", "")),
                    "description": self._clean_text(item.get("description", "")),
                    "channel": "YouTube",
                    "publishedAt": "",
                    "url": url,
                    "video_id": video_id,
                    "embed_url": f"https://www.youtube.com/embed/{video_id}",
                }
            )
        return converted

    async def handle(
        self,
        message: str,
        history: list[dict],
        external_data: str = "",
    ) -> str:
        # Deterministic output to avoid LLM repeating/garbling IT search results.
        _ = (message, history)
        if external_data:
            return external_data
        return (
            "[KET QUA IT DA NGUON]\n"
            "Khong lay duoc ket qua phu hop luc nay. Ban hay thu lai voi tu khoa cu the hon, "
            "vi du: 'python co ban', 'fastapi tutorial', 'langgraph agent'."
        )

    def _clean_text(self, value: str) -> str:
        text = html.unescape(str(value or "")).strip()
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.replace("�", " ").strip()

    def _looks_noisy(self, value: str) -> bool:
        text = self._clean_text(value).lower()
        if not text:
            return True

        tokens = text.split()
        if not tokens:
            return True

        run = 1
        for i in range(1, len(tokens)):
            if tokens[i] == tokens[i - 1]:
                run += 1
                if run >= 5:
                    return True
            else:
                run = 1

        if len(tokens) >= 24:
            unique_ratio = len(set(tokens)) / max(1, len(tokens))
            if unique_ratio < 0.3:
                return True

        return False

    def _dedupe_by_url(self, items: list[dict]) -> list[dict]:
        seen: set[str] = set()
        result: list[dict] = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            key = str(item.get("url") or item.get("title") or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result
