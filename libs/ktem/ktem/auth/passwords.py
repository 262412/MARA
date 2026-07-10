"""Password hashing and one-time legacy hash migration."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re

import bcrypt

BCRYPT_ROUNDS = 12
MARA_BCRYPT_SHA256_PREFIX = "$mara-bcrypt-sha256$"
_BCRYPT_HASH_PATTERN = re.compile(r"\$2[aby]\$12\$[./A-Za-z0-9]{53}\Z")
_LEGACY_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")


def _bcrypt_password_input(password: str) -> bytes:
    password_digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(password_digest)


def hash_password(password: str) -> str:
    """Hash a password with the versioned bcrypt-SHA256 scheme."""
    bcrypt_hash = bcrypt.hashpw(
        _bcrypt_password_input(password),
        bcrypt.gensalt(rounds=BCRYPT_ROUNDS),
    ).decode("ascii")
    return f"{MARA_BCRYPT_SHA256_PREFIX}{bcrypt_hash}"


def verify_password(
    password: str,
    stored_hash: str | None,
) -> tuple[bool, str | None]:
    """Verify a password and return an upgraded hash for legacy SHA-256 rows."""
    if not isinstance(stored_hash, str):
        return False, None

    if _LEGACY_SHA256_PATTERN.fullmatch(stored_hash):
        candidate_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(candidate_hash, stored_hash.lower()):
            return False, None
        return True, hash_password(password)

    if not stored_hash.startswith(MARA_BCRYPT_SHA256_PREFIX):
        return False, None

    bcrypt_hash = stored_hash[len(MARA_BCRYPT_SHA256_PREFIX) :]
    if not _BCRYPT_HASH_PATTERN.fullmatch(bcrypt_hash):
        return False, None

    try:
        verified = bcrypt.checkpw(
            _bcrypt_password_input(password),
            bcrypt_hash.encode("ascii"),
        )
    except (UnicodeError, ValueError):
        return False, None

    return verified, None
