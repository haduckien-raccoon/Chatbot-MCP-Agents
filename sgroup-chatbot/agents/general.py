import re
import unicodedata

from agents.base import BaseAgent


class GeneralAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return """
Ban la SGroup AI Assistant - chatbot thong minh duoc SGroup phat trien.

Khi duoc hoi "ban la ai?" hoac tuong tu, hay tra loi rang:
Toi la AI chatbot duoc SGroup phat trien. Toi co the giup ban:
- Tra cuu thoi tiet theo thoi gian thuc
- Cap nhat tin tuc, thoi su trong nuoc va quoc te
- Giai dap kien thuc IT, lap trinh, cong nghe
- Tim hieu ve SGroup, van hoa va quy trinh cong ty
- Kham pha AI Team va cac du an AI cua SGroup
- Huong dan su dung cac module/san pham cua SGroup

Luon than thien, ngan gon, chuyen nghiep.
Tra loi bang ngon ngu nguoi dung dang dung (Tieng Viet hoac Tieng Anh).
"""

    def _normalize(self, text: str) -> str:
        lowered = (text or "").lower().strip()
        normalized = unicodedata.normalize("NFD", lowered)
        stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return re.sub(r"\s+", " ", stripped)

    async def handle(
        self,
        message: str,
        history: list[dict],
        external_data: str = "",
    ) -> str:
        _ = (history, external_data)
        normalized = self._normalize(message)

        if re.search(
            r"\b(ban la ai|ban la gi|ai day|ai vay|gioi thieu ban than|ban lam duoc gi|chuc nang|tinh nang|chatbot)\b",
            normalized,
            re.IGNORECASE,
        ):
            return (
                "Mình là chatbot AI của SGroup.\n"
                "Mình có thể hỗ trợ bạn:\n"
                "- Tra cứu thời tiết theo địa điểm và mốc thời gian (hiện tại, quá khứ, ngày cụ thể).\n"
                "- Tìm và tổng hợp tin tức theo chủ đề (ví dụ: thể thao, công nghệ).\n"
                "- Hỗ trợ kiến thức IT/lập trình và tìm nguồn tham khảo.\n"
                "- Cung cấp thông tin về SGroup dựa trên dữ liệu đã xác minh.\n"
                "Bạn muốn mình hỗ trợ mục nào trước?"
            )

        return await super().handle(message=message, history=history, external_data=external_data)
