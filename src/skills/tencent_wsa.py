"""腾讯云 WSA 联网搜索 API。
文档: https://cloud.tencent.com/document/api/1806/121811
"""
from __future__ import annotations

import json
import logging
from typing import Any

from src.core.config import settings

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    if not settings.get("tencent_wsa.enabled"):
        return False
    sid = (settings.get("tencent_wsa.secret_id") or "").strip()
    sk = (settings.get("tencent_wsa.secret_key") or "").strip()
    return bool(sid and sk)


def search_sync(query: str, max_results: int = 10) -> list[dict[str, str]]:
    """同步调用腾讯云 WSA SearchPro。"""
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
        logger.warning("tencentcloud-sdk-python not installed")
        return []

    endpoint = (settings.get("tencent_wsa.endpoint") or "").strip() or "wsa.tencentcloudapi.com"
    region = str(settings.get("tencent_wsa.region") or "").strip()
    mode = settings.get("tencent_wsa.mode", 0)
    timeout = settings.get("tencent_wsa.timeout_seconds", 30)

    try:
        mode = int(mode)
        timeout = int(timeout)
    except (TypeError, ValueError):
        mode = 0
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
        logger.info("WSA SearchPro failed: %s", e)
        return []

    results: list[dict[str, str]] = []
    for page in (resp.Pages or [])[:max_results]:
        if not isinstance(page, str):
            continue
        try:
            obj: dict[str, Any] = json.loads(page)
        except json.JSONDecodeError:
            continue
        title = (obj.get("title") or "").strip()
        url = (obj.get("url") or "").strip()
        snippet = (obj.get("passage") or obj.get("content") or "").strip()
        if title or snippet:
            results.append({"title": title, "url": url, "snippet": snippet})

    return results
