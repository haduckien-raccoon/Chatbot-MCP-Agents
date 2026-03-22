import asyncio
from datetime import date, datetime, timedelta
import re
import unicodedata
from urllib.parse import quote

from agents.base import BaseAgent
from config.settings import settings
from services.weather_service import get_weather_dates, get_weather_range


class WeatherAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return """
Ban la tro ly thoi tiet cua SGroup. Du lieu thuc te da duoc cung cap.

Quy tac xu ly:
- Ho tro cau hoi cho nhieu dia diem trong cung mot tin nhan (vi du: Da Nang | Ha Noi | Ho Chi Minh).
- Ho tro hien tai/hom nay, tuong lai (ngay mai, sau X ngay) va qua khu (hom qua, truoc X ngay).
- Neu cau hoi mo ho ve dia diem hoac moc thoi gian, hoi lai ngan gon.

Trinh bay ro rang:
- Nhiet do: X do C (cam giac nhu Y do C)
- Trang thai: [mo ta]
- Do am: X%
- Gio: X m/s
- Goi y: [mang o/ao am/kem chong nang...]

Neu khong xac dinh duoc dia diem, hoi lai nguoi dung.
"""

    async def fetch_data(self, message: str) -> str:
        locations = self._extract_locations(message)
        if not locations:
            locations = [settings.weather_default_city]

        # Keep first-seen order while removing duplicates.
        locations = list(dict.fromkeys(locations))[:8]

        explicit_dates = self._extract_specific_dates(message)
        offsets: list[int] = []

        if explicit_dates:
            start_date, end_date = min(explicit_dates), max(explicit_dates)
            tasks = [
                get_weather_dates(
                    location=location,
                    start_date=start_date,
                    end_date=end_date,
                )
                for location in locations
            ]
        else:
            offsets = self._extract_day_offsets(message)
            start_offset, end_offset = min(offsets), max(offsets)
            tasks = [
                get_weather_range(
                    location=location,
                    start_offset_days=start_offset,
                    end_offset_days=end_offset,
                )
                for location in locations
            ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        blocks: list[str] = ["[DỰ BÁO THỜI TIẾT - VISUAL CROSSING]"]
        for location, result in zip(locations, results):
            if isinstance(result, BaseException):
                blocks.append(
                    "\n".join(
                        [
                            f"Địa điểm: {location}",
                            "Trạng thái: Không lấy được dữ liệu.",
                            f"Chi tiết lỗi: {result}",
                        ]
                    )
                )
                continue
            if not isinstance(result, dict):
                blocks.append(
                    "\n".join(
                        [
                            f"Địa điểm: {location}",
                            "Trạng thái: Dữ liệu không hợp lệ từ nhà cung cấp.",
                        ]
                    )
                )
                continue
            blocks.append(
                self._format_location_weather(
                    location,
                    result,
                    offsets=offsets,
                    explicit_dates=explicit_dates,
                )
            )

        blocks.append(
            "Nguồn dữ liệu: https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
        )
        return "\n\n".join(blocks)

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

    def _format_location_weather(
        self,
        requested_location: str,
        data: dict,
        offsets: list[int],
        explicit_dates: list[date] | None = None,
    ) -> str:
        resolved = str(data.get("resolvedAddress") or requested_location)
        days = data.get("days") or []
        days_by_date = {str(d.get("datetime")): d for d in days if isinstance(d, dict)}

        lines = [f"Địa điểm: {resolved}"]
        today = date.today()
        current = data.get("currentConditions") or {}

        target_dates = sorted(set(explicit_dates or []))[:6]
        if not target_dates:
            target_dates = [today + timedelta(days=offset) for offset in offsets[:6]]

        for target_date in target_dates:
            target_key = target_date.isoformat()
            day_data = days_by_date.get(target_key)

            if explicit_dates:
                label = f"Ngày {target_date.strftime('%d/%m/%Y')}"
            else:
                offset = (target_date - today).days
                label = self._label_for_offset(offset)

            is_today = target_date == today
            if is_today and current:
                temp_c = self._f_to_c(current.get("temp"))
                feels_c = self._f_to_c(current.get("feelslike"))
                humidity = current.get("humidity")
                wind_ms = self._mph_to_ms(current.get("windspeed"))
                condition = current.get("conditions") or "Không rõ"

                lines.append(f"- {label}:")
                lines.append(
                    f"  Nhiệt độ: {temp_c} độ C (cảm giác {feels_c} độ C)"
                )
                lines.append(f"  Trạng thái: {condition}")
                if humidity is not None:
                    lines.append(f"  Độ ẩm: {humidity}%")
                lines.append(f"  Tốc độ gió: {wind_ms} m/s")

                hour_hint = self._build_hour_hint(day_data)
                if hour_hint:
                    lines.append(f"  3 giờ tới: {hour_hint}")

                suggestion = self._build_suggestion(
                    temp=float(temp_c),
                    humidity=int(float(humidity or 0)),
                    weather_desc=str(condition),
                )
                lines.append(f"  Gợi ý: {suggestion}")
                continue

            if not day_data:
                lines.append(f"- {label}: Chưa có dữ liệu.")
                continue

            temp_max_c = self._f_to_c(day_data.get("tempmax"))
            temp_min_c = self._f_to_c(day_data.get("tempmin"))
            humidity = day_data.get("humidity")
            wind_ms = self._mph_to_ms(day_data.get("windspeed"))
            condition = day_data.get("conditions") or "Không rõ"

            lines.append(f"- {label}:")
            lines.append(f"  Nhiệt độ: {temp_min_c} - {temp_max_c} độ C")
            lines.append(f"  Trạng thái: {condition}")
            if humidity is not None:
                lines.append(f"  Độ ẩm: {humidity}%")
            lines.append(f"  Tốc độ gió: {wind_ms} m/s")
            suggestion = self._build_suggestion(
                temp=float((temp_min_c + temp_max_c) / 2),
                humidity=int(float(humidity or 0)),
                weather_desc=str(condition),
            )
            lines.append(f"  Gợi ý: {suggestion}")

        lines.append(f"URL theo dõi: {self._build_visualcrossing_city_url(resolved)}")
        return "\n".join(lines)

    def _extract_specific_dates(self, msg: str) -> list[date]:
        text = self._normalize_text(msg)
        found: list[date] = []

        for d, m, y in re.findall(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text):
            try:
                found.append(date(int(y), int(m), int(d)))
            except ValueError:
                pass

        for d, m, y in re.findall(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b", text):
            try:
                found.append(date(int(y), int(m), int(d)))
            except ValueError:
                pass

        for y, m, d in re.findall(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text):
            try:
                found.append(date(int(y), int(m), int(d)))
            except ValueError:
                pass

        # Natural Vietnamese format: "ngay 22 thang 3 nam 2026"
        for d, m, y in re.findall(
            r"\b(?:ngay\s+)?(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(\d{4})\b",
            text,
        ):
            try:
                found.append(date(int(y), int(m), int(d)))
            except ValueError:
                pass

        # Variant with comma before year: "ngay 22 thang 3, 2026"
        for d, m, y in re.findall(
            r"\b(?:ngay\s+)?(\d{1,2})\s+thang\s+(\d{1,2})\s*,\s*(\d{4})\b",
            text,
        ):
            try:
                found.append(date(int(y), int(m), int(d)))
            except ValueError:
                pass

        if not found:
            return []

        unique = sorted(set(found))
        # Guardrail: avoid too long historical/future spans from accidental date parsing.
        return [d for d in unique if abs((d - datetime.now().date()).days) <= 3650]

    def _build_visualcrossing_city_url(self, resolved_location: str) -> str:
        city = (resolved_location or "").split(",")[0].strip()
        if not city:
            city = "vietnam"
        safe_city = quote(city, safe="")
        return f"https://www.visualcrossing.com/weather-query-builder/{safe_city}/?v=wizard"

    def _build_hour_hint(self, day_data: dict | None) -> str:
        if not isinstance(day_data, dict):
            return ""
        hours = day_data.get("hours")
        if not isinstance(hours, list) or not hours:
            return ""

        snippets: list[str] = []
        for hour in hours[:3]:
            if not isinstance(hour, dict):
                continue
            hour_key = str(hour.get("datetime") or "")[:5]
            cond = str(hour.get("conditions") or "").strip()
            temp_c = self._f_to_c(hour.get("temp"))
            if hour_key and cond:
                snippets.append(f"{hour_key} {temp_c}C ({cond})")

        return "; ".join(snippets)

    def _normalize_text(self, text: str) -> str:
        normalized = unicodedata.normalize("NFD", text.lower())
        stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return stripped.replace("-", " ").strip()

    def _f_to_c(self, value: float | int | str | None) -> float:
        if value is None:
            return 0.0
        try:
            return round((float(value) - 32) * 5 / 9, 1)
        except (TypeError, ValueError):
            return 0.0

    def _mph_to_ms(self, value: float | int | str | None) -> float:
        if value is None:
            return 0.0
        try:
            return round(float(value) * 0.44704, 1)
        except (TypeError, ValueError):
            return 0.0

    def _build_suggestion(self, temp: float, humidity: int, weather_desc: str) -> str:
        normalized_desc = self._normalize_text(weather_desc)
        if any(k in normalized_desc for k in ["bao", "giong", "thunderstorm"]):
            return "Nên hạn chế ra ngoài, ưu tiên an toàn và tránh khu vực cây cao/cột điện."
        if "mua" in normalized_desc:
            return "Nên mang ô hoặc áo mưa khi ra ngoài."
        if temp >= 33:
            return "Trời khá nóng, nên uống đủ nước và hạn chế ra đường buổi trưa."
        if temp <= 18:
            return "Trời lạnh, nên mặc áo ấm khi ra ngoài vào sáng sớm hoặc tối."
        if humidity >= 85:
            return "Độ ẩm cao, nên mặc đồ thoáng và giữ cơ thể khô ráo."
        return "Thời tiết tương đối dễ chịu, bạn có thể di chuyển bình thường."

    def _extract_locations(self, msg: str) -> list[str]:
        raw_text = msg.strip()
        if not raw_text:
            return []

        text = self._normalize_text(raw_text)
        match = re.search(r"(?:tai|o)\s+(.+)$", text, re.IGNORECASE)
        segment = match.group(1).strip() if match else text

        if not match:
            # Handle patterns like "thoi tiet da nang hom qua the nao".
            segment = re.sub(
                r"^(thoi tiet|du bao thoi tiet|nhiet do|weather)\s+",
                "",
                segment,
                flags=re.IGNORECASE,
            )

        segment = re.split(
            r"\?|\.|!|\b(the nao|ra sao|la sao|sao roi|khong)\b",
            segment,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        normalized_separators = re.sub(r"\s+va\s+|\s+và\s+", "|", segment, flags=re.IGNORECASE)
        normalized_separators = normalized_separators.replace(";", "|").replace(",", "|")
        parts = [p.strip(" .,!?:;'\"-") for p in normalized_separators.split("|")]

        cleaned = [self._normalize_location_alias(self._clean_location_fragment(p)) for p in parts]
        cleaned = [p for p in cleaned if p and len(p) <= 80]
        if cleaned:
            return cleaned

        fallback = self._extract_single_location(raw_text)
        if not fallback:
            return []
        return [self._normalize_location_alias(self._clean_location_fragment(fallback))]

    def _clean_location_fragment(self, text: str) -> str:
        stripped = text.strip(" .,!?:;'\"-")
        stripped = self._normalize_text(stripped)
        stripped = re.sub(
            r"\b(thoi tiet|du bao thoi tiet|nhiet do|weather)\b",
            "",
            stripped,
            flags=re.IGNORECASE,
        )
        stripped = re.sub(
            r"\b(hom nay|hom qua|hom kia|ngay mai|ngay kia|sau\s+\d+\s+ngay|truoc\s+\d+\s+ngay|cach day\s+\d+\s+ngay|the nao|ra sao|la sao|khong)\b",
            "",
            stripped,
            flags=re.IGNORECASE,
        )
        stripped = re.sub(r"\s+", " ", stripped).strip()
        stripped = stripped.strip(" .,!?:;'\"-")
        return stripped

    def _normalize_location_alias(self, location: str) -> str:
        normalized = self._normalize_text(location)
        alias_map = {
            "hcm": "ho chi minh",
            "tp hcm": "ho chi minh",
            "tphcm": "ho chi minh",
            "sai gon": "ho chi minh",
            "sg": "ho chi minh",
            "hn": "ha noi",
            "danang": "da nang",
        }
        return alias_map.get(normalized, normalized)

    def _extract_single_location(self, msg: str) -> str | None:
        patterns = [
            r"thời tiết (?:ở |tại )?(.+?)(?:\?|$| hôm nay| ngày mai| hôm qua| hôm kia| thế nào)",
            r"nhiệt độ (?:ở |tại )?(.+?)(?:\?|$| hôm nay| ngày mai| hôm qua| hôm kia| thế nào)",
            r"(?:ở|tại) (.+?) (?:hôm nay|ngày mai|hôm qua|hôm kia|nhiệt độ|thời tiết|thế nào)",
            r"thoi tiet (?:o |tai )?(.+?)(?:\?|$| hom nay| ngay mai| hom qua| hom kia| the nao)",
            r"(?:o|tai) (.+?) (?:hom nay|ngay mai|hom qua|hom kia|nhiet do|thoi tiet|the nao)",
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

    def _extract_day_offsets(self, msg: str) -> list[int]:
        text = self._normalize_text(msg)

        range_past = re.search(
            r"(\d+)\s*(?:-|den|toi|to)\s*(\d+)\s*ngay\s*(?:truoc|qua)",
            text,
        )
        if range_past:
            a, b = int(range_past.group(1)), int(range_past.group(2))
            lo, hi = min(a, b), max(a, b)
            return [-(d) for d in range(lo, hi + 1)]

        range_future = re.search(
            r"(?:sau)\s*(\d+)\s*(?:-|den|toi|to)\s*(\d+)\s*ngay",
            text,
        )
        if range_future:
            a, b = int(range_future.group(1)), int(range_future.group(2))
            lo, hi = min(a, b), max(a, b)
            return [d for d in range(lo, hi + 1)]

        past = re.search(r"(?:cach day|truoc)\s*(\d+)\s*ngay", text)
        if past:
            return [-int(past.group(1))]

        past_rev = re.search(r"(\d+)\s*ngay\s*(?:truoc|qua)", text)
        if past_rev:
            return [-int(past_rev.group(1))]

        future = re.search(r"(?:sau|toi)\s*(\d+)\s*ngay", text)
        if future:
            return [int(future.group(1))]

        if "hom qua" in text:
            return [-1]
        if "hom kia" in text:
            return [-2]
        if "2-3 ngay" in text and ("truoc" in text or "qua" in text):
            return [-2, -3]
        if "ngay kia" in text:
            return [2]
        if "ngay mai" in text:
            return [1]
        if "hien tai" in text or "bay gio" in text or "luc nay" in text:
            return [0]

        return [0]

    def _label_for_offset(self, offset: int) -> str:
        if offset == 0:
            return "Hiện tại / hôm nay"
        if offset == -1:
            return "Hôm qua"
        if offset == 1:
            return "Ngày mai"
        if offset < 0:
            return f"{abs(offset)} ngày trước"
        return f"Sau {offset} ngày"
