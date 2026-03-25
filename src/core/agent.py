"""AI Agent：处理对话、工具调用、记忆管理。"""
import asyncio
import json
from typing import Any

import httpx

from src.core.config import settings
from src.core.memory import memory
from src.core.vector_memory import vector_db
from src.core.logger import logger
from src.skills.registry import get_loaded_skill_summary
from src.skills.tools import TOOL_DEFINITIONS, run_tool

DEFAULT_TIMEOUT = 120.0


class Agent:
    """AI Agent 核心类。"""

    def __init__(self) -> None:
        self.api_url = settings.get("openclaw.api_url", "").rstrip("/")
        self.api_key = settings.get("openclaw.api_key")
        self.model = settings.get("openclaw.model", "deepseek-chat")
        self.enable_tools = bool(settings.get("openclaw.enable_tools", True))
        self.max_tool_rounds = int(settings.get("openclaw.max_tool_rounds", 5))
        self.store_each_turn = bool(settings.get("memory.store_each_turn_in_vector", False))
        self.system_prompt = settings.get("system_prompt", self._default_prompt())

        skills = get_loaded_skill_summary() if self.enable_tools else "disabled"
        logger.info("Agent ready: model=%s tools=%s skills=[%s]", self.model, self.enable_tools, skills)

    def _default_prompt(self) -> str:
        return "你是一个拥有长期记忆与联网检索能力的实用 AI 助手。"

    async def _chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """调用 LLM API。"""
        url = f"{self.api_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def get_response(self, chat_id: str, user_text: str) -> str:
        """获取 AI 回复，支持工具调用。"""
        if not self.api_url or not self.api_key:
            return "错误：未配置 AI 接口地址或密钥"

        long_term = vector_db.query_context(chat_id, user_text)
        summary, short_history = memory.get_context(chat_id)

        system_content = self._build_system_content(summary, long_term)
        messages: list[dict] = [{"role": "system", "content": system_content}]
        messages.extend(short_history)
        messages.append({"role": "user", "content": user_text})

        tools = TOOL_DEFINITIONS if self.enable_tools else None
        logger.info("AI 思考中: chat_id=%s short_msgs=%d has_long_term=%s",
                    chat_id, len(short_history), bool(long_term))

        try:
            return await self._run_with_tools(chat_id, messages, tools, user_text)
        except Exception:
            logger.exception("Agent 运行异常")
            return "服务暂时不可用，请稍后重试"

    def _build_system_content(self, summary: str, long_term: str) -> str:
        """构建系统提示词。"""
        content = self.system_prompt
        if summary:
            content += f"\n\n【会话摘要】\n{summary}"
        if long_term:
            content += f"\n\n【相关记忆】\n{long_term}"
        return content

    async def _run_with_tools(
        self, chat_id: str, messages: list[dict], tools: list[dict] | None, user_text: str
    ) -> str:
        """执行带工具调用的对话循环。"""
        for _ in range(self.max_tool_rounds):
            result = await self._chat(messages, tools=tools)
            msg = result["choices"][0]["message"]
            tool_calls = msg.get("tool_calls")

            if tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.get("content") or "",
                    "tool_calls": tool_calls,
                })
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    args = fn.get("arguments", "{}")
                    output = await run_tool(name, args, chat_id, vector_db.query_context)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": output,
                    })
                continue

            reply = msg.get("content") or "（无回复）"
            self._save_turn(chat_id, user_text, reply)
            return reply

        return "工具调用次数过多，请简化问题"

    def _save_turn(self, chat_id: str, user: str, assistant: str) -> None:
        """保存对话到记忆。"""
        memory.add_message(chat_id, "user", user)
        memory.add_message(chat_id, "assistant", assistant)

        if self.store_each_turn:
            asyncio.create_task(self._persist_to_vector(chat_id, user, assistant))

        asyncio.create_task(memory.try_summarize(chat_id, self))
        logger.info("AI 响应成功: chat_id=%s", chat_id)

    async def _persist_to_vector(self, chat_id: str, user: str, assistant: str) -> None:
        """异步持久化到向量库。"""
        try:
            vector_db.save_iteration(chat_id, user, assistant)
        except Exception:
            logger.exception("向量存储失败")


agent = Agent()
