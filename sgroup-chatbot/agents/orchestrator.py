import json
import re
import unicodedata

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

    def _normalize(self, text: str) -> str:
        lowered = (text or "").lower().strip()
        normalized = unicodedata.normalize("NFD", lowered)
        stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return re.sub(r"\s+", " ", stripped)

    def _fast_route(self, normalized_message: str) -> str | None:
        # Fast path for identity/capability/general chatbot questions.
        if re.search(
            r"\b(ban la ai|ban la gi|ai day|ai vay|gioi thieu ban than|chatbot|tro ly ao|ban lam duoc gi|chuc nang|tinh nang)\b",
            normalized_message,
            re.IGNORECASE,
        ):
            return "general"

        # Rule-based fast path for common weather intents to reduce routing misses.
        if re.search(
            r"\b(thoi tiet|nhiet do|weather|temperature|mua|nang|rain|sunny)\b",
            normalized_message,
            re.IGNORECASE,
        ):
            return "weather"

        # AI Team specific intents should be routed before generic SGroup intents.
        if re.search(
            r"\b(ai team|team ai|doi ai|nhom ai|du an ai|thanh vien ai|members ai|ai sgroup|sgroup ai)\b",
            normalized_message,
            re.IGNORECASE,
        ):
            return "ai_team"

        # Route SGroup organization/role intents before IT to avoid collisions with words like 'lap trinh'.
        if re.search(
            r"\b(sgroup|s-group|chu nhiem|pho chu nhiem|ban van hanh|ban noi bo|ban truyen thong|truong chuyen mon|ve chung toi|tuyen thanh vien|so do to chuc)\b",
            normalized_message,
            re.IGNORECASE,
        ):
            return "sgroup_knowledge"

        # Rule-based fast path for news/article search queries.
        if re.search(
            r"\b(tin tuc|bai bao|thoi su|su kien|the thao|bong da|ban tin|news|headline|tin moi)\b",
            normalized_message,
            re.IGNORECASE,
        ):
            return "news"

        # Rule-based fast path for programming/IT help.
        if re.search(
            r"\b(it|lap trinh|code|bug|loi|python|java|javascript|react|docker|kubernetes|api|database|devops|llm|ai ml|machine learning|tri tue nhan tao)\b",
            normalized_message,
            re.IGNORECASE,
        ):
            return "it_knowledge"

        return None

    def _split_clauses(self, message: str) -> list[str]:
        if not message:
            return []

        parts = re.split(
            r"\s*(?:[;,]|\bva\b|\bvà\b|\broi\b|\brồi\b|\bsau do\b|\bsau đó\b|\band\b|\bthen\b)\s*",
            message,
            flags=re.IGNORECASE,
        )
        clauses = [p.strip() for p in parts if p and p.strip()]
        return clauses if len(clauses) > 1 else [message.strip()]

    def _is_internal_sgroup_query(self, normalized_message: str) -> bool:
        return bool(
            re.search(
                r"\b(sgroup|s-group|chu nhiem|pho chu nhiem|ban van hanh|ban noi bo|ban truyen thong|truong chuyen mon|ve chung toi|tuyen thanh vien|so do to chuc)\b",
                normalized_message,
                re.IGNORECASE,
            )
        )

    def _collect_fast_intents(self, normalized_message: str) -> list[str]:
        intents: list[str] = []

        if re.search(
            r"\b(ban la ai|ban la gi|ai day|ai vay|gioi thieu ban than|chatbot|tro ly ao|ban lam duoc gi|chuc nang|tinh nang)\b",
            normalized_message,
            re.IGNORECASE,
        ):
            intents.append("general")

        if re.search(
            r"\b(thoi tiet|nhiet do|weather|temperature|mua|nang|rain|sunny)\b",
            normalized_message,
            re.IGNORECASE,
        ):
            intents.append("weather")

        if re.search(
            r"\b(ai team|team ai|doi ai|nhom ai|du an ai|thanh vien ai|members ai|ai sgroup|sgroup ai)\b",
            normalized_message,
            re.IGNORECASE,
        ):
            intents.append("ai_team")

        if re.search(
            r"\b(sgroup|s-group|chu nhiem|pho chu nhiem|ban van hanh|ban noi bo|ban truyen thong|truong chuyen mon|ve chung toi|tuyen thanh vien|so do to chuc)\b",
            normalized_message,
            re.IGNORECASE,
        ):
            intents.append("sgroup_knowledge")

        if re.search(
            r"\b(tin tuc|bai bao|thoi su|su kien|the thao|bong da|ban tin|news|headline|tin moi)\b",
            normalized_message,
            re.IGNORECASE,
        ):
            intents.append("news")

        if re.search(
            r"\b(it|lap trinh|code|bug|loi|python|java|javascript|react|docker|kubernetes|api|database|devops|llm|ai ml|machine learning|tri tue nhan tao)\b",
            normalized_message,
            re.IGNORECASE,
        ):
            intents.append("it_knowledge")

        # Guardrail: internal SGroup questions often contain words like 'lap trinh',
        # but they should stay in sgroup_knowledge to avoid irrelevant IT search results.
        if self._is_internal_sgroup_query(normalized_message):
            intents = [x for x in intents if x != "it_knowledge"]

        if len(intents) > 1 and "general" in intents:
            intents = [x for x in intents if x != "general"]

        return intents

    async def route(self, message: str) -> str:
        normalized_message = self._normalize(message)
        fast_agent = self._fast_route(normalized_message)
        if fast_agent:
            return fast_agent

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

    async def plan_routes(self, message: str) -> tuple[list[str], dict[str, str]]:
        clauses = self._split_clauses(message)

        if len(clauses) == 1:
            normalized_message = self._normalize(message)
            all_intents = self._collect_fast_intents(normalized_message)
            if len(all_intents) > 1:
                return all_intents, {agent: message for agent in all_intents}

        selected_agents: list[str] = []
        agent_queries: dict[str, str] = {}

        for clause in clauses:
            normalized_clause = self._normalize(clause)
            agent = self._fast_route(normalized_clause)
            if not agent:
                agent = await self.route(clause)

            if agent not in selected_agents:
                selected_agents.append(agent)
                agent_queries[agent] = clause
            else:
                # Keep context for repeated intents inside a long multi-part message.
                agent_queries[agent] = f"{agent_queries[agent]}; {clause}"

        if not selected_agents:
            fallback = await self.route(message)
            return [fallback], {fallback: message}

        if len(selected_agents) > 1 and "general" in selected_agents:
            selected_agents = [a for a in selected_agents if a != "general"]
            agent_queries.pop("general", None)

        if not selected_agents:
            fallback = await self.route(message)
            return [fallback], {fallback: message}

        return selected_agents, agent_queries
