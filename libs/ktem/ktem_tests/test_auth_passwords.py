import base64
import hashlib
import importlib
import importlib.util

import bcrypt
import pytest

MARA_BCRYPT_SHA256_PREFIX = "$mara-bcrypt-sha256$"


def _passwords_module():
    package_spec = importlib.util.find_spec("ktem.auth")
    assert package_spec is not None, "ktem.auth must provide shared auth primitives"

    module_spec = importlib.util.find_spec("ktem.auth.passwords")
    assert (
        module_spec is not None
    ), "ktem.auth.passwords must centralize password hashing"
    return importlib.import_module("ktem.auth.passwords")


def test_hash_password_uses_versioned_bcrypt_sha256_with_cost_12():
    passwords = _passwords_module()

    password_hash = passwords.hash_password("CorrectHorse7!")

    assert password_hash.startswith(f"{MARA_BCRYPT_SHA256_PREFIX}$2b$12$")
    assert password_hash != passwords.hash_password("CorrectHorse7!")


def test_verify_password_accepts_bcrypt_sha256_without_upgrade():
    passwords = _passwords_module()
    password_hash = passwords.hash_password("CorrectHorse7!")

    verified, upgraded_hash = passwords.verify_password("CorrectHorse7!", password_hash)

    assert verified is True
    assert upgraded_hash is None


def test_bcrypt_sha256_supports_unicode_passwords_longer_than_72_bytes():
    passwords = _passwords_module()
    password = "密碼🔐" * 30
    assert len(password.encode("utf-8")) > 72

    password_hash = passwords.hash_password(password)

    assert passwords.verify_password(password, password_hash) == (True, None)


def test_verify_password_rejects_wrong_bcrypt_password():
    passwords = _passwords_module()
    password_hash = passwords.hash_password("CorrectHorse7!")

    verified, upgraded_hash = passwords.verify_password("WrongHorse7!", password_hash)

    assert verified is False
    assert upgraded_hash is None


def test_verify_password_upgrades_legacy_sha256_with_constant_time_compare(
    monkeypatch,
):
    passwords = _passwords_module()
    legacy_hash = hashlib.sha256(b"CorrectHorse7!").hexdigest().upper()
    compare_calls = []
    original_compare_digest = passwords.hmac.compare_digest

    def _compare_digest(left, right):
        compare_calls.append((left, right))
        return original_compare_digest(left, right)

    monkeypatch.setattr(passwords.hmac, "compare_digest", _compare_digest)

    verified, upgraded_hash = passwords.verify_password("CorrectHorse7!", legacy_hash)

    assert verified is True
    assert upgraded_hash is not None
    assert upgraded_hash.startswith(f"{MARA_BCRYPT_SHA256_PREFIX}$2b$12$")
    assert compare_calls == [
        (hashlib.sha256(b"CorrectHorse7!").hexdigest(), legacy_hash.lower())
    ]


def test_verify_password_does_not_upgrade_wrong_legacy_password():
    passwords = _passwords_module()
    legacy_hash = hashlib.sha256(b"CorrectHorse7!").hexdigest()

    verified, upgraded_hash = passwords.verify_password("WrongHorse7!", legacy_hash)

    assert verified is False
    assert upgraded_hash is None


def test_verify_password_upgrades_long_legacy_sha256_password():
    passwords = _passwords_module()
    password = "密碼🔐" * 30
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

    verified, upgraded_hash = passwords.verify_password(password, legacy_hash)

    assert verified is True
    assert upgraded_hash is not None
    assert upgraded_hash.startswith(f"{MARA_BCRYPT_SHA256_PREFIX}$2b$12$")
    assert passwords.verify_password(password, upgraded_hash) == (True, None)


def test_verify_password_rejects_unprefixed_bcrypt_hash():
    passwords = _passwords_module()
    password_hash = bcrypt.hashpw(
        b"CorrectHorse7!",
        bcrypt.gensalt(rounds=12),
    ).decode("ascii")

    assert passwords.verify_password("CorrectHorse7!", password_hash) == (False, None)


def test_verify_password_rejects_prefixed_bcrypt_with_wrong_cost():
    passwords = _passwords_module()
    password_input = base64.b64encode(hashlib.sha256(b"CorrectHorse7!").digest())
    password_hash = bcrypt.hashpw(
        password_input,
        bcrypt.gensalt(rounds=4),
    ).decode("ascii")

    assert passwords.verify_password(
        "CorrectHorse7!",
        f"{MARA_BCRYPT_SHA256_PREFIX}{password_hash}",
    ) == (False, None)


@pytest.mark.parametrize(
    "stored_hash",
    [
        "",
        "not-a-password-hash",
        "g" * 64,
        "$2b$12$malformed",
        f"{MARA_BCRYPT_SHA256_PREFIX}$2b$12$malformed",
        None,
    ],
)
def test_verify_password_rejects_malformed_hashes_cleanly(stored_hash):
    passwords = _passwords_module()

    assert passwords.verify_password("CorrectHorse7!", stored_hash) == (False, None)
