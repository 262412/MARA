"""Password hashing and one-time legacy hash migration."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re

import bcrypt

BCRYPT_ROUNDS = 12
MARA_BCRYPT_SHA256_PREFIX = "$mara-bcrypt-sha256$"
_DUMMY_BCRYPT_HASH = b"$2b$12$RwhUy721./dNELW47maHVeTbdjFVSiiZZLHJ1XGD5gqvLWMjafAt."
_BCRYPT_HASH_PATTERN = re.compile(
    r"\$2[aby]\$12\$[./A-Za-z0-9]{21}[.Oeu]" r"[./A-Za-z0-9]{30}[.CGKOSWaeimquy26]\Z"
)
_LEGACY_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")
PASSWORD_SPECIAL_CHARACTERS = "^$*.[]{}()?-\"!@#%&/\\,><':;|_~+="


def validate_password(password: str, confirmation: str) -> str:
    """Return the existing MARA password-policy errors, if any."""
    errors = []
    if password != confirmation:
        errors.append("Password does not match")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    if not any(character.isupper() for character in password):
        errors.append("Password must contain at least one uppercase letter")
    if not any(character.islower() for character in password):
        errors.append("Password must contain at least one lowercase letter")
    if not any(character.isdigit() for character in password):
        errors.append("Password must contain at least one digit")
    if not any(character in PASSWORD_SPECIAL_CHARACTERS for character in password):
        errors.append(
            "Password must contain at least one special character from the "
            f"following: {PASSWORD_SPECIAL_CHARACTERS}"
        )
    return "; ".join(errors)


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


def _reject_with_dummy_bcrypt_check(
    password_input: bytes,
) -> tuple[bool, str | None]:
    bcrypt.checkpw(password_input, _DUMMY_BCRYPT_HASH)
    return False, None


def verify_password(
    password: str,
    stored_hash: str | None,
) -> tuple[bool, str | None]:
    """Verify a password and return an upgraded hash for legacy SHA-256 rows."""
    password_input = _bcrypt_password_input(password)
    if not isinstance(stored_hash, str):
        return _reject_with_dummy_bcrypt_check(password_input)

    if _LEGACY_SHA256_PATTERN.fullmatch(stored_hash):
        candidate_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(candidate_hash, stored_hash.lower()):
            return _reject_with_dummy_bcrypt_check(password_input)
        return True, hash_password(password)

    if not stored_hash.startswith(MARA_BCRYPT_SHA256_PREFIX):
        return _reject_with_dummy_bcrypt_check(password_input)

    bcrypt_hash = stored_hash[len(MARA_BCRYPT_SHA256_PREFIX) :]
    if not _BCRYPT_HASH_PATTERN.fullmatch(bcrypt_hash):
        return _reject_with_dummy_bcrypt_check(password_input)

    try:
        verified = bcrypt.checkpw(
            password_input,
            bcrypt_hash.encode("ascii"),
        )
    except (UnicodeError, ValueError):
        return _reject_with_dummy_bcrypt_check(password_input)

    return verified, None
