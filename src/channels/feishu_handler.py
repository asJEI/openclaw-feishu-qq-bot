"""飞书消息处理器：处理 Webhook 事件、租户认证、消息收发。"""
import json
import asyncio
from collections import OrderedDict
from typing import Any

import httpx

from src.core.agent import agent
from src.core.config import settings
from src.core.logger import logger

# 常量配置
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
MAX_PROCESSED_EVENTS = 1000  # 事件去重队列最大长度
MAX_SEND_RETRIES = 2  # 消息发送重试次数


class FeishuHandler:
    """飞书事件处理器。"""

    def __init__(self) -> None:
        self.app_id = settings.get("feishu.app_id")
        self.app_secret = settings.get("feishu.app_secret")
        # LRU 缓存：防止内存无限增长
        self._processed_events: OrderedDict[str, None] = OrderedDict()

    def _is_duplicate(self, event_id: str) -> bool:
        """检查事件是否已处理，使用 LRU 缓存。"""
        if event_id in self._processed_events:
            return True
        self._processed_events[event_id] = None
        if len(self._processed_events) > MAX_PROCESSED_EVENTS:
            self._processed_events.popitem(last=False)
        return False

    async def _get_tenant_token(self) -> str | None:
        """获取飞书租户访问令牌。"""
        url = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json().get("tenant_access_token")
        except Exception:
            logger.exception("获取飞书租户令牌失败")
            return None

    def handle_event(self, data: dict[str, Any]) -> dict[str, Any]:
        """处理飞书 Webhook 事件，返回同步响应。"""
        # URL 验证：飞书控制台配置时需要
        if data.get("type") == "url_verification":
            return {"challenge": data.get("challenge")}

        header = data.get("header", {})
        event_id = header.get("event_id")
        event_type = header.get("event_type")

        # 去重检查
        if event_id and self._is_duplicate(event_id):
            logger.debug("重复事件，跳过: %s", event_id)
            return {"code": 0}

        # 异步处理消息，立即返回避免飞书重试
        if event_type == "im.message.receive_v1":
            asyncio.create_task(self._process_message(data))

        return {"code": 0}

    async def _process_message(self, data: dict[str, Any]) -> None:
        """异步处理单条消息。"""
        try:
            event = data.get("event", {})
            message = event.get("message", {})
            chat_id = message.get("chat_id")
            msg_type = message.get("message_type")

            if not chat_id or msg_type != "text":
                logger.debug("忽略非文本消息: type=%s", msg_type)
                return

            content = json.loads(message.get("content", "{}"))
            user_text = content.get("text", "").strip()

            if not user_text:
                return

            logger.info("飞书消息: %s", user_text[:50] + "..." if len(user_text) > 50 else user_text)

            reply = await agent.get_response(chat_id, user_text)
            await self._send_with_retry(chat_id, reply)

        except Exception:
            logger.exception("处理飞书消息失败")

    async def _send_with_retry(self, chat_id: str, text: str) -> bool:
        """发送消息，带重试机制。"""
        token = await self._get_tenant_token()
        if not token:
            return False

        url = f"{FEISHU_API_BASE}/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        params = {"receive_id_type": "chat_id"}
        payload = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        }

        for attempt in range(MAX_SEND_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, params=params, json=payload, headers=headers)
                    resp.raise_for_status()
                    logger.info("飞书消息已发送: chat_id=%s", chat_id)
                    return True
            except Exception:
                if attempt < MAX_SEND_RETRIES:
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    logger.exception("发送飞书消息失败，已重试%d次", MAX_SEND_RETRIES)

        return False
