import asyncio
import html
import re
from urllib.parse import quote_plus
from urllib.parse import parse_qs, urlparse

import feedparser
import httpx


def _extract_video_id(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        if parsed.netloc.endswith("youtu.be"):
            return parsed.path.strip("/")
        if "youtube.com" in parsed.netloc:
            query = parse_qs(parsed.query)
            if "v" in query and query["v"]:
                return query["v"][0]
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in {"shorts", "embed"}:
                return parts[1]
    except Exception:
        return ""
    return ""


def _build_embed_item(video_id: str, *, title: str = "", channel: str = "", published: str = "") -> dict:
    clean_id = (video_id or "").strip()
    if not clean_id:
        return {}
    return {
        "title": (title or "").strip() or f"YouTube video {clean_id}",
        "description": "",
        "channel": (channel or "").strip(),
        "publishedAt": (published or "").strip(),
        "url": f"https://www.youtube.com/watch?v={clean_id}",
        "video_id": clean_id,
        "embed_url": f"https://www.youtube.com/embed/{clean_id}",
        "thumbnail": f"https://i.ytimg.com/vi/{clean_id}/hqdefault.jpg",
    }


async def _youtube_search_via_web_request(query: str, *, limit: int) -> list[dict]:
    search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
    }

    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            response = await client.get(search_url, headers=headers)
            response.raise_for_status()
            page = response.text
    except Exception:
        return []

    # Fast path: collect watch links from search page HTML.
    ids: list[str] = []
    seen_ids: set[str] = set()
    for match in re.finditer(r"/watch\?v=([A-Za-z0-9_-]{11})", page):
        vid = match.group(1)
        if vid in seen_ids:
            continue
        seen_ids.add(vid)
        ids.append(vid)
        if len(ids) >= max(5, min(limit, 10)):
            break

    if not ids:
        return []

    # Optional title extraction from inline JSON fragments.
    titles = re.findall(r'"title"\s*:\s*\{\s*"runs"\s*:\s*\[\s*\{\s*"text"\s*:\s*"(.*?)"', page)

    items: list[dict] = []
    target_count = max(5, min(limit, 10))
    for idx, vid in enumerate(ids[:target_count]):
        title = ""
        if idx < len(titles):
            title = html.unescape(titles[idx]).replace("\\u0026", "&")
        item = _build_embed_item(vid, title=title, channel="YouTube")
        if item:
            items.append(item)
    return items


async def youtube_search_recent(query: str, *, limit: int = 8) -> list[dict]:
    """Search recent YouTube videos by query using public RSS feed."""
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return []

    url = (
        "https://www.youtube.com/feeds/videos.xml?search_query="
        f"{quote_plus(cleaned_query)}"
    )

    try:
        feed = await asyncio.to_thread(feedparser.parse, url)
    except Exception:
        feed = None

    items: list[dict] = []
    seen: set[str] = set()
    for entry in (feed.entries if feed else [])[: max(5, min(limit, 10))]:
        author = entry.get("author", "")
        published = entry.get("published", "")
        entry_url = entry.get("link", "")
        video_id = _extract_video_id(entry_url)
        dedupe_key = video_id or entry_url
        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        items.append(
            {
                "title": entry.get("title", ""),
                "description": entry.get("summary", ""),
                "channel": author,
                "publishedAt": published,
                "url": entry_url,
                "video_id": video_id,
                "embed_url": f"https://www.youtube.com/embed/{video_id}" if video_id else "",
                "thumbnail": (
                    f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else ""
                ),
            }
        )

    # Fallback: direct request to YouTube search page and parse videos from HTML.
    if len(items) < 5:
        web_items = await _youtube_search_via_web_request(cleaned_query, limit=limit)
        for item in web_items:
            key = item.get("video_id") or item.get("url")
            if not key or key in seen:
                continue
            seen.add(key)
            items.append(item)
            if len(items) >= max(5, min(limit, 10)):
                break

    return items[: max(5, min(limit, 10))]
