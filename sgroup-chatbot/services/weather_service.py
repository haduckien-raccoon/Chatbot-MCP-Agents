import httpx
import unicodedata

from config.settings import settings

_BASE = "https://api.openweathermap.org/data/2.5"


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _location_candidates(location: str) -> list[str]:
    base = (location or "").strip()
    if not base:
        return []

    ascii_base = _strip_accents(base)
    candidates = [base, ascii_base]

    if "," not in base:
        candidates.append(f"{base},VN")
    if ascii_base and "," not in ascii_base:
        candidates.append(f"{ascii_base},VN")

    seen: set[str] = set()
    result: list[str] = []
    for item in candidates:
        clean = item.strip()
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            result.append(clean)
    return result


async def get_weather(location: str) -> dict:
    candidates = _location_candidates(location)
    if not candidates:
        raise ValueError("location is empty")

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=10) as client:
        for query in candidates:
            params = {
                "q": query,
                "appid": settings.openweather_api_key,
                "units": "metric",
                "lang": "vi",
            }
            try:
                response = await client.get(f"{_BASE}/weather", params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                # Keep trying alternative query forms for not-found cases.
                if exc.response.status_code in {400, 404}:
                    continue
                raise

    raise RuntimeError(f"Khong tim thay du lieu thoi tiet cho '{location}'") from last_error


async def get_forecast(location: str) -> dict:
    params = {
        "q": location,
        "appid": settings.openweather_api_key,
        "units": "metric",
        "lang": "vi",
        "cnt": 24,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{_BASE}/forecast", params=params)
        response.raise_for_status()
        return response.json()
