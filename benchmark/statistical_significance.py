from __future__ import annotations

import random
from collections import defaultdict
from typing import Any


def paired_route_delta_rows(
    records: list[dict[str, Any]],
    *,
    baseline_route: str,
    candidate_route: str,
    metric: str,
) -> list[dict[str, Any]]:
    by_key = _records_by_dataset_example_route(records)
    rows: list[dict[str, Any]] = []
    for dataset, example_id in sorted({key[:2] for key in by_key}):
        baseline = by_key.get((dataset, example_id, baseline_route))
        candidate = by_key.get((dataset, example_id, candidate_route))
        if baseline is None or candidate is None:
            continue
        baseline_value = _metric_value(baseline, metric)
        candidate_value = _metric_value(candidate, metric)
        rows.append(
            {
                "dataset": dataset,
                "example_id": example_id,
                "baseline_route": baseline_route,
                "candidate_route": candidate_route,
                f"baseline_{metric}": baseline_value,
                f"candidate_{metric}": candidate_value,
                f"delta_{metric}": round(candidate_value - baseline_value, 4),
            }
        )
    return rows


def bootstrap_ci_by_dataset_route(
    records: list[dict[str, Any]],
    *,
    baseline_route: str,
    candidate_route: str,
    metric: str,
    iterations: int = 1000,
    seed: int = 13,
) -> list[dict[str, Any]]:
    paired = paired_route_delta_rows(
        records,
        baseline_route=baseline_route,
        candidate_route=candidate_route,
        metric=metric,
    )
    by_dataset: dict[str, list[float]] = defaultdict(list)
    for row in paired:
        by_dataset[str(row["dataset"])].append(float(row[f"delta_{metric}"]))
    return [
        _bootstrap_dataset_row(
            dataset,
            deltas,
            baseline_route=baseline_route,
            candidate_route=candidate_route,
            metric=metric,
            iterations=iterations,
            seed=seed,
        )
        for dataset, deltas in sorted(by_dataset.items())
    ]


def route_win_loss_tie_rows(
    records: list[dict[str, Any]],
    *,
    baseline_route: str,
    candidate_route: str,
    metric: str,
) -> list[dict[str, Any]]:
    paired = paired_route_delta_rows(
        records,
        baseline_route=baseline_route,
        candidate_route=candidate_route,
        metric=metric,
    )
    grouped: dict[str, dict[str, int]] = defaultdict(
        lambda: {"wins": 0, "losses": 0, "ties": 0}
    )
    for row in paired:
        delta = float(row[f"delta_{metric}"])
        bucket = "ties"
        if delta > 0:
            bucket = "wins"
        elif delta < 0:
            bucket = "losses"
        grouped[str(row["dataset"])][bucket] += 1
    return [
        {
            "dataset": dataset,
            "baseline_route": baseline_route,
            "candidate_route": candidate_route,
            "wins": counts["wins"],
            "losses": counts["losses"],
            "ties": counts["ties"],
            "n": counts["wins"] + counts["losses"] + counts["ties"],
        }
        for dataset, counts in sorted(grouped.items())
    ]


def controller_oracle_regret_rows(
    records: list[dict[str, Any]],
    *,
    controller_route: str,
    metric: str,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(_dataset(record), _example_id(record))].append(record)
    rows: list[dict[str, Any]] = []
    for (dataset, example_id), items in sorted(grouped.items()):
        controller = next(
            (
                item
                for item in items
                if str(item.get("route") or "") == controller_route
            ),
            None,
        )
        fixed_routes = [
            item for item in items if str(item.get("route") or "") != controller_route
        ]
        if controller is None or not fixed_routes:
            continue
        controller_value = _metric_value(controller, metric)
        oracle = max(fixed_routes, key=lambda item: _metric_value(item, metric))
        oracle_value = _metric_value(oracle, metric)
        rows.append(
            {
                "dataset": dataset,
                "example_id": example_id,
                "controller_route": controller_route,
                f"controller_{metric}": controller_value,
                "oracle_route": str(oracle.get("route") or ""),
                f"oracle_{metric}": oracle_value,
                f"regret_{metric}": round(max(oracle_value - controller_value, 0.0), 4),
            }
        )
    return rows


def _bootstrap_dataset_row(
    dataset: str,
    deltas: list[float],
    *,
    baseline_route: str,
    candidate_route: str,
    metric: str,
    iterations: int,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    means: list[float] = []
    sample_count = len(deltas)
    for _ in range(max(iterations, 1)):
        sample = [deltas[rng.randrange(sample_count)] for _ in range(sample_count)]
        means.append(sum(sample) / sample_count)
    means.sort()
    return {
        "dataset": dataset,
        "baseline_route": baseline_route,
        "candidate_route": candidate_route,
        "n": sample_count,
        f"mean_delta_{metric}": round(sum(deltas) / sample_count, 4),
        f"ci_low_{metric}": round(_percentile(means, 0.025), 4),
        f"ci_high_{metric}": round(_percentile(means, 0.975), 4),
    }


def _records_by_dataset_example_route(
    records: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {
        (_dataset(record), _example_id(record), str(record.get("route") or "")): record
        for record in records
        if _dataset(record) and _example_id(record) and str(record.get("route") or "")
    }


def _dataset(record: dict[str, Any]) -> str:
    return str(record.get("dataset") or record.get("dataset_name") or "").strip()


def _example_id(record: dict[str, Any]) -> str:
    return str(record.get("example_id") or record.get("question_id") or "").strip()


def _metric_value(record: dict[str, Any], metric: str) -> float:
    try:
        return round(float(record.get(metric) or 0.0), 4)
    except (TypeError, ValueError):
        return 0.0


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    index = min(max(round((len(values) - 1) * fraction), 0), len(values) - 1)
    return values[index]
