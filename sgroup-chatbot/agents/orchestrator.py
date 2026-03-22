import json
import re

from services.gemini_service import GeminiService

_SYSTEM = """
Ban la agent dieu huong cua SGroup chatbot. Phan tich cau hoi va chon agent phu hop.

Agents co san:
- "general"           -> Cau hoi chung, gioi thieu chatbot, ban la ai
- "ai_team"           -> AI Team SGroup, cac du an AI
- "weather"           -> Thoi tiet, nhiet do, du bao thoi tiet
- "news"              -> Tin tuc, thoi su, su kien moi nhat
- "it_knowledge"      -> Lap trinh, cong nghe, IT, code
- "sgroup_knowledge"  -> Thong tin noi bo SGroup, cong ty, quy trinh
- "module_a"          -> Module A cua SGroup
- "module_b"          -> Module B cua SGroup

Chi tra ve JSON, khong giai thich:
{"agent": "<ten>", "confidence": <0.0-1.0>, "reason": "<ngan gon>"}
"""

_ALLOWED_AGENTS = {
    "general",
    "ai_team",
    "weather",
    "news",
    "it_knowledge",
    "sgroup_knowledge",
    "module_a",
    "module_b",
}


class Orchestrator:
    def __init__(self):
        self.llm = GeminiService()

    async def route(self, message: str) -> str:
        # Rule-based fast path for common weather intents to reduce routing misses.
        if re.search(
            r"\b(thời tiết|thoi tiet|nhiệt độ|nhiet do|weather|temperature|mưa|nắng|rain|sunny)\b",
            message,
            re.IGNORECASE,
        ):
            return "weather"

        raw = await self.llm.chat(system=_SYSTEM, message=message, history=[])
        try:
            clean = raw.strip()
            if "```" in clean:
                parts = clean.split("```")
                if len(parts) > 1:
                    clean = parts[1]
                    if clean.startswith("json"):
                        clean = clean[4:]
            agent = json.loads(clean.strip()).get("agent", "general")
            return agent if agent in _ALLOWED_AGENTS else "general"
        except Exception:
            return "general"
