import asyncio

import feedparser
import httpx

from config.settings import settings

_BASE = "https://newsapi.org/v2"
_RSS_FEEDS = [
    "https://vnexpress.net/rss/tin-moi-nhat.rss",
    "https://tuoitre.vn/rss/tin-moi-nhat.rss",
]


async def search_newsapi(query: str) -> list[dict]:
    if not settings.news_api_key:
        return []

    params = {
        "q": query,
        "language": "vi",
        "sortBy": "publishedAt",
        "pageSize": 5,
        "apiKey": settings.news_api_key,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{_BASE}/everything", params=params)
        response.raise_for_status()
        return response.json().get("articles", [])


async def get_rss_news() -> list[dict]:
    """Fallback when NewsAPI key is missing or request fails."""
    articles: list[dict] = []
    for url in _RSS_FEEDS:
        try:
            feed = await asyncio.to_thread(feedparser.parse, url)
            for entry in feed.entries[:3]:
                articles.append(
                    {
                        "title": entry.get("title", ""),
                        "description": entry.get("summary", ""),
                        "source": {"name": feed.feed.get("title", url)},
                        "publishedAt": entry.get("published", ""),
                        "url": entry.get("link", ""),
                    }
                )
        except Exception:
            pass

    return articles[:5]


async def get_news(query: str) -> list[dict]:
    articles = await search_newsapi(query)
    if not articles:
        articles = await get_rss_news()
    return articles
