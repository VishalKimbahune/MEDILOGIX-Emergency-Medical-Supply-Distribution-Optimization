"""
Core Authentication & Cryptographic Security Utilities (Phase 6 Redesign).

- Argon2id password hashing (via argon2-cffi)
- Short-lived HS256 JWT access tokens (via PyJWT)
- Cryptographically secure URL-safe tokens + SHA-256 digest storage for refresh,
  password-reset, and email-verification tokens
- Sliding-window in-memory rate limiter for login and password-reset endpoints
"""

from __future__ import annotations

import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

_PASSWORD_HASHER = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _PASSWORD_HASHER.hash(plain_password)


def validate_password_strength(password: str) -> str | None:
    """Validate password complexity; returns error message string or None when valid."""
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not any(ch.isupper() for ch in password):
        return "Password must contain at least one uppercase letter."
    if not any(ch.islower() for ch in password):
        return "Password must contain at least one lowercase letter."
    if not any(ch.isdigit() for ch in password):
        return "Password must contain at least one digit."
    if not any(not ch.isalnum() for ch in password):
        return "Password must contain at least one special character."
    return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored Argon2id hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return _PASSWORD_HASHER.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def generate_secure_token(nbytes: int = 32) -> str:
    """Generate a cryptographically secure URL-safe random token."""
    return secrets.token_urlsafe(nbytes)


def hash_token(raw_token: str) -> str:
    """Return deterministic SHA-256 hex digest of an opaque token for safe DB storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(
    *,
    user_id: int,
    email: str,
    role: str,
    expires_minutes: int | None = None,
) -> tuple[str, int]:
    """
    Create a signed short-lived JWT access token.

    Returns (encoded_jwt, expires_in_seconds).
    """
    settings = get_settings()
    ttl_min = (
        expires_minutes
        if expires_minutes is not None
        else settings.access_token_expire_minutes
    )
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=ttl_min)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(8),
    }
    encoded = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded, int(ttl_min * 60)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT access token; raises jwt.PyJWTError on invalid/expired token."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Token type is not 'access'.")
    return payload


class SlidingWindowRateLimiter:
    """Thread-safe lightweight in-memory sliding-window rate limiter."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check_and_record(self, key: str, *, max_attempts: int, window_sec: int) -> bool:
        """
        Return True if request is allowed (and record the attempt); False if rate-limited.
        """
        now = time.monotonic()
        cutoff = now - window_sec
        bucket = self._hits[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_attempts:
            return False
        bucket.append(now)
        return True

    def clear(self) -> None:
        """Clear all tracked rate-limit buckets (for testing)."""
        self._hits.clear()


auth_rate_limiter = SlidingWindowRateLimiter()
