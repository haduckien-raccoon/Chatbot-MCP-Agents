from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from config.settings import settings


def _tokenize(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFD", text.lower())
    ascii_like = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    cleaned = (
        ascii_like
        .replace("?", " ")
        .replace("!", " ")
        .replace(",", " ")
        .replace(".", " ")
        .replace(":", " ")
        .replace(";", " ")
        .replace("(", " ")
        .replace(")", " ")
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
            lines.append(f"   Tóm tắt: {summary}")
        if content:
            lines.append(f"   Nội dung: {content}")
        if technical_doc:
            lines.append(f"   Tài liệu kỹ thuật liên quan: {technical_doc}")
            excerpt = _read_doc_excerpt(technical_doc)
            if excerpt:
                lines.append(f"   Trích đoạn tài liệu: {excerpt}")
        if source:
            lines.append(f"   Nguồn: {source}")

    return "\n".join(lines)


def get_sgroup_context(message: str) -> str:
    records = _read_json_file("sgroup.json")
    site_records = _read_json_file("sgroup-site.json")

    picked = _pick_top_records(records, message, limit=4)
    picked_sites = _pick_top_records(site_records, message, limit=2)

    lines = ["[DỮ LIỆU SGROUP CHÍNH THỨC]"]
    if picked:
        lines.append(_format_records(picked))

    if picked_sites:
        lines.append("\n[TRÍCH XUẤT TỪ WEBSITE SGROUP]")
        for i, item in enumerate(picked_sites, 1):
            lines.append(f"{i}. {item.get('title', '')}")
            lines.append(f"   URL: {item.get('url', '')}")
            snippet = str(item.get("content", ""))[:450]
            if snippet:
                lines.append(f"   Trích dẫn: {snippet}")

    return "\n".join(lines)


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", (text or "").lower())
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip()


def _get_verified_and_unverified_records() -> tuple[dict, dict]:
    records = _read_json_file("sgroup.json")
    verified = next(
        (
            r
            for r in records
            if str(r.get("sourceType", "")).lower() == "official"
            and "xac minh" in _normalize_text(str(r.get("title", "")))
        ),
        {},
    )
    unverified = next(
        (
            r
            for r in records
            if str(r.get("sourceType", "")).lower() == "unverified"
        ),
        {},
    )
    return verified, unverified


def _extract_current_chairperson(text: str) -> str | None:
    if not text:
        return None

    segment = text
    if "gồm:" in text:
        segment = text.split("gồm:", 1)[1]

    match = re.search(r"([A-ZĐ][A-Za-zÀ-ỹà-ỹ\s]+?)\s*\(Chủ nhiệm\)", segment)
    if match:
        return match.group(1).strip()
    return None


def _extract_role_name(text: str, role_label: str) -> str | None:
    if not text:
        return None

    segment = text
    if "gồm:" in text:
        segment = text.split("gồm:", 1)[1]

    pattern = rf"([A-ZĐ][A-Za-zÀ-ỹà-ỹ\s]+?)\s*\({re.escape(role_label)}\)"
    match = re.search(pattern, segment)
    if match:
        return match.group(1).strip()
    return None


def get_sgroup_answer(message: str) -> str:
    normalized_q = _normalize_text(message)
    verified, unverified = _get_verified_and_unverified_records()
    verified_content = str(verified.get("content", ""))
    verified_source = str(verified.get("sourceUrl", "")).strip()
    unverified_content = str(unverified.get("content", ""))

    source_about = "https://sgroupvn.org/ve-chung-toi"

    # 0) Sơ đồ tổ chức / các ban
    if any(k in normalized_q for k in ["so do to chuc", "ban van hanh", "ban truyen thong"]):
        lead = _extract_current_chairperson(verified_content)
        deputy = _extract_role_name(verified_content, "Phó chủ nhiệm")
        lead_prog = _extract_role_name(verified_content, "Trưởng chuyên môn lập trình")
        lead_mo = _extract_role_name(verified_content, "Trưởng chuyên môn Marketing Online")
        lead_design = _extract_role_name(verified_content, "Trưởng chuyên môn Thiết Kế")
        lead_media = _extract_role_name(verified_content, "Trưởng ban Truyền Thông")

        lines = ["Theo dữ liệu đã xác minh trên website S-Group:"]
        lines.append("- Sơ đồ tổ chức hiển thị 3 ban: Ban vận hành, Ban nội bộ, Ban truyền thông.")

        members: list[str] = []
        if lead:
            members.append(f"Chủ nhiệm: {lead}")
        if deputy:
            members.append(f"Phó chủ nhiệm: {deputy}")
        if lead_prog:
            members.append(f"Trưởng chuyên môn lập trình: {lead_prog}")
        if lead_mo:
            members.append(f"Trưởng chuyên môn Marketing Online: {lead_mo}")
        if lead_design:
            members.append(f"Trưởng chuyên môn Thiết Kế: {lead_design}")
        if lead_media:
            members.append(f"Trưởng ban Truyền Thông: {lead_media}")

        if members:
            lines.append("- Nhân sự hiển thị trên phần sơ đồ tổ chức:")
            lines.extend([f"  + {m}" for m in members])

        lines.append(
            "- Với Ban nội bộ/Ban truyền thông: trang hiển thị tab ban; danh sách chi tiết đầy đủ theo từng ban cần xem trực tiếp trên trang."
        )
        lines.append(f"Nguồn: {source_about}")
        return "\n".join(lines)

    # 0) Phó chủ nhiệm (check before 'chủ nhiệm' to avoid overlap)
    if any(k in normalized_q for k in ["pho chu nhiem", "pho chu nhiem"]):
        name = _extract_role_name(verified_content, "Phó chủ nhiệm")
        lines = ["Theo dữ liệu đã xác minh trên website S-Group:"]
        if name:
            lines.append(f"- Phó chủ nhiệm: {name}.")
        else:
            lines.append("- Chưa trích xuất được tên Phó chủ nhiệm từ dữ liệu xác minh.")
        lines.append(f"Nguồn: {source_about}")
        return "\n".join(lines)

    # 1) Chủ nhiệm
    if any(k in normalized_q for k in ["chu nhiem", "ban chu nhiem"]) and "pho chu nhiem" not in normalized_q:
        current_chair = _extract_current_chairperson(verified_content)
        lines = ["Theo dữ liệu đã xác minh trên website S-Group:"]
        if current_chair:
            lines.append(f"- Chủ nhiệm hiện được hiển thị: {current_chair}.")
        else:
            lines.append("- Chưa trích xuất được tên Chủ nhiệm từ dữ liệu xác minh hiện có.")

        if "dang quang nhat linh" in _normalize_text(unverified_content):
            lines.append(
                "- Thông tin 'Đặng Quang Nhật Linh' hiện đang ở trạng thái CHƯA XÁC MINH từ các URL đã cung cấp."
            )

        lines.append(f"Nguồn: {source_about}")
        return "\n".join(lines)

    # 1.1) Ban nội bộ
    if "ban noi bo" in normalized_q:
        lines = ["Theo dữ liệu đã xác minh trên website S-Group:"]
        lines.append("- Ban nội bộ gồm:")
        lines.append("  + Nguyễn Hồng Kiều Linh - Trưởng ban nội bộ")
        lines.append("  + Huỳnh Trọng Khoa - Thành viên")
        lines.append("  + Trần Đức Mạnh - Thành viên")
        lines.append("  + Cao Tuấn Kiệt - Thành viên")
        lines.append("  + Nguyễn Đức Truyền - Thành viên")
        lines.append("- Thông tin trên được trích từ phần tab 'Ban nội bộ' trong mục Sơ đồ tổ chức.")
        lines.append(f"Nguồn: {source_about}")
        return "\n".join(lines)

    # 1.2) Trưởng chuyên môn
    if any(k in normalized_q for k in ["chuyen mon lap trinh", "truong chuyen mon lap trinh"]):
        name = _extract_role_name(verified_content, "Trưởng chuyên môn lập trình")
        lines = ["Theo dữ liệu đã xác minh trên website S-Group:"]
        if name:
            lines.append(f"- Trưởng chuyên môn lập trình: {name}.")
        else:
            lines.append("- Chưa trích xuất được tên Trưởng chuyên môn lập trình từ dữ liệu xác minh.")
        lines.append(f"Nguồn: {source_about}")
        return "\n".join(lines)

    if any(k in normalized_q for k in ["chuyen mon marketing online", "truong chuyen mon mo"]):
        name = _extract_role_name(verified_content, "Trưởng chuyên môn Marketing Online")
        lines = ["Theo dữ liệu đã xác minh trên website S-Group:"]
        if name:
            lines.append(f"- Trưởng chuyên môn Marketing Online: {name}.")
        else:
            lines.append("- Chưa trích xuất được tên Trưởng chuyên môn Marketing Online từ dữ liệu xác minh.")
        lines.append(f"Nguồn: {source_about}")
        return "\n".join(lines)

    if any(k in normalized_q for k in ["chuyen mon thiet ke", "truong chuyen mon thiet ke"]):
        name = _extract_role_name(verified_content, "Trưởng chuyên môn Thiết Kế")
        lines = ["Theo dữ liệu đã xác minh trên website S-Group:"]
        if name:
            lines.append(f"- Trưởng chuyên môn Thiết Kế: {name}.")
        else:
            lines.append("- Chưa trích xuất được tên Trưởng chuyên môn Thiết Kế từ dữ liệu xác minh.")
        lines.append(f"Nguồn: {source_about}")
        return "\n".join(lines)

    if any(k in normalized_q for k in ["truong ban truyen thong", "ban truyen thong"]):
        name = _extract_role_name(verified_content, "Trưởng ban Truyền Thông")
        lines = ["Theo dữ liệu đã xác minh trên website S-Group:"]
        if not name:
            # Fallback from verified organization snapshot on ve-chung-toi.
            name = "Đỗ Thị Thu Uyên"
        if name:
            lines.append(f"- Trưởng ban Truyền Thông: {name}.")
        else:
            lines.append("- Chưa trích xuất được tên Trưởng ban Truyền Thông từ dữ liệu xác minh.")
        lines.append(f"Nguồn: {source_about}")
        return "\n".join(lines)

    # 2) 3S
    if "3s" in normalized_q:
        lines = ["Theo dữ liệu đã xác minh:"]
        lines.append("- Trang 'Về chúng tôi' có mục 3S và hiển thị rõ mục 'Share'.")
        lines.append(
            "- Chưa có xác minh trực tiếp cụm đầy đủ 'Social, Special, Share' trên các URL đã crawl."
        )
        lines.append(f"Nguồn: {source_about}")
        return "\n".join(lines)

    # 3) Fallback ngắn gọn, không dump dữ liệu
    overview = next(
        (r for r in _read_json_file("sgroup.json") if _normalize_text(str(r.get("title", ""))) == "sgroup overview"),
        {},
    )
    lines = ["Thông tin ngắn gọn về SGroup (dựa trên dữ liệu hiện có):"]
    summary = str(overview.get("summary", "")).strip()
    if summary:
        lines.append(f"- {summary}")
    lines.append("- Nếu bạn hỏi cụ thể (ví dụ: chủ nhiệm, 3S, trưởng chuyên môn), mình sẽ trả lời đúng trọng tâm 1-3 dòng.")
    lines.append(f"Nguồn: {source_about}")
    return "\n".join(lines)


def get_ai_team_context(message: str) -> str:
    records = _read_json_file("ai-team.json")
    picked = _pick_top_records(records, message, limit=5)
    if not picked:
        return ""
    return "[DỮ LIỆU AI TEAM]\n" + _format_records(picked)


def _extract_unverified_members(unverified_content: str) -> list[str]:
    if not unverified_content:
        return []
    match = re.search(
        r"Danh sách người dùng cung cấp:\s*(.*?)\s*\.\s*Không tìm thấy",
        unverified_content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []
    raw = match.group(1)
    names = [part.strip() for part in raw.split(",") if part.strip()]
    return names


def get_ai_team_answer(message: str) -> str:
    normalized_q = _normalize_text(message)
    records = _read_json_file("ai-team.json")
    if not records:
        return "[DỮ LIỆU AI TEAM]\nChưa có dữ liệu AI Team trong kho tri thức hiện tại."

    overview = next(
        (r for r in records if _normalize_text(str(r.get("title", ""))) == "ai team overview"),
        {},
    )
    official = next(
        (r for r in records if str(r.get("sourceType", "")).lower() == "official"),
        {},
    )
    unverified = next(
        (r for r in records if str(r.get("sourceType", "")).lower() == "unverified"),
        {},
    )

    project_records = [
        r
        for r in records
        if str(r.get("module", "")).strip().lower()
        in {
            "asr-translate-tts",
            "video-search",
            "recommendation-system",
            "video-summary",
            "chatbot",
            "knowledge-assistant",
        }
    ]

    module_alias_map = {
        "asr-translate-tts": ["asr", "tts", "translate", "giong noi", "xu ly tieng noi"],
        "video-search": ["video search", "clip", "index video", "tim kiem video"],
        "recommendation-system": ["recommend", "goi y", "neo4j", "youtube"],
        "video-summary": ["video summary", "tom tat video", "highlight", "blip", "qwen"],
        "chatbot": ["chatbot", "agent", "router"],
        "knowledge-assistant": ["knowledge", "tri thuc", "assistant", "noi bo"],
    }

    selected_module = ""
    for module, aliases in module_alias_map.items():
        if any(alias in normalized_q for alias in aliases):
            selected_module = module
            break

    if selected_module:
        rec = next(
            (
                r
                for r in project_records
                if str(r.get("module", "")).strip().lower() == selected_module
            ),
            {},
        )
        if rec:
            lines = ["Theo dữ liệu trong data/ai-team.json:"]
            lines.append(f"- {rec.get('title', 'Dự án AI Team')}.")
            summary = str(rec.get("summary", "")).strip()
            if summary:
                lines.append(f"- {summary}")
            tech_doc = str(rec.get("technical_doc", "")).strip()
            if tech_doc:
                lines.append(f"- Tài liệu kỹ thuật liên quan: {tech_doc}.")
            source = str(rec.get("sourceUrl", "")).strip()
            if source:
                lines.append(f"Nguồn: {source}")
            return "\n".join(lines)

    if any(k in normalized_q for k in ["thanh vien", "member", "nhan su", "co ai", "gom ai"]):
        lines = ["Theo dữ liệu trong data/ai-team.json:"]
        official_summary = str(official.get("summary", "")).strip()
        if official_summary:
            lines.append(f"- {official_summary}")

        unverified_names = _extract_unverified_members(str(unverified.get("content", "")))
        if unverified_names:
            lines.append("- Danh sách thành viên Team AI hiện có trong data (trạng thái: CHƯA XÁC MINH URL):")
            for name in unverified_names:
                lines.append(f"  + {name}")
        else:
            lines.append("- Chưa có danh sách thành viên đã xác minh từ URL chính thức.")

        source = str(official.get("sourceUrl", "")).strip() or "https://sgroupvn.org/ve-chung-toi"
        lines.append(f"Nguồn xác minh nhánh AI: {source}")
        return "\n".join(lines)

    if any(k in normalized_q for k in ["du an", "project", "san pham", "module", "lam gi"]):
        lines = ["Theo dữ liệu trong data/ai-team.json, AI Team đang có các hướng chính:"]
        for rec in project_records[:6]:
            title = str(rec.get("title", "")).strip()
            summary = str(rec.get("summary", "")).strip()
            if title:
                if summary:
                    lines.append(f"- {title}: {summary}")
                else:
                    lines.append(f"- {title}")
        lines.append("Nếu bạn muốn, mình có thể đi sâu 1 dự án cụ thể (ASR/TTS, video search, recommendation, video summary, chatbot).")
        return "\n".join(lines)

    lines = ["Theo dữ liệu trong data/ai-team.json:"]
    overview_summary = str(overview.get("summary", "")).strip()
    if overview_summary:
        lines.append(f"- {overview_summary}")
    lines.append("- Các mảng chính: chatbot đa-agent, knowledge assistant, ASR-Translate-TTS, video search/indexing, recommendation system, video summary.")

    official_summary = str(official.get("summary", "")).strip()
    if official_summary:
        lines.append(f"- Xác minh từ website: {official_summary}")

    source = str(official.get("sourceUrl", "")).strip() or "https://sgroupvn.org/ve-chung-toi"
    lines.append(f"Nguồn: {source}")
    return "\n".join(lines)


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

    return f"[DỮ LIỆU MODULE {module_key.upper()}]\n" + _format_records(picked)
