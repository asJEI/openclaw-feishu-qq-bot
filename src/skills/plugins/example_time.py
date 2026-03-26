"""示例技能：获取服务器时间。"""
from __future__ import annotations
from datetime import datetime
from typing import Any


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_server_time",
            "description": "获取服务器当前时间",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }
]


async def run_tool(name: str, args: dict, *, chat_id: str, vector_query_fn) -> str | None:
    if name != "get_server_time":
        return None
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
