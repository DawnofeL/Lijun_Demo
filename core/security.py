"""密码哈希与 token 签发校验。只用标准库，不引 JWT。

token 格式：base64(user_id.expires_at).signature
签名是 hmac-sha256，校验时先验签再验过期。
"""

import base64
import hashlib
import hmac
import time

import config

_SALT = "starcare-demo"


def hash_password(password: str) -> str:
    return hashlib.sha256((_SALT + password).encode("utf-8")).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_password(password), hashed)


def _sign(payload: str) -> str:
    mac = hmac.new(config.SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256)
    return base64.urlsafe_b64encode(mac.digest()).decode("ascii").rstrip("=")


def issue_token(user_id: int) -> str:
    expires_at = int(time.time()) + config.TOKEN_TTL_HOURS * 3600
    payload = f"{user_id}.{expires_at}"
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{encoded}.{_sign(payload)}"


def read_token(token: str) -> int | None:
    """回传 user_id，无效或过期回传 None。"""
    try:
        encoded, signature = token.rsplit(".", 1)
        padding = "=" * (-len(encoded) % 4)
        payload = base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        user_id_text, expires_text = payload.split(".")
    except (ValueError, UnicodeDecodeError, base64.binascii.Error):
        return None

    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    if int(expires_text) < int(time.time()):
        return None
    return int(user_id_text)
