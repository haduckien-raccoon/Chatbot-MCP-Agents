from __future__ import annotations

import json
import logging
import re
from collections import defaultdict

from config.settings import settings
from services.gemini_service import GeminiService

try:
    from redis import Redis
except Exception:  # pragma: no cover - import failure handled at runtime
    Redis = None


_sessions: dict[str, list[dict]] = defaultdict(list)
_long_memory_cache: dict[str, dict] = {}
_redis_client = None
_memory_llm = GeminiService()
_redis_fallback_active = False
_logger = logging.getLogger(__name__)

MAX_SHORT_TURNS = 20
MAX_PREFS = 8
MAX_TOPICS = 10


def _redis_key(session_id: str) -> str:
    return f"{settings.redis_memory_prefix}:{session_id}"


def _mark_redis_fallback(reason: str) -> None:
    global _redis_fallback_active
    if _redis_fallback_active:
        return
    _redis_fallback_active = True
    _logger.warning("Redis long-memory fallback to in-memory cache: %s", reason)


def _mark_redis_recovered() -> None:
    global _redis_fallback_active
    if not _redis_fallback_active:
        return
    _redis_fallback_active = False
    _logger.info("Redis long-memory connection recovered")


def _get_redis_client():
    global _redis_client

    if not settings.redis_memory_enabled:
        _mark_redis_fallback("REDIS_MEMORY_ENABLED=false")
        return None

    if Redis is None:
        _mark_redis_fallback("redis package is not installed")
        return None

    if _redis_client is None:
        try:
            _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
            _redis_client.ping()
            _mark_redis_recovered()
        except Exception:
            _mark_redis_fallback(f"cannot connect to {settings.redis_url}")
            _redis_client = None

    return _redis_client


def _load_long_memory_from_redis(session_id: str) -> dict:
    client = _get_redis_client()
    if not client:
        return {}

    try:
        raw = client.get(_redis_key(session_id))
        if not raw:
            return {}
        payload = json.loads(raw)
        _mark_redis_recovered()
        return payload if isinstance(payload, dict) else {}
    except Exception:
        _mark_redis_fallback("read failure while loading long-memory")
        global _redis_client
        _redis_client = None
        return {}


def _save_long_memory_to_redis(session_id: str, memory: dict) -> None:
    client = _get_redis_client()
    if not client:
        return

    try:
        serialized = json.dumps(memory, ensure_ascii=False)
        ttl_seconds = max(0, settings.redis_memory_ttl_seconds)
        if ttl_seconds > 0:
            client.setex(_redis_key(session_id), ttl_seconds, serialized)
        else:
            client.set(_redis_key(session_id), serialized)
        _mark_redis_recovered()
    except Exception:
        _mark_redis_fallback("write failure while saving long-memory")
        global _redis_client
        _redis_client = None
        return


def _delete_long_memory_from_redis(session_id: str) -> None:
    client = _get_redis_client()
    if not client:
        return

    try:
        client.delete(_redis_key(session_id))
        _mark_redis_recovered()
    except Exception:
        _mark_redis_fallback("delete failure while clearing long-memory")
        global _redis_client
        _redis_client = None
        return


def _ensure_long_memory_shape(session_id: str) -> dict:
    current = _long_memory_cache.get(session_id)
    if current is None:
        current = _load_long_memory_from_redis(session_id)

    profile = current.get("profile") if isinstance(current.get("profile"), dict) else {}
    preferences = current.get("preferences") if isinstance(current.get("preferences"), list) else []
    topics = current.get("topics") if isinstance(current.get("topics"), list) else []
    summary = current.get("memory_summary") if isinstance(current.get("memory_summary"), str) else ""

    shaped = {
        "profile": profile,
        "preferences": preferences[:MAX_PREFS],
        "topics": topics[:MAX_TOPICS],
        "memory_summary": summary.strip(),
    }
    _long_memory_cache[session_id] = shaped
    return shaped


def _append_unique(items: list[str], value: str, max_items: int) -> list[str]:
    clean = re.sub(r"\s+", " ", (value or "").strip())
    if not clean:
        return items

    lowered = clean.lower()
    seen = {x.lower() for x in items if isinstance(x, str)}
    if lowered in seen:
        return items

    items.append(clean)
    return items[-max_items:]


def _extract_first_json_object(text: str) -> dict:
    if not text:
        return {}

    candidate = text.strip()
    if "```" in candidate:
        parts = candidate.split("```")
        if len(parts) >= 2:
            candidate = parts[1]
            if candidate.lstrip().startswith("json"):
                candidate = candidate.lstrip()[4:]

    match = re.search(r"\{[\s\S]*\}", candidate)
    if match:
        candidate = match.group(0)

    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _merge_long_memory(current: dict, candidate: dict) -> dict:
    merged = {
        "profile": dict(current.get("profile") or {}),
        "preferences": list(current.get("preferences") or []),
        "topics": list(current.get("topics") or []),
        "memory_summary": str(current.get("memory_summary") or "").strip(),
    }

    profile = candidate.get("profile") if isinstance(candidate.get("profile"), dict) else {}
    for key in ("name", "location"):
        value = str(profile.get(key) or "").strip()
        if value:
            merged["profile"][key] = value

    for value in candidate.get("preferences") or []:
        if isinstance(value, str):
            merged["preferences"] = _append_unique(merged["preferences"], value, MAX_PREFS)

    for value in candidate.get("topics") or []:
        if isinstance(value, str):
            merged["topics"] = _append_unique(merged["topics"], value, MAX_TOPICS)

    summary = str(candidate.get("memory_summary") or "").strip()
    if summary:
        merged["memory_summary"] = summary

    merged["preferences"] = merged["preferences"][:MAX_PREFS]
    merged["topics"] = merged["topics"][:MAX_TOPICS]
    return merged


async def _update_long_memory_with_llm(session_id: str, user_msg: str, bot_msg: str) -> None:
    current = _ensure_long_memory_shape(session_id)

    system_prompt = (
        "Ban la bo nho dai han cho chatbot. "
        "Nhiem vu: cap nhat long-memory tu hoi thoai moi nhat. "
        "Chi tra ve JSON hop le, KHONG them giai thich."
    )
    message = (
        "Long memory hien tai:\n"
        f"{json.dumps(current, ensure_ascii=False)}\n\n"
        "Luot hoi thoai moi:\n"
        f"- user: {user_msg}\n"
        f"- assistant: {bot_msg}\n\n"
        "Tra ve JSON dung schema:\n"
        "{\n"
        '  "profile": {"name": "", "location": ""},\n'
        '  "preferences": ["..."],\n'
        '  "topics": ["..."],\n'
        '  "memory_summary": "Tom tat ngan gon bang tieng Viet co dau"\n'
        "}\n"
        "Quy tac:\n"
        "- Chi luu thong tin ben vung, khong luu thong tin tam thoi.\n"
        "- Khong bịa, neu khong chac chan thi de trong.\n"
        f"- preferences toi da {MAX_PREFS} muc, topics toi da {MAX_TOPICS} muc."
    )

    candidate: dict = {}
    try:
        raw = await _memory_llm.chat(system=system_prompt, message=message, history=[])
        candidate = _extract_first_json_object(raw)
    except Exception:
        candidate = {}

    if not candidate:
        return

    merged = _merge_long_memory(current, candidate)
    _long_memory_cache[session_id] = merged
    _save_long_memory_to_redis(session_id, merged)


def get_short_memory(session_id: str) -> list[dict]:
    return _sessions[session_id][-MAX_SHORT_TURNS * 2 :]


def get_long_memory(session_id: str) -> dict:
    return _ensure_long_memory_shape(session_id)


def upsert_long_memory(session_id: str, payload: dict) -> dict:
    current = _ensure_long_memory_shape(session_id)
    candidate = payload if isinstance(payload, dict) else {}
    merged = _merge_long_memory(current, candidate)
    _long_memory_cache[session_id] = merged
    _save_long_memory_to_redis(session_id, merged)
    return merged


def clear_long_memory(session_id: str) -> None:
    _long_memory_cache.pop(session_id, None)
    _delete_long_memory_from_redis(session_id)


def get_memory_debug_info(session_id: str) -> dict:
    long_memory = get_long_memory(session_id)
    return {
        "session_id": session_id,
        "redis_enabled": bool(settings.redis_memory_enabled),
        "redis_connected": _get_redis_client() is not None,
        "redis_fallback_active": _redis_fallback_active,
        "long_memory": long_memory,
        "long_memory_context": get_long_memory_context(session_id),
    }


def get_long_memory_context(session_id: str) -> str:
    memory = _ensure_long_memory_shape(session_id)
    profile = memory.get("profile", {})
    preferences = memory.get("preferences", [])
    topics = memory.get("topics", [])

    lines: list[str] = []
    if profile.get("name"):
        lines.append(f"- Ten nguoi dung: {profile['name']}")
    if profile.get("location"):
        lines.append(f"- Vi tri thuong dung: {profile['location']}")
    if preferences:
        lines.append("- So thich/muc tieu da nho: " + "; ".join(preferences[:MAX_PREFS]))
    if topics:
        lines.append("- Chu de hay quan tam: " + ", ".join(topics[:MAX_TOPICS]))
    if memory.get("memory_summary"):
        lines.append(f"- Tom tat dai han: {memory['memory_summary']}")

    if not lines:
        return ""

    return "[LONG MEMORY]\n" + "\n".join(lines)


def get_history(session_id: str) -> list[dict]:
    short_memory = get_short_memory(session_id)
    long_memory_context = get_long_memory_context(session_id)
    if not long_memory_context:
        return short_memory

    return [{"role": "assistant", "content": long_memory_context}, *short_memory]


def save_turn(session_id: str, user_msg: str, bot_msg: str) -> None:
    _sessions[session_id].append({"role": "user", "content": user_msg})
    _sessions[session_id].append({"role": "assistant", "content": bot_msg})


async def save_turn_with_long_memory(session_id: str, user_msg: str, bot_msg: str) -> None:
    save_turn(session_id, user_msg, bot_msg)
    await _update_long_memory_with_llm(session_id, user_msg, bot_msg)


def clear_history(session_id: str) -> None:
    _sessions[session_id] = []
    clear_long_memory(session_id)
