"""示例技能：返回服务器本地时间（可复制此文件改名后编写自己的工具）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_server_local_time",
            "description": "获取机器人服务端当前的本地日期与时间（ISO 格式）。用户问「现在几点」「今天几号」且无需联网时可用。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }
]


async def run_tool(
    name: str,
    args: dict,
    *,
    chat_id: str,
    vector_query_fn,
) -> str | None:
    if name != "get_server_local_time":
        return None
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S（服务器本地时间）")
