import asyncio
from urllib.parse import quote_plus

import feedparser


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
        return []

    items: list[dict] = []
    for entry in feed.entries[: max(5, min(limit, 10))]:
        author = entry.get("author", "")
        published = entry.get("published", "")
        items.append(
            {
                "title": entry.get("title", ""),
                "description": entry.get("summary", ""),
                "channel": author,
                "publishedAt": published,
                "url": entry.get("link", ""),
            }
        )
    return items
