from agents.base import BaseAgent
from services.news_service import get_news


class NewsAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return """
Ban la tro ly tin tuc cua SGroup. Du lieu tin tuc thuc te da duoc cung cap.

Tom tat toi da 8 tin noi bat:
- [Tieu de] - [1-2 cau mo ta] - [Nguon]

Giu thai do khach quan, trung lap, ghi ro thoi gian dang.
Khong dua nhan xet chinh tri.
"""

    async def fetch_data(self, message: str) -> str:
        articles = await get_news(message, limit=6)
        if not articles:
            return "[Không lấy được tin tức phù hợp với truy vấn.]"

        lines = [
            "[DỮ LIỆU TIN TỨC ĐA NGUỒN]",
            f"Từ khóa/chủ đề: {message}",
        ]
        valid_count = 0
        for article in articles:
            title = (article.get("title", "") or "").strip()
            if not title or len(title) < 8:
                continue

            description = (article.get("description", "") or "").strip()
            description = description[:220] if description else "Không có mô tả ngắn."
            source = article.get("source", {}).get("name", "")
            published = article.get("publishedAt", "")[:19]
            url = article.get("url", "")

            valid_count += 1

            lines.append(
                f"{valid_count}. {title}\n"
                f"   {description}\n"
                f"   Nguồn: {source} | Thời gian: {published}\n"
                f"   URL: {url}"
            )

        if valid_count == 0:
            return "[Không tìm thấy bài báo phù hợp sau khi lọc dữ liệu.]"

        return "\n\n".join(lines)

    async def handle(
        self,
        message: str,
        history: list[dict],
        external_data: str = "",
    ) -> str:
        # Deterministic output to prevent LLM rewriting news snippets into garbled text.
        _ = (message, history)
        if external_data:
            return external_data
        return "[Không lấy được tin tức phù hợp với truy vấn.]"
