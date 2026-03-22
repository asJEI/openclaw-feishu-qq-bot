import asyncio
import logging
import re
from datetime import date
from typing import Any

from src.core.config import settings

logger = logging.getLogger(__name__)


def _search_provider() -> str:
    """auto：配置了腾讯云 WSA 则优先 WSA，否则 ddgs；tencent_wsa 仅 WSA；ddgs 仅 ddgs。"""
    p = (settings.get("search.provider") or "auto").strip().lower()
    if p in ("tencent_wsa", "tencent", "wsa"):
        return "tencent_wsa"
    if p == "ddgs":
        return "ddgs"
    return "auto"

_WEATHER_KEYS = (
    "天气",
    "气温",
    "降雨",
    "下雨",
    "下雪",
    "多云",
    "晴天",
    "阴天",
    "预报",
    "空气质量",
    "湿度",
    "风力",
    "台风",
    "降温",
    "升温",
)
_WEATHER_EN = ("weather", "forecast", "temperature", "humidity", "rain", "snow")


def _is_weather_intent(text: str) -> bool:
    low = text.lower()
    if any(k in text for k in _WEATHER_KEYS):
        return True
    return any(w in low for w in _WEATHER_EN)


def _enrich_weather_search_query(q: str) -> str:
    """天气类查询自动补上当天日期，减少搜到「整月气候」综述页的概率。"""
    if not _is_weather_intent(q):
        return q
    today = date.today()
    iso = today.isoformat()
    zh = f"{today.year}年{today.month}月{today.day}日"
    if iso in q or re.search(r"\d{4}年\d{1,2}月\d{1,2}日", q):
        return q
    if zh in q:
        return q
    return f"{q} {iso} 今日天气预报"


_WEATHER_TOOL_HINT = (
    "【检索结果使用说明】若用户问的是「今天天气」，请只依据与「当日/今明两天预报」直接相关的条目作答；"
    "忽略整月气候、常年平均、季节综述类内容，更不要用它代替今日预报。"
    "若下列摘要中明显没有今日数据，请明确说当前结果不足以给出今日实况。\n\n"
)


def _normalize_row(r: dict[str, Any]) -> dict[str, str] | None:
    title = (r.get("title") or "").strip()
    href = (r.get("href") or r.get("link") or "").strip()
    body = (r.get("body") or r.get("snippet") or "").strip()
    if not (title or body):
        return None
    return {"title": title, "url": href, "snippet": body}


def _sync_search(query: str, max_results: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    provider = _search_provider()

    if provider in ("auto", "tencent_wsa"):
        from src.skills.tencent_wsa import is_configured, search_sync as tencent_search_sync

        if provider == "tencent_wsa" or is_configured():
            if is_configured():
                try:
                    out = tencent_search_sync(query, max_results)
                except Exception as e:
                    logger.info("腾讯云 WSA 搜索异常: %s", e)
                    out = []
            if out:
                return out
            if provider == "tencent_wsa":
                return []

    if provider == "tencent_wsa":
        return []

    # ddgs / auto 回退
    # 优先 ddgs：duckduckgo-search 近期版本强制只走 Bing，国内易失败
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            raw = ddgs.text(query, max_results=max_results)
        for r in raw or []:
            if isinstance(r, dict):
                row = _normalize_row(r)
                if row:
                    out.append(row)
        if out:
            return out
    except Exception as e:
        logger.info("ddgs 搜索失败: %s", e)

    # 备选：旧包（部分环境仍可用）
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            raw = ddgs.text(query, max_results=max_results)
        for r in raw or []:
            if isinstance(r, dict):
                row = _normalize_row(r)
                if row:
                    out.append(row)
    except Exception as e:
        logger.info("duckduckgo_search 搜索失败: %s", e)

    return out


async def run_web_search(query: str, max_results: int = 5) -> str:
    q = (query or "").strip()
    if not q:
        return "（空查询）"

    weather = _is_weather_intent(q)
    q_search = _enrich_weather_search_query(q)
    n = min(max_results, 4) if weather else max_results

    try:
        rows = await asyncio.to_thread(_sync_search, q_search, n)
    except Exception as e:
        logger.exception("联网搜索线程异常")
        return (
            f"联网搜索出现异常（{type(e).__name__}）。"
            "若在国内网络可优先使用 ddgs；仍失败可在 config 中设置 openclaw.enable_tools: false。"
        )

    if not rows:
        if _search_provider() == "tencent_wsa":
            return (
                "未获取到腾讯云联网搜索结果。请检查 config 中 tencent_wsa 密钥、"
                "控制台是否已开通联网搜索 API（WSA），以及 endpoint/region 是否与账号地域一致。"
            )
        return (
            "未获取到搜索结果（可能被目标站点限制或网络不可用）。"
            "请稍后再试；若已配置腾讯云 WSA，可将 search.provider 设为 auto 并启用 tencent_wsa。"
        )

    lines = []
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. {r['title']}\n   {r['snippet']}\n   {r['url']}")
    body = "\n\n".join(lines)
    if weather:
        return _WEATHER_TOOL_HINT + f"（实际检索使用的关键词：{q_search}）\n\n" + body
    return body
