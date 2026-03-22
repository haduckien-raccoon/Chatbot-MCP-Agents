import re

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
            return (
                "[DU LIEU THOI TIET THUC TE]\n"
                f"Dia diem: {data['name']}, {data['sys']['country']}\n"
                f"Nhiet do: {data['main']['temp']} do C (cam giac {data['main']['feels_like']} do C)\n"
                f"Trang thai: {data['weather'][0]['description']}\n"
                f"Do am: {data['main']['humidity']}%\n"
                f"Toc do gio: {data['wind']['speed']} m/s"
            )
        except Exception as exc:
            return f"[Khong lay duoc du lieu thoi tiet: {exc}]"

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
