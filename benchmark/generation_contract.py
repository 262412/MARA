from __future__ import annotations

from typing import Final

BENCHMARK_GENERATION_TEMPERATURE: Final[int] = 0
BENCHMARK_GENERATION_TOP_P: Final[int] = 1
BENCHMARK_GENERATION_SEED: Final[int] = 20260724


def benchmark_generation_config() -> dict[str, int]:
    return {
        "temperature": BENCHMARK_GENERATION_TEMPERATURE,
        "top_p": BENCHMARK_GENERATION_TOP_P,
        "seed": BENCHMARK_GENERATION_SEED,
    }


def benchmark_request_generation_config() -> dict[str, int]:
    return {
        "generation_temperature": BENCHMARK_GENERATION_TEMPERATURE,
        "generation_top_p": BENCHMARK_GENERATION_TOP_P,
        "generation_seed": BENCHMARK_GENERATION_SEED,
    }


def benchmark_generation_trace(seed: int) -> dict[str, str]:
    return {
        "generation_temperature": str(BENCHMARK_GENERATION_TEMPERATURE),
        "generation_top_p": str(BENCHMARK_GENERATION_TOP_P),
        "generation_seed": str(seed),
    }
