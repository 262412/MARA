"""Preserve fd permission failures and cleanup at the attestation boundary."""

import os
import stat

import pytest
from ktem.preview import cache_attestation
from ktem.preview.errors import PreviewConversionError


@pytest.mark.parametrize("operation", ["key", "manifest"])
@pytest.mark.parametrize("missing", [True, False])
def test_permission_capability_failure_never_publishes_or_leaks_descriptor(
    monkeypatch, tmp_path, operation, missing
):
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
