"""联网搜索。支持腾讯云 WSA 和 DuckDuckGo。"""
import asyncio
import logging
from datetime import date
from typing import Any

from src.core.config import settings

logger = logging.getLogger(__name__)

_WEATHER_KEYWORDS = (
    "天气", "气温", "降雨", "下雨", "下雪", "多云", "晴天", "阴天",
    "预报", "空气质量", "湿度", "风力", "台风", "降温", "升温",
)


def _is_weather(query: str) -> bool:
    return any(k in query for k in _WEATHER_KEYWORDS)


def _enrich_query(query: str) -> str:
    """天气查询自动补全日期。"""
    if not _is_weather(query):
        return query
    today = date.today().isoformat()
    if today in query:
        return query
    return f"{query} {today}"


def _normalize(result: dict[str, Any]) -> dict[str, str] | None:
    title = (result.get("title") or "").strip()
    url = (result.get("href") or result.get("link") or "").strip()
    snippet = (result.get("body") or result.get("snippet") or "").strip()
    if not (title or snippet):
        return None
    return {"title": title, "url": url, "snippet": snippet}


def _search_sync(query: str, max_results: int) -> list[dict[str, str]]:
    """同步搜索，优先腾讯云 WSA，失败则回退到 DuckDuckGo。"""
    results: list[dict[str, str]] = []
    provider = (settings.get("search.provider") or "auto").strip().lower()

    # 尝试腾讯云 WSA
    if provider in ("auto", "tencent_wsa"):
        from src.skills.tencent_wsa import is_configured, search_sync as tencent_search

        if is_configured():
            try:
                results = tencent_search(query, max_results)
                if results:
                    return results
            except Exception as e:
                logger.info("Tencent WSA failed: %s", e)

        if provider == "tencent_wsa":
            return []

    # 回退到 DuckDuckGo
    for module_name in ("ddgs", "duckduckgo_search"):
        try:
            mod = __import__(module_name, fromlist=["DDGS"])
            with mod.DDGS() as ddgs:
                raw = ddgs.text(query, max_results=max_results)
            for r in raw or []:
                if isinstance(r, dict):
                    row = _normalize(r)
                    if row:
                        results.append(row)
            if results:
                return results
        except Exception as e:
            logger.info("%s failed: %s", module_name, e)

    return results


async def run_web_search(query: str, max_results: int = 5) -> str:
    q = (query or "").strip()
    if not q:
        return "Empty query"

    q_search = _enrich_query(q)
    limit = min(max_results, 4) if _is_weather(q) else max_results

    try:
        rows = await asyncio.to_thread(_search_sync, q_search, limit)
    except Exception as e:
        logger.exception("Search failed")
        return f"Search error: {type(e).__name__}"

    if not rows:
        return "No search results available."

    lines = [f"{i}. {r['title']}\n   {r['snippet']}\n   {r['url']}" for i, r in enumerate(rows, 1)]
    return "\n\n".join(lines)
