import asyncio
import html
import re
import unicodedata

import feedparser
import httpx

from config.settings import settings

_BASE = "https://newsapi.org/v2"
_RSS_FEEDS = [
    "https://vnexpress.net/rss/tin-moi-nhat.rss",
    "https://tuoitre.vn/rss/tin-moi-nhat.rss",
    "https://thanhnien.vn/rss/home.rss",
]
_SPORTS_RSS_FEEDS = [
    "https://vnexpress.net/rss/the-thao.rss",
    "https://tuoitre.vn/rss/the-thao.rss",
    "https://thanhnien.vn/rss/the-thao.rss",
]

_STOPWORDS = {
    "tim",
    "giup",
    "toi",
    "minh",
    "cac",
    "bai",
    "bao",
    "tin",
    "tuc",
    "cho",
    "ve",
    "theo",
    "chu",
    "de",
    "hom",
    "nay",
    "moi",
    "nhat",
    "thong",
    "tin",
    "search",
    "xem",
    "tra",
    "cuu",
}

_SPORTS_KEYWORDS = {
    "the thao",
    "bong da",
    "world cup",
    "champions league",
    "premier league",
    "v league",
    "tennis",
    "cau long",
    "bong ro",
    "olympic",
    "marathon",
    "f1",
    "dua xe",
}


def _clean_text(text: str) -> str:
    value = html.unescape((text or "").strip())
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    # Drop replacement/control-like symbols frequently seen in bad RSS encodings.
    value = value.replace("�", " ")
    return value.strip()


def _looks_garbled(text: str) -> bool:
    cleaned = _clean_text(text)
    if not cleaned:
        return True

    # Too many repeated words often indicates broken RSS content.
    tokens = _normalize_text(cleaned).split()
    if not tokens:
        return True

    run = 1
    for i in range(1, len(tokens)):
        if tokens[i] == tokens[i - 1]:
            run += 1
            if run >= 6:
                return True
        else:
            run = 1

    # Excessively long title/description with low diversity can be noisy/garbled.
    if len(tokens) >= 30:
        unique_ratio = len(set(tokens)) / max(1, len(tokens))
        if unique_ratio < 0.28:
            return True

    return False


def _normalize_text(text: str) -> str:
    lowered = _clean_text(text).lower().strip()
    normalized = unicodedata.normalize("NFD", lowered)
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", stripped)


def _is_sports_query(query: str) -> bool:
    normalized = _normalize_text(query)
    return any(k in normalized for k in _SPORTS_KEYWORDS)


def _detect_mode(query: str) -> str:
    q = _normalize_text(query)
    if any(k in q for k in ["moi nhat", "tin moi", "hot", "breaking", "latest"]):
        return "latest"
    if any(k in q for k in ["chu de", "topic", "ve ", "linh vuc", "theo chu de"]):
        return "topic"
    return "keyword"


def _extract_topic(query: str) -> str:
    q = _normalize_text(query)
    q = re.sub(r"\b(tin tuc|news|tim|search|tra cuu|xem)\b", " ", q)
    q = re.sub(r"\b(moi nhat|latest|hot|breaking)\b", " ", q)
    q = re.sub(r"\b(chu de|topic|theo chu de|linh vuc|ve)\b", " ", q)
    q = re.sub(r"\s+", " ", q).strip(" .,!?;:")
    tokens = [t for t in q.split() if len(t) >= 3 and t not in _STOPWORDS]
    cleaned = " ".join(tokens).strip()
    if cleaned:
        return cleaned
    if _is_sports_query(query):
        return "the thao"
    return "viet nam"


def _article_score(article: dict, query: str) -> int:
    target = _normalize_text(
        f"{article.get('title', '')} {article.get('description', '')}"
    )
    query_terms = [
        t
        for t in _normalize_text(query).split()
        if len(t) >= 3 and t not in _STOPWORDS
    ]
    score = sum(1 for term in query_terms if term in target)
    if _is_sports_query(query) and _is_sports_article(article):
        score += 3
    return score


def _is_sports_article(article: dict) -> bool:
    target = _normalize_text(
        f"{article.get('title', '')} {article.get('description', '')} {article.get('url', '')}"
    )
    return any(k in target for k in _SPORTS_KEYWORDS)


def _unique_articles(articles: list[dict]) -> list[dict]:
    seen: set[str] = set()
    merged: list[dict] = []
    for article in articles:
        key = (article.get("url") or article.get("title") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(article)
    return merged


async def search_newsapi(query: str, *, limit: int = 8, mode: str = "keyword") -> list[dict]:
    if not settings.news_api_key:
        return []

    normalized_mode = mode if mode in {"latest", "topic", "keyword"} else "keyword"
    topic = _extract_topic(query)

    is_sports = _is_sports_query(query)

    params = {
        "q": topic,
        "language": "vi",
        "sortBy": "publishedAt",
        "pageSize": max(5, min(limit, 20)),
        "apiKey": settings.news_api_key,
    }
    if normalized_mode == "latest":
        params["q"] = "the thao OR bong da OR tennis" if is_sports else "viet nam OR cong nghe OR kinh te"
    if is_sports:
        params["q"] = f"({params['q']}) AND (the thao OR bong da OR tennis OR olympic)"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{_BASE}/everything", params=params)
        response.raise_for_status()
        raw_articles = response.json().get("articles", [])

    articles: list[dict] = []
    for article in raw_articles:
        cleaned = {
            **article,
            "title": _clean_text(article.get("title", "")),
            "description": _clean_text(article.get("description", "")),
        }
        if _looks_garbled(cleaned.get("title", "")):
            continue
        if cleaned.get("description") and _looks_garbled(cleaned.get("description", "")):
            continue
        if is_sports and not _is_sports_article(cleaned):
            continue
        articles.append(cleaned)

    if normalized_mode in {"topic", "keyword"} and topic:
        ranked = sorted(articles, key=lambda item: _article_score(item, topic), reverse=True)
        return ranked[:limit]
    return articles[:limit]


async def get_rss_news(query: str = "", *, limit: int = 8, mode: str = "keyword") -> list[dict]:
    """Fallback when NewsAPI key is missing or request fails."""
    normalized_mode = mode if mode in {"latest", "topic", "keyword"} else "keyword"
    topic = _extract_topic(query)
    is_sports = _is_sports_query(query)

    articles: list[dict] = []
    feed_urls = _SPORTS_RSS_FEEDS + _RSS_FEEDS if is_sports else _RSS_FEEDS
    for url in feed_urls:
        try:
            feed = await asyncio.to_thread(feedparser.parse, url)
            source_name = _clean_text(feed.feed.get("title", url))
            for entry in feed.entries[:12]:
                item = {
                    "title": _clean_text(entry.get("title", "")),
                    "description": _clean_text(entry.get("summary", "")),
                    "source": {"name": source_name},
                    "publishedAt": entry.get("published", ""),
                    "url": entry.get("link", ""),
                }
                if _looks_garbled(item["title"]):
                    continue
                if item["description"] and _looks_garbled(item["description"]):
                    continue
                if is_sports and not _is_sports_article(item):
                    continue
                if normalized_mode in {"topic", "keyword"} and topic:
                    score = _article_score(item, topic)
                    if score <= 0:
                        continue
                articles.append(item)
        except Exception:
            pass

    if normalized_mode in {"topic", "keyword"} and topic:
        articles = sorted(articles, key=lambda item: _article_score(item, topic), reverse=True)
    return _unique_articles(articles)[:limit]


async def get_news(query: str, *, limit: int = 8) -> list[dict]:
    mode = _detect_mode(query)

    try:
        newsapi_articles = await search_newsapi(query, limit=limit, mode=mode)
    except Exception:
        newsapi_articles = []

    rss_articles = await get_rss_news(query=query, limit=limit, mode=mode)
    merged = _unique_articles(newsapi_articles + rss_articles)

    if _is_sports_query(query):
        merged = [item for item in merged if _is_sports_article(item)]

    if mode in {"topic", "keyword"}:
        merged = sorted(merged, key=lambda item: _article_score(item, _extract_topic(query)), reverse=True)

    return merged[:limit]
