import asyncio
import json
import logging
from typing import Any, Optional

import httpx

from src.core.config import settings
from src.core.memory import memory
from src.core.vector_memory import vector_db
from src.skills.registry import get_loaded_skill_summary
from src.skills.tools import TOOL_DEFINITIONS, run_tool

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self):
        self.api_url = settings.get("openclaw.api_url", "").rstrip("/")
        self.api_key = settings.get("openclaw.api_key")
        self.model = settings.get("openclaw.model", "deepseek-chat")
        self.enable_tools = bool(settings.get("openclaw.enable_tools", True))
        self.max_tool_rounds = int(settings.get("openclaw.max_tool_rounds", 5))
        self.store_each_turn = bool(settings.get("memory.store_each_turn_in_vector", False))
        skills_summary = get_loaded_skill_summary() if self.enable_tools else "(disabled)"
        print(f"[Agent] ready model={self.model} tools={self.enable_tools} skills=[{skills_summary}]")

    async def get_simple_chat(self, prompt: str) -> str:
        url = f"{self.api_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                result = response.json()
                return result["choices"][0]["message"]["content"] or ""
        except Exception as e:
            print(f"❌ [Internal] 简单对话请求失败: {e}")
            return ""

    async def _post_chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
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
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")
            return response.json()

    async def get_response(self, chat_id, user_text: str) -> str:
        if not self.api_url or not self.api_key:
            return "错误：未配置 AI 接口地址或密钥，请检查 config.yaml"

        long_term_history = vector_db.query_context(chat_id, user_text)
        summary, short_history = memory.get_context(chat_id)

        system_content = (
            "你是一个拥有长期记忆与联网检索能力的实用 AI 助手。"
            "在需要事实核查或最新信息时，应主动调用 web_search；"
            "在需要回忆历史约定时，可调用 recall_long_term_memory。"
            "系统已预检索部分相关记忆片段，请与工具结果一并参考。\n"
            "【天气类问题】若用户明确问「今天/现在/当地」天气，你只能根据检索结果总结当日或未来 48 小时预报（晴雨、气温范围、风等）；"
            "不得用「整个三月气候特点」「季节概况」等月度/气候学描述代替今日预报。"
            "若检索摘要里没有当日实况，须如实说明并建议用户查看气象台或天气 App，不要编造。"
        )
        if summary:
            system_content += f"\n【会话滚动摘要】：\n{summary}"
        if long_term_history:
            system_content += (
                f"\n【预检索的长期记忆片段】：\n{long_term_history}\n"
                "（可与 recall_long_term_memory 结果互相补充）"
            )

        messages: list[dict[str, Any]] = [{"role": "system", "content": system_content}]
        messages.extend(short_history)
        messages.append({"role": "user", "content": user_text})

        tools = TOOL_DEFINITIONS if self.enable_tools else None

        print(
            f"🧠 AI 思考中... (ID: {chat_id} | 短期消息数: {len(short_history)} | "
            f"预检索记忆: {'有' if long_term_history else '无'})"
        )

        try:
            rounds = 0
            while rounds < self.max_tool_rounds:
                rounds += 1
                result = await self._post_chat(messages, tools=tools)
                msg = result["choices"][0]["message"]
                tool_calls = msg.get("tool_calls")

                if tool_calls:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": msg.get("content") or "",
                            "tool_calls": tool_calls,
                        }
                    )
                    for tc in tool_calls:
                        fn = tc.get("function") or {}
                        name = fn.get("name") or ""
                        raw_args = fn.get("arguments") or "{}"
                        out = await run_tool(
                            name,
                            raw_args,
                            chat_id,
                            vector_db.query_context,
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.get("id", ""),
                                "content": out,
                            }
                        )
                    continue

                ai_reply = msg.get("content") or ""
                if not ai_reply:
                    ai_reply = "（模型未返回文本）"

                memory.add_message(chat_id, "user", user_text)
                memory.add_message(chat_id, "assistant", ai_reply)

                if self.store_each_turn:
                    asyncio.create_task(
                        self._persist_turn(chat_id, user_text, ai_reply)
                    )

                asyncio.create_task(memory.try_summarize(chat_id, self))
                print("✅ AI 响应成功")
                return ai_reply

            return "工具调用次数过多，请简化问题后重试。"

        except Exception as e:
            logger.exception("Agent 运行异常")
            print(f"🔥 Agent 运行崩溃: {e}")
            return "我的大脑连接线断了..."

    async def _persist_turn(self, chat_id, user_text: str, ai_reply: str) -> None:
        try:
            vector_db.save_iteration(chat_id, user_text, ai_reply)
        except Exception as e:
            print(f"⚠️ 单轮向量写入失败: {e}")


agent = Agent()
