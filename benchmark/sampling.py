from __future__ import annotations

import random
from typing import Any, Sequence


def select_examples(
    examples: Sequence[Any],
    *,
    limit: int | None = None,
    sample_seed: int | None = None,
    shard_index: int | None = None,
    num_shards: int | None = None,
) -> list[Any]:
    selected = list(examples)
    if sample_seed is not None:
        random.Random(sample_seed).shuffle(selected)
    if num_shards is not None:
        selected = _shard_examples(
            selected,
            shard_index=0 if shard_index is None else shard_index,
            num_shards=num_shards,
        )
    if limit is not None:
        selected = selected[:limit]
    return selected


def select_examples_for_config(examples: Sequence[Any], config: Any) -> list[Any]:
    return select_examples(
        examples,
        limit=config.limit,
        sample_seed=config.sample_seed,
        shard_index=config.shard_index,
        num_shards=config.num_shards,
    )


def selection_summary(config: Any, total_examples: int) -> dict[str, Any]:
    return {
        "num_manifest_examples": total_examples,
        "selection": {
            "limit": config.limit,
            "sample_seed": config.sample_seed,
            "shard_index": config.shard_index,
            "num_shards": config.num_shards,
        },
    }


def validate_sampling_options(
    *,
    limit: int | None,
    shard_index: int | None,
    num_shards: int | None,
) -> None:
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative.")
    if num_shards is None:
        if shard_index is not None:
            raise ValueError("shard_index requires num_shards.")
        return
    if num_shards <= 0:
        raise ValueError("num_shards must be greater than zero.")
    if shard_index is None:
        return
    if shard_index < 0 or shard_index >= num_shards:
        raise ValueError("shard_index must be between 0 and num_shards - 1.")


def _shard_examples(
    examples: list[Any],
    *,
    shard_index: int,
    num_shards: int,
) -> list[Any]:
    validate_sampling_options(
        limit=None,
        shard_index=shard_index,
        num_shards=num_shards,
    )
    return [
        example
        for index, example in enumerate(examples)
        if index % num_shards == shard_index
    ]
