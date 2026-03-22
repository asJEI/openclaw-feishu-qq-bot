"""内置技能：联网搜索、长期记忆检索（与 OpenAI function calling 格式一致）。"""

from __future__ import annotations

from typing import Any

from src.skills.web_search import run_web_search

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "在互联网上检索最新信息。新闻、股价、不确定的事实等可用一条聚焦的查询。"
                "若用户问「今天/当地天气」，query 必须同时包含：城市或地区名 + 当天日期（可写 YYYY-MM-DD 或「X月X日」）+「今日/当天天气预报」等字样；"
                "优先一条精准查询，不要为同一问题连续发起多轮宽泛搜索。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "简短检索句。天气类务必含地点+日期+「今日预报」；避免只用「三月气温」这类易返回气候综述的词。",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_long_term_memory",
            "description": "按语义从长期记忆库中检索与该会话相关的历史总结与事实。当用户提到「之前说过」「还记得吗」或需要引用历史约定时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用于向量检索的查询语句，描述你想回忆的内容",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


async def run_tool(
    name: str,
    args: dict,
    *,
    chat_id: str,
    vector_query_fn,
) -> str | None:
    if name == "web_search":
        return await run_web_search(str(args.get("query", "")))

    if name == "recall_long_term_memory":
        q = str(args.get("query", ""))
        chunk = vector_query_fn(chat_id, q)
        return chunk or "（未检索到相关长期记忆）"

    return None
