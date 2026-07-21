import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

from app.core.config import settings

ph = PasswordHasher()


def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False

def check_needs_rehash(hashed_password: str) -> bool:
    return ph.check_needs_rehash(hashed_password)


def _secret() -> str:
    return settings.SECRET_KEY.get_secret_value()

def _encode_token(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, _secret(), algorithm=settings.JWT_ALGORITHM)

def create_access_token(
        subject: str,
        extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "typ": "access",
        **(extra_claims or {}),
    }
    return _encode_token(payload)

def create_refresh_token(subject: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "typ": "refresh",
    }
    return _encode_token(payload)

def decode_token(
        token: str,
        expected_type: str = "access",
) -> dict[str, Any]:
    payload: dict[str, Any] = jwt.decode(
        token,
        _secret(),
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["sub", "jti", "iat", "nbf", "exp", "typ"]},
    )
    if payload.get("typ") != expected_type:
        msg = f"Expected token type '{expected_type}', got '{payload.get('typ')}'"
        raise jwt.InvalidTokenError(msg)
    return payload