"""
腾讯云联网搜索 API（WSA）SearchPro。
文档：https://cloud.tencent.com/document/api/1806/121811
接入域名示例：wsa.tencentcloudapi.com 或 wsa.ap-guangzhou.tencentcloudapi.com
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.core.config import settings

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    if not settings.get("tencent_wsa.enabled", False):
        return False
    sid = (settings.get("tencent_wsa.secret_id") or "").strip()
    sk = (settings.get("tencent_wsa.secret_key") or "").strip()
    return bool(sid and sk)


def search_sync(query: str, max_results: int = 10) -> list[dict[str, str]]:
    q = (query or "").strip()
    if not q:
        return []

    sid = (settings.get("tencent_wsa.secret_id") or "").strip()
    sk = (settings.get("tencent_wsa.secret_key") or "").strip()
    if not sid or not sk:
        return []

    try:
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.wsa.v20250508 import wsa_client, models
    except ImportError:
        logger.warning("未安装 tencentcloud-sdk-python，无法调用 WSA")
        return []

    endpoint = (settings.get("tencent_wsa.endpoint") or "").strip() or "wsa.tencentcloudapi.com"
    region = settings.get("tencent_wsa.region")
    if region is None:
        region = ""
    region = str(region).strip()

    mode = settings.get("tencent_wsa.mode", 0)
    try:
        mode = int(mode)
    except (TypeError, ValueError):
        mode = 0

    timeout = settings.get("tencent_wsa.timeout_seconds", 30)
    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        timeout = 30

    http_profile = HttpProfile(endpoint=endpoint, reqTimeout=timeout)
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile

    cred = credential.Credential(sid, sk)
    client = wsa_client.WsaClient(cred, region, client_profile)

    req = models.SearchProRequest()
    req.Query = q
    req.Mode = mode

    try:
        resp = client.SearchPro(req)
    except Exception as e:
        logger.info("腾讯云 WSA SearchPro 失败: %s", e)
        return []

    out: list[dict[str, str]] = []
    pages = resp.Pages or []
    for raw in pages[: max(1, max_results)]:
        if not isinstance(raw, str):
            continue
        try:
            obj: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            continue
        title = (obj.get("title") or "").strip()
        url = (obj.get("url") or "").strip()
        body = (obj.get("passage") or obj.get("content") or "").strip()
        if not (title or body):
            continue
        out.append({"title": title, "url": url, "snippet": body})

    if (resp.Msg or "").strip():
        logger.debug("WSA Msg: %s", resp.Msg)

    return out
