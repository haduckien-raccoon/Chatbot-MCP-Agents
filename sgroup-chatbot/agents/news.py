from agents.base import BaseAgent
from services.news_service import get_news


class NewsAgent(BaseAgent):
    @property
    def system_prompt(self) -> str:
        return """
Ban la tro ly tin tuc cua SGroup. Du lieu tin tuc thuc te da duoc cung cap.

Tom tat toi da 5 tin noi bat:
- [Tieu de] - [1-2 cau mo ta] - [Nguon]

Giu thai do khach quan, trung lap, ghi ro thoi gian dang.
Khong dua nhan xet chinh tri.
"""

    async def fetch_data(self, message: str) -> str:
        articles = await get_news(message)
        if not articles:
            return "[Khong lay duoc tin tuc]"

        lines = ["[DU LIEU TIN TUC THUC TE]"]
        for i, article in enumerate(articles, 1):
            lines.append(
                f"{i}. {article.get('title', '')}\n"
                f"   {article.get('description', '')[:150]}\n"
                f"   Nguon: {article.get('source', {}).get('name', '')} | "
                f"{article.get('publishedAt', '')[:10]}\n"
                f"   URL: {article.get('url', '')}"
            )

        return "\n\n".join(lines)
