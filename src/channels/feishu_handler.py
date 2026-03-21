import json
import asyncio
import httpx
from src.core.agent import agent
from src.core.config import settings

class FeishuHandler:
    def __init__(self):
        self.app_id = settings.get("feishu.app_id")
        self.app_secret = settings.get("feishu.app_secret")
        # 用于去重：记录最近处理过的消息 ID
        self.processed_msgs = set()

    async def get_tenant_access_token(self):
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload)
            return res.json().get("tenant_access_token")

    async def handle_event(self, data):
        # 1. 响应 URL 验证
        if data.get("type") == "url_verification":
            return {"challenge": data.get("challenge")}

        header = data.get("header", {})
        event_id = header.get("event_id") # 每个事件唯一的 ID

        # 2. 去重逻辑：如果这个 event_id 处理过了，直接跳过
        if event_id in self.processed_msgs:
            return {"code": 0}
        self.processed_msgs.add(event_id)

        # 3. 异步处理：不等待 AI，直接返回 200 给飞书
        if header.get("event_type") == "im.message.receive_v1":
            # 使用 asyncio.create_task 让它在后台运行
            asyncio.create_task(self.process_and_reply(data))

        # 立刻返回，防止飞书重试
        return {"code": 0}

    async def process_and_reply(self, data):
        """后台异步处理逻辑"""
        try:
            event = data.get("event", {})
            message = event.get("message", {})
            chat_id = message.get("chat_id")
            
            content_str = message.get("content", "{}")
            user_text = json.loads(content_str).get("text", "")

            if user_text:
                print(f"📩 正在处理消息: {user_text}")
                reply = await agent.get_response(chat_id, user_text)
                await self.send_text_message(chat_id, reply)
        except Exception as e:
            print(f"❌ 异步处理出错: {e}")

    async def send_text_message(self, chat_id, text):
        token = await self.get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        payload = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text})
        }
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers)
            print("✅ 回复已送达")