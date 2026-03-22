import httpx

from config.settings import settings


async def exa_search(query: str, num: int = 5) -> list[dict]:
    """Exa neural search for semantic retrieval."""
    headers = {
        "x-api-key": settings.exa_api_key,
        "Content-Type": "application/json",
    }
    body = {
        "query": query,
        "numResults": num,
        "useAutoprompt": True,
        "type": "neural",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post("https://api.exa.ai/search", json=body, headers=headers)
        response.raise_for_status()
        return response.json().get("results", [])
