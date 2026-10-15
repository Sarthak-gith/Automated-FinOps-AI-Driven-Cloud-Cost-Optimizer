"""Small standard-library signed session tokens for the local demo."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

TOKEN_TTL_SECONDS = 60 * 60 * 8


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return base64.urlsafe_b64encode(salt + derived).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        raw = base64.urlsafe_b64decode(stored.encode())
        salt, expected = raw[:16], raw[16:]
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _secret() -> bytes:
    return os.getenv("APP_SECRET_KEY", "local-demo-secret-change-before-sharing").encode()


def issue_token(user_id: int) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({
        "sub": user_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }, separators=(",", ":")).encode()).rstrip(b"=")
    signature = hmac.new(_secret(), payload, hashlib.sha256).digest()
    return payload.decode() + "." + base64.urlsafe_b64encode(signature).decode().rstrip("=")


def read_token(token: str) -> int | None:
    try:
        payload, signature = token.encode().split(b".", 1)
        expected = hmac.new(_secret(), payload, hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(signature + b"=" * (-len(signature) % 4))
        if not hmac.compare_digest(expected, supplied):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload + b"=" * (-len(payload) % 4)))
        if int(data["exp"]) <= int(time.time()):
            return None
        return int(data["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
