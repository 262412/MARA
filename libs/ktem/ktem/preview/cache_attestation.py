from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .errors import PreviewConversionError, PreviewErrorCode

_ATTESTATION_VERSION = "mara-office-preview-v1"
_KEY_BYTES = 32
_MAX_MANIFEST_BYTES = 4096


@dataclass(frozen=True)
class PreparedAttestation:
    manifest: bytes
    target: Path


class CacheAttestationStore:
    """Authenticate cached conversion artifacts with a key outside the cache."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.key_path = _key_path(cache_dir)

    def is_trusted(
        self,
        source_path: Path,
        artifact_path: Path,
        cache_key: str,
    ) -> bool:
        artifact = _regular_file_or_missing(artifact_path, source_path, "artifact")
        if artifact is None:
            return False
        manifest_path = _manifest_path(artifact)
        manifest_file = _regular_file_or_missing(
            manifest_path, source_path, "attestation"
        )
        if manifest_file is None:
            return False
        try:
            with manifest_file.open("rb") as file_obj:
                raw = file_obj.read(_MAX_MANIFEST_BYTES + 1)
            if len(raw) > _MAX_MANIFEST_BYTES:
                return False
            recorded = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False
        expected = self._manifest_record(source_path, artifact, cache_key)
        return hmac.compare_digest(
            json.dumps(recorded, sort_keys=True, separators=(",", ":")),
            json.dumps(expected, sort_keys=True, separators=(",", ":")),
        )

    def prepare(
        self,
        source_path: Path,
        candidate_path: Path,
        target_path: Path,
        cache_key: str,
    ) -> PreparedAttestation:
        candidate = _required_regular_file(candidate_path, source_path, "candidate")
        _publish_target(target_path, source_path, "artifact")
        manifest_target = _manifest_path(target_path)
        _publish_target(manifest_target, source_path, "attestation")
        record = self._manifest_record(
            source_path,
            candidate,
            cache_key,
            target_path=target_path,
        )
        return PreparedAttestation(
            manifest=(
                json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode("utf-8"),
            target=manifest_target,
        )

    def publish(self, prepared: PreparedAttestation, source_path: Path) -> None:
        descriptor, name = tempfile.mkstemp(
            prefix=f".{prepared.target.name}.",
            suffix=".tmp",
            dir=self.cache_dir,
        )
        temporary = Path(name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as file_obj:
                descriptor = -1
                file_obj.write(prepared.manifest)
                file_obj.flush()
                os.fsync(file_obj.fileno())
            _publish_target(prepared.target, source_path, "attestation")
            os.replace(temporary, prepared.target)
        except OSError as exc:
            raise _attestation_error(
                source_path, f"Unable to publish cache attestation: {exc}"
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)

    def publish_artifact(
        self,
        source_path: Path,
        candidate_path: Path,
        target_path: Path,
        cache_key: str,
    ) -> Path:
        prepared = self.prepare(source_path, candidate_path, target_path, cache_key)
        os.replace(candidate_path, target_path)
        self.publish(prepared, source_path)
        return target_path

    def _manifest_record(
        self,
        source_path: Path,
        artifact_path: Path,
        cache_key: str,
        *,
        target_path: Path | None = None,
    ) -> dict[str, str]:
        target = target_path or artifact_path
        payload = {
            "artifact_sha256": _file_digest(artifact_path),
            "cache_key": cache_key,
            "source_sha256": _file_digest(source_path),
            "target": str(target.absolute()),
            "version": _ATTESTATION_VERSION,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        payload["mac"] = hmac.new(
            self._key(source_path), encoded, hashlib.sha256
        ).hexdigest()
        return payload

    def _key(self, source_path: Path) -> bytes:
        if not self.key_path.exists():
            _create_key_atomically(self.key_path, source_path)
        key_file = _required_regular_file(self.key_path, source_path, "attestation key")
        mode = key_file.stat().st_mode
        if mode & 0o077:
            raise _attestation_error(
                source_path, "The cache attestation key must have mode 0600."
            )
        key = key_file.read_bytes()
        if len(key) != _KEY_BYTES:
            raise _attestation_error(
                source_path, "The cache attestation key is invalid."
            )
        return key


def _key_path(cache_dir: Path) -> Path:
    configured = os.environ.get("KH_APP_DATA_DIR")
    root = Path(configured).expanduser() if configured else cache_dir.parent
    root = root.resolve()
    if root == cache_dir or cache_dir in root.parents:
        root = cache_dir.parent.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root / ".mara-preview-cache.key"


def _create_key_atomically(key_path: Path, source_path: Path) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".preview-key-", dir=key_path.parent)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as file_obj:
            descriptor = -1
            file_obj.write(secrets.token_bytes(_KEY_BYTES))
            file_obj.flush()
            os.fsync(file_obj.fileno())
        try:
            os.link(temporary, key_path)
        except FileExistsError:
            pass
    except OSError as exc:
        raise _attestation_error(
            source_path, f"Unable to create cache attestation key: {exc}"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def _manifest_path(artifact_path: Path) -> Path:
    return artifact_path.with_name(f".{artifact_path.name}.attestation.json")


def _regular_file_or_missing(path: Path, source_path: Path, label: str) -> Path | None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise _attestation_error(
            source_path, f"Unable to inspect {label}: {exc}"
        ) from exc
    if stat.S_ISLNK(mode):
        raise _attestation_error(source_path, f"The cache {label} cannot be a symlink.")
    if not stat.S_ISREG(mode):
        raise _attestation_error(
            source_path, f"The cache {label} is not a regular file."
        )
    return path


def _required_regular_file(path: Path, source_path: Path, label: str) -> Path:
    file_path = _regular_file_or_missing(path, source_path, label)
    if file_path is None:
        raise _attestation_error(source_path, f"The cache {label} is missing.")
    return file_path


def _publish_target(path: Path, source_path: Path, label: str) -> None:
    _regular_file_or_missing(path, source_path, label)


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for block in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _attestation_error(source_path: Path, details: str) -> PreviewConversionError:
    return PreviewConversionError(
        PreviewErrorCode.OUTPUT_INVALID,
        stage="cache_attestation",
        source_path=source_path,
        converter="filesystem",
        details=details,
    )
