import asyncio
import json
import re
import time
from typing import Any, Optional

import httpx
from fastapi import HTTPException

from src.channels.qq_crypto import normalize_headers, sign_validation_response, verify_webhook_signature
from src.core.agent import agent
from src.core.config import settings


def _strip_qq_mentions(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<@[^>]+>\s*", "", text).strip()


class QQAccessToken:
    def __init__(self):
        self._token: Optional[str] = None
        self._expires_at: float = 0.0

    async def get(self) -> str:
        now = time.time()
        if self._token and now < self._expires_at - 60:
            return self._token
        app_id = settings.get("qq.app_id") or settings.get("qq.bot_id")
        secret = settings.get("qq.client_secret") or settings.get("qq.secret")
        url = "https://bots.qq.com/app/getAppAccessToken"
        payload = {"appId": str(app_id), "clientSecret": str(secret)}
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
        self._token = data.get("access_token")
        exp = data.get("expires_in")
        try:
            self._expires_at = now + float(exp)
        except (TypeError, ValueError):
            self._expires_at = now + 7000
        return self._token


class QQBotHandler:
    def __init__(self):
        self._token_cache = QQAccessToken()
        self.processed_events: set[str] = set()
        self._sandbox = bool(settings.get("qq.sandbox", False))
        self._base = (
            "https://sandbox.api.sgroup.qq.com"
            if self._sandbox
            else "https://api.sgroup.qq.com"
        )
        self._app_id = str(settings.get("qq.app_id") or settings.get("qq.bot_id") or "")
        self._secret = str(settings.get("qq.client_secret") or settings.get("qq.secret") or "")
        self._verify_sig = bool(settings.get("qq.verify_signature", True))

    def _api_headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"QQBot {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    async def handle_raw_webhook(self, headers: dict[str, str], raw_body: bytes) -> dict[str, Any]:
        hdr = normalize_headers(headers)
        if self._verify_sig and self._secret:
            if not verify_webhook_signature(self._secret, hdr, raw_body):
                raise HTTPException(status_code=401, detail="invalid webhook signature")

        expected_app = hdr.get("x-bot-appid")
        if self._app_id and expected_app and expected_app != self._app_id:
            raise HTTPException(status_code=403, detail="X-Bot-Appid mismatch")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise HTTPException(status_code=400, detail="invalid json body")

        op = payload.get("op")
        if op == 13:
            return self._handle_validation(payload)

        if op == 0:
            evt_id = payload.get("id")
            if evt_id:
                if evt_id in self.processed_events:
                    return {"op": 12}
                self.processed_events.add(evt_id)
                if len(self.processed_events) > 5000:
                    self.processed_events.clear()

            t = payload.get("t") or ""
            d = payload.get("d") or {}
            asyncio.create_task(self._dispatch_event(t, d, payload))
            return {"op": 12}

        return {"op": 12}

    def _handle_validation(self, payload: dict[str, Any]) -> dict[str, Any]:
        d = payload.get("d") or {}
        plain = d.get("plain_token") or ""
        event_ts = str(d.get("event_ts") or "")
        if not plain or not event_ts or not self._secret:
            return {"plain_token": plain, "signature": ""}
        sig = sign_validation_response(self._secret, event_ts, plain)
        return {"plain_token": plain, "signature": sig}

    async def _dispatch_event(self, t: str, d: dict[str, Any], envelope: dict[str, Any]) -> None:
        try:
            if t == "C2C_MESSAGE_CREATE":
                await self._on_c2c(d)
            elif t == "GROUP_AT_MESSAGE_CREATE":
                await self._on_group_at(d)
            elif t == "AT_MESSAGE_CREATE":
                await self._on_guild_at(d)
        except Exception as e:
            print(f"❌ [QQ] 事件处理异常 ({t}): {e}")

    async def _on_c2c(self, d: dict[str, Any]) -> None:
        author = d.get("author") or {}
        uid = author.get("user_openid")
        content = _strip_qq_mentions(d.get("content") or "")
        if not content or not uid:
            return
        chat_id = f"qq:c2c:{uid}"
        print(f"📩 [QQ C2C] {content[:80]}...")
        reply = await agent.get_response(chat_id, content)
        await self._send_c2c(uid, reply, msg_id=d.get("id"))

    async def _on_group_at(self, d: dict[str, Any]) -> None:
        gid = d.get("group_openid")
        content = _strip_qq_mentions(d.get("content") or "")
        if not content or not gid:
            return
        chat_id = f"qq:group:{gid}"
        print(f"📩 [QQ Group] {content[:80]}...")
        reply = await agent.get_response(chat_id, content)
        await self._send_group(gid, reply, msg_id=d.get("id"))

    async def _on_guild_at(self, d: dict[str, Any]) -> None:
        channel_id = d.get("channel_id")
        guild_id = d.get("guild_id")
        content = _strip_qq_mentions(d.get("content") or "")
        if not content or not channel_id:
            return
        chat_id = f"qq:guild:{guild_id}:{channel_id}"
        print(f"📩 [QQ Guild] {content[:80]}...")
        reply = await agent.get_response(chat_id, content)
        await self._send_channel(channel_id, reply, msg_id=d.get("id"))

    async def _send_c2c(self, user_openid: str, text: str, msg_id: Optional[str]) -> None:
        token = await self._token_cache.get()
        url = f"{self._base}/v2/users/{user_openid}/messages"
        body: dict[str, Any] = {"content": self._truncate(text), "msg_type": 0}
        if msg_id:
            body["msg_id"] = msg_id
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, headers=self._api_headers(token), json=body)
            if r.status_code >= 400:
                print(f"❌ [QQ] C2C 发送失败: {r.status_code} {r.text}")

    async def _send_group(self, group_openid: str, text: str, msg_id: Optional[str]) -> None:
        token = await self._token_cache.get()
        url = f"{self._base}/v2/groups/{group_openid}/messages"
        body: dict[str, Any] = {"content": self._truncate(text), "msg_type": 0}
        if msg_id:
            body["msg_id"] = msg_id
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, headers=self._api_headers(token), json=body)
            if r.status_code >= 400:
                print(f"❌ [QQ] 群聊发送失败: {r.status_code} {r.text}")

    async def _send_channel(self, channel_id: str, text: str, msg_id: Optional[str]) -> None:
        token = await self._token_cache.get()
        url = f"{self._base}/channels/{channel_id}/messages"
        body: dict[str, Any] = {"content": self._truncate(text)}
        if msg_id:
            body["msg_id"] = msg_id
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, headers=self._api_headers(token), json=body)
            if r.status_code >= 400:
                print(f"❌ [QQ] 频道发送失败: {r.status_code} {r.text}")

    @staticmethod
    def _truncate(text: str, max_len: int = 3800) -> str:
        if len(text) <= max_len:
            return text
        return text[: max_len - 20] + "\n...(已截断)"
