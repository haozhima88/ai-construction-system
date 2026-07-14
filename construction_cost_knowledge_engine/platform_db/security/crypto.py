from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class SecurityConfigurationError(RuntimeError):
    pass


PASSWORD_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=19_456,
    parallelism=1,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)
DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))


def normalize_username(value: str) -> str:
    return value.strip().casefold()


def validate_password(value: str) -> None:
    if len(value) < 12:
        raise ValueError("Password must contain at least 12 characters")
    if len(value) > 1024:
        raise ValueError("Password is too long")


def hash_password(value: str) -> str:
    validate_password(value)
    return PASSWORD_HASHER.hash(value)


def verify_password(password_hash: str | None, candidate: str) -> bool:
    target = password_hash or DUMMY_PASSWORD_HASH
    try:
        return bool(PASSWORD_HASHER.verify(target, candidate)) if password_hash else False
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def _secret_bytes(secret: str) -> bytes:
    if len(secret) < 32 or secret.startswith("replace_with_"):
        raise SecurityConfigurationError("PLATFORM_SESSION_HASH_SECRET must be at least 32 non-placeholder characters")
    return secret.encode("utf-8")


def new_session_token() -> str:
    return secrets.token_urlsafe(48)


def token_hash(raw_token: str, secret: str, purpose: str = "session") -> str:
    return hmac.new(_secret_bytes(secret), f"{purpose}:{raw_token}".encode("utf-8"), hashlib.sha256).hexdigest()


def derive_csrf_token(raw_session_token: str, secret: str) -> str:
    digest = hmac.new(_secret_bytes(secret), f"csrf-token:{raw_session_token}".encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
