import re
import unicodedata

from agents.base import BaseAgent
from config.settings import settings
from services.weather_service import get_weather


class WeatherAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return """
Ban la tro ly thoi tiet cua SGroup. Du lieu thuc te da duoc cung cap.

Trinh bay ro rang:
- Nhiet do: X do C (cam giac nhu Y do C)
- Trang thai: [mo ta]
- Do am: X%
- Gio: X m/s
- Goi y: [mang o/ao am/kem chong nang...]

Neu khong xac dinh duoc dia diem, hoi lai nguoi dung.
"""

    async def fetch_data(self, message: str) -> str:
        location = self._extract_location(message) or settings.weather_default_city
        try:
            data = await get_weather(location)
            reference_link = self._build_forecast_link(location, data)
            suggestion = self._build_suggestion(
                temp=float(data["main"]["temp"]),
                humidity=int(data["main"]["humidity"]),
                weather_desc=str(data["weather"][0]["description"]),
            )
            return (
                "[DU LIEU THOI TIET THUC TE]\n"
                f"Dia diem: {data['name']}, {data['sys']['country']}\n"
                f"Nhiet do: {data['main']['temp']} do C (cam giac {data['main']['feels_like']} do C)\n"
                f"Trang thai: {data['weather'][0]['description']}\n"
                f"Do am: {data['main']['humidity']}%\n"
                f"Toc do gio: {data['wind']['speed']} m/s\n"
                f"Goi y: {suggestion}\n"
                f"Xem du bao chi tiet: {reference_link}"
            )
        except Exception as exc:
            return f"[Khong lay duoc du lieu thoi tiet: {exc}]"

    async def handle(
        self,
        message: str,
        history: list[dict],
        external_data: str = "",
    ) -> str:
        # Return deterministic weather answer to avoid LLM changing trusted links.
        _ = (message, history)
        if external_data:
            return external_data
        return "[Khong lay duoc du lieu thoi tiet]"

    def _build_forecast_link(self, raw_location: str, weather_data: dict) -> str:
        city = str(weather_data.get("name") or raw_location or "").strip()
        normalized = self._normalize_text(city)

        if normalized in {"da nang", "danang", }:
            return (
                "https://www.accuweather.com/en/vn/da-nang/352954/"
                "weather-forecast/352954#google_vignette"
            )

        safe_city = city.replace(" ", "-").lower()
        return f"https://www.accuweather.com/vi/search-locations?query={safe_city}"

    def _normalize_text(self, text: str) -> str:
        normalized = unicodedata.normalize("NFD", text.lower())
        stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return stripped.replace("-", " ").strip()

    def _build_suggestion(self, temp: float, humidity: int, weather_desc: str) -> str:
        normalized_desc = self._normalize_text(weather_desc)
        if "mua" in normalized_desc:
            return "Nen mang o hoac ao mua khi ra ngoai."
        if temp >= 33:
            return "Troi kha nong, nen uong du nuoc va han che ra duong buoi trua."
        if humidity >= 85:
            return "Do am cao, nen mac do thoang va giu co the kho rao."
        return "Thoi tiet tuong doi de chiu, ban co the di chuyen binh thuong."

    def _extract_location(self, msg: str) -> str | None:
        patterns = [
            r"thời tiết (?:ở |tại )?(.+?)(?:\?|$| hôm nay| ngày mai)",
            r"nhiệt độ (?:ở |tại )?(.+?)(?:\?|$| hôm nay| ngày mai)",
            r"(?:ở|tại) (.+?) (?:hôm nay|ngày mai|nhiệt độ|thời tiết)",
            r"thoi tiet (?:o |tai )?(.+?)(?:\?|$| hom nay| ngay mai)",
            r"(?:o|tai) (.+?) (?:hom nay|ngay mai|nhiet do|thoi tiet)",
            r"weather (?:in |at )?(.+?)(?:\?|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, msg, re.IGNORECASE)
            if match:
                location = match.group(1).strip(" .,!?:;\"'")
                if location:
                    return location

        # Fallback: if user sends a short phrase, treat it as location (e.g. "Da Nang").
        cleaned = msg.strip(" .,!?:;\"'")
        words = cleaned.split()
        if 1 <= len(words) <= 4:
            return cleaned
        return None
