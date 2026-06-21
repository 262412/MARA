from __future__ import annotations

BENCHMARK_ANSWER_MODES = ("scoring_adapter_v1", "product")


def normalize_benchmark_answer_mode(mode: str | None) -> str:
    value = str(mode or "scoring_adapter_v1").strip().lower()
    if value not in BENCHMARK_ANSWER_MODES:
        choices = "', '".join(BENCHMARK_ANSWER_MODES)
        raise ValueError(f"benchmark_answer_mode must be one of '{choices}'.")
    return value
