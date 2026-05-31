from __future__ import annotations

from typing import Any


def _empty_cache_stats() -> dict[str, int]:
    return {"hits": 0, "misses": 0, "writes": 0}


def _sum_cache_stats(stats: list[dict[str, int]]) -> dict[str, int]:
    total = _empty_cache_stats()
    for item in stats:
        for key in total:
            total[key] += int(item.get(key, 0) or 0)
    return total


def _parsed_indexes_cache(parsed_indexes: list[Any]) -> dict[str, dict[str, int]]:
    return {
        "parse": _sum_cache_stats(
            [
                dict(getattr(item, "parse_cache_stats", {}) or {})
                for item in parsed_indexes
            ]
        ),
        "embedding": _sum_cache_stats(
            [
                dict(getattr(item, "embedding_cache_stats", {}) or {})
                for item in parsed_indexes
            ]
        ),
    }


def _performance_from_timings(
    timings: dict[str, float], parsed_indexes: list[Any]
) -> dict[str, Any]:
    return {
        **timings,
        "total_seconds": round(sum(float(value) for value in timings.values()), 4),
        "num_documents": len(parsed_indexes),
        "num_chunks": sum(
            len(getattr(item, "index_documents", []) or []) for item in parsed_indexes
        ),
    }
