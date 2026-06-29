from __future__ import annotations

from typing import Any


def benchmark_prompt_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    policies = [
        str(item.get("benchmark_prompt_policy") or "").strip()
        for item in predictions
        if str(item.get("benchmark_prompt_policy") or "").strip()
    ]
    profiles = [
        str(item.get("benchmark_prompt_profile") or "").strip()
        for item in predictions
        if str(item.get("benchmark_prompt_profile") or "").strip()
    ]
    sources = [
        str(item.get("benchmark_prompt_source") or "").strip()
        for item in predictions
        if str(item.get("benchmark_prompt_source") or "").strip()
    ]
    no_think_values = [
        bool(item.get("benchmark_no_think"))
        for item in predictions
        if "benchmark_no_think" in item
    ]
    return {
        "benchmark_prompt_policy": _single_or_mixed(policies),
        "benchmark_prompt_profiles": _count_values(profiles),
        "benchmark_prompt_sources": _count_values(sources),
        "benchmark_no_think": _single_bool_or_mixed(no_think_values),
    }


def _single_or_mixed(values: list[str]) -> str | None:
    if not values:
        return None
    unique = sorted(set(values))
    if len(unique) == 1:
        return unique[0]
    return "mixed"


def _single_bool_or_mixed(values: list[bool]) -> bool | str | None:
    if not values:
        return None
    unique = sorted(set(values))
    if len(unique) == 1:
        return unique[0]
    return "mixed"


def _count_values(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts
