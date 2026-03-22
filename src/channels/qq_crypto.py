"""QQ 开放平台 Webhook：Ed25519 验签与回调地址验证（op=13）签名。"""

from __future__ import annotations

import binascii
from typing import Mapping

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey


def expand_secret_to_seed(bot_secret: str) -> bytes:
    b = bot_secret.encode("utf-8")
    seed = b
    while len(seed) < 32:
        seed = seed + seed
    return seed[:32]


def signing_key_from_bot_secret(bot_secret: str) -> SigningKey:
    return SigningKey(expand_secret_to_seed(bot_secret))


def sign_validation_response(bot_secret: str, event_ts: str, plain_token: str) -> str:
    sk = signing_key_from_bot_secret(bot_secret)
    msg = event_ts.encode("utf-8") + plain_token.encode("utf-8")
    return sk.sign(msg).signature.hex()


def verify_webhook_signature(
    bot_secret: str,
    headers: Mapping[str, str],
    raw_body: bytes,
) -> bool:
    sig_hex = headers.get("x-signature-ed25519") or headers.get("X-Signature-Ed25519") or ""
    ts = headers.get("x-signature-timestamp") or headers.get("X-Signature-Timestamp") or ""
    if not sig_hex or not ts:
        return False
    try:
        sig = binascii.unhexlify(sig_hex.strip())
    except binascii.Error:
        return False
    if len(sig) != 64:
        return False
    msg = ts.encode("utf-8") + raw_body
    vk = signing_key_from_bot_secret(bot_secret).verify_key
    try:
        vk.verify(msg, sig)
        return True
    except BadSignatureError:
        return False


def normalize_headers(headers: Mapping[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in headers.items():
        if v is None:
            continue
        out[str(k).lower()] = str(v)
    return out
