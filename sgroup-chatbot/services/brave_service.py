import httpx

from config.settings import settings


async def brave_search(query: str, count: int = 5) -> list[dict]:
    """Brave Search API."""
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": settings.brave_api_key,
    }
    params = {"q": query, "count": count, "lang": "vi"}

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        return response.json().get("web", {}).get("results", [])
