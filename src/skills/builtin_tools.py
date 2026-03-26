"""内置工具：联网搜索、记忆检索。"""
from __future__ import annotations
from typing import Any

from src.skills.web_search import run_web_search

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索互联网获取最新信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_long_term_memory",
            "description": "从长期记忆中检索相关信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索内容"}
                },
                "required": ["query"],
            },
        },
    },
]


async def run_tool(
    name: str, args: dict, *, chat_id: str, vector_query_fn
) -> str | None:
    if name == "web_search":
        return await run_web_search(str(args.get("query", "")))

    if name == "recall_long_term_memory":
        result = vector_query_fn(chat_id, str(args.get("query", "")))
        return result or "未找到相关记忆"

    return None
