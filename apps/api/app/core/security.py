"""JWT + password primitives. Access 15 min / refresh 7 d, httpOnly cookies set by routes."""
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def _token(sub: str, kind: str, minutes: int, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": sub,
        "typ": kind,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(sub: str, role: str, merchant_id: str) -> str:
    return _token(sub, "access", settings.access_token_minutes, {"role": role, "mid": merchant_id})


def create_refresh_token(sub: str) -> str:
    return _token(sub, "refresh", settings.refresh_token_days * 24 * 60)


def decode_token(token: str, expected_typ: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("typ") != expected_typ:
            return None
        return payload
    except jwt.PyJWTError:
        return None


def create_portal_token(sub: str) -> str:
    return _token(sub, "portal", settings.refresh_token_days * 24 * 60)
