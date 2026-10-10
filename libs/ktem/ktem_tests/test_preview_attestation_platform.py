"""Preserve fd permission failures and cleanup at the attestation boundary."""

import os
import stat
import sys
from types import ModuleType

import pytest
from ktem.preview import cache_attestation
from ktem.preview.errors import PreviewConversionError


class _FakeWindowsDPAPIError(Exception):
    pass


def _install_fake_dpapi(monkeypatch, *, protect, unprotect):
    pywintypes = ModuleType("pywintypes")
    setattr(pywintypes, "error", _FakeWindowsDPAPIError)
    win32crypt = ModuleType("win32crypt")
    setattr(win32crypt, "CryptProtectData", protect)
    setattr(win32crypt, "CryptUnprotectData", unprotect)
    monkeypatch.setitem(sys.modules, "pywintypes", pywintypes)
    monkeypatch.setitem(sys.modules, "win32crypt", win32crypt)


def test_mocked_windows_key_is_encrypted_and_tampering_fails_closed(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(cache_attestation, "_WINDOWS", True)
    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "app-data"))
    fake_key = b"k" * 32
    ciphertext_prefix = b"encrypted:"

    def protect(data, *_args):
        return ciphertext_prefix + bytes(value ^ 0xFF for value in data)

    def unprotect(data, *_args):
        if data.startswith(ciphertext_prefix):
            encrypted = data[len(ciphertext_prefix) :]
            return "MARA preview cache", bytes(value ^ 0xFF for value in encrypted)
        raise _FakeWindowsDPAPIError("invalid encrypted key")

    _install_fake_dpapi(monkeypatch, protect=protect, unprotect=unprotect)
    monkeypatch.setattr(
        cache_attestation.secrets, "token_bytes", lambda _size: fake_key
    )
    store = cache_attestation.CacheAttestationStore(tmp_path / "cache")
    source = tmp_path / "source.docx"

    cache_attestation._create_key_atomically(store.key_path, source)

    assert store.key_path.read_bytes() == ciphertext_prefix + bytes(
        value ^ 0xFF for value in fake_key
    )
    assert fake_key not in store.key_path.read_bytes()
    assert store._key(source) == fake_key
    identity = store.key_path.stat()
    cache_attestation._create_key_atomically(store.key_path, source)
    assert store.key_path.stat().st_ino == identity.st_ino

    store.key_path.write_bytes(b"invalid encrypted key")
    with pytest.raises(PreviewConversionError, match="Windows key protection"):
        store._key(source)


def test_mocked_windows_encryption_failure_leaves_no_key_or_temporary(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(cache_attestation, "_WINDOWS", True)
    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "app-data"))

    def denied(*_args):
        raise _FakeWindowsDPAPIError("owned permission denial")

    _install_fake_dpapi(monkeypatch, protect=denied, unprotect=lambda *_args: None)
    store = cache_attestation.CacheAttestationStore(tmp_path / "cache")

    with pytest.raises(PreviewConversionError, match="Windows key protection"):
        cache_attestation._create_key_atomically(store.key_path, tmp_path / "source")

    assert list(store.key_path.parent.iterdir()) == []


@pytest.mark.parametrize("operation", ["key", "manifest"])
@pytest.mark.parametrize("missing", [True, False])
def test_permission_capability_failure_never_publishes_or_leaks_descriptor(
    monkeypatch, tmp_path, operation, missing
):
    monkeypatch.setattr(cache_attestation, "_WINDOWS", False)
    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "app-data"))
    cache = tmp_path / "cache"
    cache.mkdir()
    store = cache_attestation.CacheAttestationStore(cache)
    source = tmp_path / "source.docx"
    source.write_bytes(b"owned fixture")
    target = cache / "attestation.json"
    target.write_bytes(b"previous attestation")
    prepared = cache_attestation.PreparedAttestation(b"replacement", target)
    descriptors = []
    original = cache_attestation.tempfile.mkstemp

    def tracked_mkstemp(*args, **kwargs):
        fd, name = original(*args, **kwargs)
        descriptors.append(fd)
        return fd, name

    failure = PermissionError("owned permission denial")

    def denied(_descriptor, _mode):
        raise failure

    monkeypatch.setattr(cache_attestation.tempfile, "mkstemp", tracked_mkstemp)
    if missing:
        monkeypatch.delattr(os, "fchmod", raising=False)
    else:
        monkeypatch.setattr(os, "fchmod", denied, raising=False)
    error = AttributeError if missing else PreviewConversionError
    with pytest.raises(
        error, match="fchmod" if missing else "permission denial"
    ) as caught:
        if operation == "key":
            cache_attestation._create_key_atomically(store.key_path, source)
        else:
            store.publish(prepared, source)
    if not missing:
        assert caught.value.__cause__ is failure
    assert not store.key_path.exists()
    assert target.read_bytes() == b"previous attestation"
    assert list(cache.iterdir()) == [target]
    assert list(store.key_path.parent.iterdir()) == []
    assert len(descriptors) == 1
    with pytest.raises(OSError):
        os.fstat(descriptors[0])


@pytest.mark.skipif(not hasattr(os, "fchmod"), reason="requires native fd permissions")
def test_native_key_and_manifest_permissions_and_existing_key_identity(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "app-data"))
    cache = tmp_path / "cache"
    cache.mkdir()
    source = tmp_path / "source.docx"
    source.write_bytes(b"owned fixture")
    store = cache_attestation.CacheAttestationStore(cache)
    cache_attestation._create_key_atomically(store.key_path, source)
    identity = store.key_path.stat()
    assert stat.S_IMODE(identity.st_mode) == 0o600
    assert identity.st_size == 32
    cache_attestation._create_key_atomically(store.key_path, source)
    current = store.key_path.stat()
    assert (current.st_ino, current.st_mtime_ns, current.st_size) == (
        identity.st_ino,
        identity.st_mtime_ns,
        identity.st_size,
    )
    target = cache / "attestation.json"
    store.publish(
        cache_attestation.PreparedAttestation(b"owned manifest", target), source
    )
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert target.read_bytes() == b"owned manifest"
    assert list(cache.iterdir()) == [target]
    assert list(store.key_path.parent.iterdir()) == [store.key_path]


@pytest.mark.skipif(os.name != "nt", reason="requires Windows DPAPI")
def test_windows_key_is_encrypted_and_tampering_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "app-data"))
    fake_key = b"k" * 32
    monkeypatch.setattr(
        cache_attestation.secrets, "token_bytes", lambda _size: fake_key
    )
    store = cache_attestation.CacheAttestationStore(tmp_path / "cache")
    source = tmp_path / "source.docx"
    cache_attestation._create_key_atomically(store.key_path, source)
    assert fake_key not in store.key_path.read_bytes()
    assert store._key(source) == fake_key
    identity = store.key_path.stat()
    cache_attestation._create_key_atomically(store.key_path, source)
    assert store.key_path.stat().st_ino == identity.st_ino
    store.key_path.write_bytes(b"invalid encrypted key")
    with pytest.raises(PreviewConversionError, match="Windows key protection"):
        store._key(source)


@pytest.mark.skipif(os.name != "nt", reason="requires Windows DPAPI")
def test_windows_encryption_failure_leaves_no_key_or_temporary(monkeypatch, tmp_path):
    import pywintypes
    import win32crypt

    monkeypatch.setenv("KH_APP_DATA_DIR", str(tmp_path / "app-data"))
    store = cache_attestation.CacheAttestationStore(tmp_path / "cache")

    def denied(*args):
        raise pywintypes.error(5, "CryptProtectData", "owned permission denial")

    monkeypatch.setattr(win32crypt, "CryptProtectData", denied)
    with pytest.raises(PreviewConversionError, match="Windows key protection"):
        cache_attestation._create_key_atomically(store.key_path, tmp_path / "source")
    assert list(store.key_path.parent.iterdir()) == []
