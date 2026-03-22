"""对外导出：工具定义与分发（由 registry 合并内置 + 插件）。"""

from __future__ import annotations

from src.skills.registry import dispatch_tool, get_tool_definitions

TOOL_DEFINITIONS = get_tool_definitions()


async def run_tool(
    name: str,
    arguments_json: str,
    chat_id: str,
    vector_query_fn,
) -> str:
    return await dispatch_tool(name, arguments_json, chat_id, vector_query_fn)
