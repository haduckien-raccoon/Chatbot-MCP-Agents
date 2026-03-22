from datetime import date, timedelta
from urllib.parse import quote
import unicodedata

import httpx

from config.settings import settings

_BASE = (
    "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
)


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


def _build_timeline_url(location: str, start_date: date | None, end_date: date | None) -> str:
    safe_location = quote(location.strip(), safe="")
    if start_date and end_date:
        return f"{_BASE}/{safe_location}/{start_date.isoformat()}/{end_date.isoformat()}"
    return f"{_BASE}/{safe_location}"


async def get_weather(location: str) -> dict:
    """Return timeline payload containing current/day/hour weather data for a location."""
    return await get_weather_range(location=location, start_offset_days=0, end_offset_days=0)


async def get_weather_range(
    location: str,
    start_offset_days: int = 0,
    end_offset_days: int = 0,
) -> dict:
    candidates = _location_candidates(location)
    if not candidates:
        raise ValueError("location is empty")

    today = date.today()
    start_date = today + timedelta(days=start_offset_days)
    end_date = today + timedelta(days=end_offset_days)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    params = {
        "unitGroup": "us",
        "include": "days,hours,current",
        "key": settings.visualcrossing_api_key,
        "contentType": "json",
    }

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=12) as client:
        for query in candidates:
            try:
                url = _build_timeline_url(query, start_date, end_date)
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code in {400, 404}:
                    continue
                raise

    raise RuntimeError(f"Khong tim thay du lieu thoi tiet cho '{location}'") from last_error


async def get_weather_dates(
    location: str,
    start_date: date,
    end_date: date,
) -> dict:
    candidates = _location_candidates(location)
    if not candidates:
        raise ValueError("location is empty")

    query_start = start_date
    query_end = end_date
    if query_start > query_end:
        query_start, query_end = query_end, query_start

    params = {
        "unitGroup": "us",
        "include": "days,hours,current",
        "key": settings.visualcrossing_api_key,
        "contentType": "json",
    }

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=12) as client:
        for query in candidates:
            try:
                url = _build_timeline_url(query, query_start, query_end)
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code in {400, 404}:
                    continue
                raise

    raise RuntimeError(f"Khong tim thay du lieu thoi tiet cho '{location}'") from last_error
