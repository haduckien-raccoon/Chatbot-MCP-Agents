from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from config.settings import settings


def _tokenize(text: str) -> set[str]:
    cleaned = (
        text.lower()
        .replace("?", " ")
        .replace("!", " ")
        .replace(",", " ")
        .replace(".", " ")
        .replace("\n", " ")
    )
    return {t.strip() for t in cleaned.split() if t.strip()}


@lru_cache(maxsize=1)
def _resolve_data_dir() -> Path:
    # Resolve DATA_DIR relative to project root (where config lives).
    project_root = Path(__file__).resolve().parents[1]
    configured = Path(settings.data_dir)
    if configured.is_absolute():
        return configured
    return (project_root / configured).resolve()


def _read_json_file(file_name: str) -> list[dict]:
    path = _resolve_data_dir() / file_name
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        return []
    except Exception:
        return []


def _read_doc_excerpt(doc_name: str, max_chars: int = 420) -> str:
    if not doc_name:
        return ""
    path = _resolve_data_dir() / "docs" / doc_name
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
        compact = " ".join(text.replace("\n", " ").split())
        return compact[:max_chars]
    except Exception:
        return ""


def _score_record(message_tokens: set[str], record: dict) -> int:
    title_tokens = _tokenize(str(record.get("title", "")))
    summary_tokens = _tokenize(str(record.get("summary", "")))
    keyword_tokens: set[str] = set()
    for kw in record.get("keywords", []) or []:
        keyword_tokens.update(_tokenize(str(kw)))

    score = 0
    score += len(message_tokens.intersection(keyword_tokens)) * 3
    score += len(message_tokens.intersection(title_tokens)) * 2
    score += len(message_tokens.intersection(summary_tokens))
    return score


def _pick_top_records(records: list[dict], message: str, limit: int = 4) -> list[dict]:
    if not records:
        return []

    message_tokens = _tokenize(message)
    ranked = [(_score_record(message_tokens, r), r) for r in records]
    ranked.sort(key=lambda x: x[0], reverse=True)

    top = [record for score, record in ranked if score > 0][:limit]
    if top:
        return top
    return records[:limit]


def _format_records(records: list[dict]) -> str:
    lines: list[str] = []
    for idx, rec in enumerate(records, 1):
        title = rec.get("title", "")
        summary = rec.get("summary", "")
        content = rec.get("content", "")
        source = rec.get("sourceUrl", "")
        technical_doc = rec.get("technical_doc", "")

        lines.append(f"{idx}. {title}")
        if summary:
            lines.append(f"   Tom tat: {summary}")
        if content:
            lines.append(f"   Noi dung: {content}")
        if technical_doc:
            lines.append(f"   Tai lieu ky thuat lien quan: {technical_doc}")
            excerpt = _read_doc_excerpt(technical_doc)
            if excerpt:
                lines.append(f"   Trich doan tai lieu: {excerpt}")
        if source:
            lines.append(f"   Nguon: {source}")

    return "\n".join(lines)


def get_sgroup_context(message: str) -> str:
    records = _read_json_file("sgroup.json")
    site_records = _read_json_file("sgroup-site.json")

    picked = _pick_top_records(records, message, limit=4)
    picked_sites = _pick_top_records(site_records, message, limit=2)

    lines = ["[DU LIEU SGROUP CHINH THUC]"]
    if picked:
        lines.append(_format_records(picked))

    if picked_sites:
        lines.append("\n[TRICH XUAT TU WEBSITE SGROUP]")
        for i, item in enumerate(picked_sites, 1):
            lines.append(f"{i}. {item.get('title', '')}")
            lines.append(f"   URL: {item.get('url', '')}")
            snippet = str(item.get("content", ""))[:450]
            if snippet:
                lines.append(f"   Trich dan: {snippet}")

    return "\n".join(lines)


def get_ai_team_context(message: str) -> str:
    records = _read_json_file("ai-team.json")
    picked = _pick_top_records(records, message, limit=5)
    if not picked:
        return ""
    return "[DU LIEU AI TEAM]\n" + _format_records(picked)


def get_module_context(module_key: str, message: str) -> str:
    records = _read_json_file("ai-team.json")
    if not records:
        return ""

    module_alias = {
        "module_a": "chatbot",
        "module_b": "knowledge-assistant",
    }
    target = module_alias.get(module_key, module_key)

    filtered = [
        r for r in records if str(r.get("module", "")).strip().lower() == target.lower()
    ]
    if not filtered:
        filtered = records

    picked = _pick_top_records(filtered, message, limit=3)
    if not picked:
        return ""

    return f"[DU LIEU MODULE {module_key.upper()}]\n" + _format_records(picked)
