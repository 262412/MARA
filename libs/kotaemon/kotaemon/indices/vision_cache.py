from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

from .performance_cache import JsonDiskCache, content_hash, stable_cache_key


@dataclass
class CachedModelResult:
    value: Any
    stats: dict[str, int]
    cache_hit: bool
    cache_key: str | None = None


def cached_model_result(
    *,
    cache_dir: str | os.PathLike[str] | None,
    namespace: str,
    payload: Any,
    model_name: str,
    compute: Callable[[], Any],
) -> CachedModelResult:
    """Cache an OCR/VLM/model result by input payload hash and model name."""

    if not cache_dir:
        return CachedModelResult(
            value=compute(),
            stats={"hits": 0, "misses": 0, "writes": 0},
            cache_hit=False,
        )

    cache = JsonDiskCache(cache_dir, namespace)
    key = stable_cache_key(
        namespace,
        {
            "element_image_hash": content_hash(payload),
            "model_name": model_name,
        },
    )
    found, cached = cache.get_with_status(key)
    if found:
        return CachedModelResult(
            value=cached,
            stats=cache.stats.to_dict(),
            cache_hit=True,
            cache_key=key,
        )

    value = compute()
    cache.set(key, value)
    return CachedModelResult(
        value=value,
        stats=cache.stats.to_dict(),
        cache_hit=False,
        cache_key=key,
    )
