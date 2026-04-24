"""Small, dependency-free cache primitives for performance-sensitive stages."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


_HASH_CHUNK_SIZE = 1024 * 1024

__all__ = [
    "CacheStats",
    "JsonDiskCache",
    "content_hash",
    "file_hash",
    "stable_cache_key",
]


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    writes: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "writes": self.writes,
        }


def file_hash(path: str | os.PathLike[str]) -> str:
    """Return a SHA-256 hash for the bytes currently stored at path."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(_HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_hash(value: Any) -> str:
    """Return a stable SHA-256 hash for supported JSON-like payloads."""
    payload = _stable_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stable_cache_key(namespace: str, payload: Any) -> str:
    """Return a stable key scoped by namespace and derived from payload."""
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("namespace must be a non-empty string")
    digest = content_hash({"namespace": namespace, "payload": payload})
    return f"{_safe_name(namespace)}-{digest}"


class JsonDiskCache:
    """A namespaced JSON cache stored as one atomic file per key."""

    def __init__(self, cache_dir: str | os.PathLike[str], namespace: str):
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("namespace must be a non-empty string")
        self.namespace = namespace
        self.cache_dir = Path(cache_dir) / _safe_name(namespace)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.stats = CacheStats()

    def get(self, key: str) -> Any | None:
        found, value = self._read(key)
        return value if found else None

    def get_with_status(self, key: str) -> tuple[bool, Any | None]:
        return self._read(key)

    def set(self, key: str, value: Any) -> None:
        encoded = _json_dumps_cache_value(value)
        target = self._path_for_key(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_name = ""

        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{target.stem}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_name = temp_file.name
                temp_file.write(encoded)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_name, target)
        finally:
            if temp_name:
                temp_path = Path(temp_name)
                if temp_path.exists():
                    temp_path.unlink()

        self.stats.writes += 1

    def get_or_compute(self, key: str, compute: Callable[[], Any]) -> Any:
        found, cached = self._read(key)
        if found:
            return cached

        value = compute()
        self.set(key, value)
        return value

    def _read(self, key: str) -> tuple[bool, Any | None]:
        path = self._path_for_key(key)
        if not path.exists():
            self.stats.misses += 1
            return False, None

        with path.open("r", encoding="utf-8") as file:
            value = json.load(file)
        self.stats.hits += 1
        return True, value

    def _path_for_key(self, key: str) -> Path:
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty string")
        safe_key = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{safe_key}.json"


def _stable_json(value: Any) -> str:
    normalized = _normalize_payload(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _normalize_payload(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return {"__cache_type__": "bytes", "hex": value.hex()}
    if isinstance(value, os.PathLike):
        return {"__cache_type__": "path", "value": os.fspath(value)}
    if isinstance(value, tuple):
        return {
            "__cache_type__": "tuple",
            "items": [_normalize_payload(item) for item in value],
        }
    if isinstance(value, list):
        return [_normalize_payload(item) for item in value]
    if isinstance(value, dict):
        return {
            "__cache_type__": "dict",
            "items": [
                [_normalize_payload(key), _normalize_payload(item)]
                for key, item in sorted(
                    value.items(),
                    key=lambda pair: _stable_json(pair[0]),
                )
            ],
        }

    raise TypeError(f"Payload value of type {type(value).__name__!r} is not supported")


def _json_dumps_cache_value(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise TypeError("Cache value must be JSON serializable") from exc


def _safe_name(value: str) -> str:
    safe = "".join(
        char if char.isalnum() or char in ("-", "_", ".") else "_" for char in value
    ).strip("._")
    if not safe:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    return safe
