from __future__ import annotations

import os
import sys
from pathlib import Path


def _find_bundled_llama_index_nltk_cache() -> Path | None:
    for entry in sys.path:
        if not entry:
            continue
        candidate = (
            Path(entry).resolve() / "llama_index" / "core" / "_static" / "nltk_cache"
        )
        if candidate.is_dir():
            return candidate
    return None


def ensure_llama_index_nltk_cache() -> None:
    cache_dir = _find_bundled_llama_index_nltk_cache()
    if cache_dir is not None:
        (cache_dir / "tokenizers" / "punkt").mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("NLTK_DATA", str(cache_dir))


def ensure_tiktoken_cache() -> None:
    for entry in sys.path:
        if not entry:
            continue
        cache_dir = Path(entry).resolve() / "tiktoken_cache"
        if cache_dir.is_dir():
            os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(cache_dir))
            return


__all__ = ["ensure_llama_index_nltk_cache", "ensure_tiktoken_cache"]
