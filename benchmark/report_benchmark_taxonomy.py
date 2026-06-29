from __future__ import annotations

from typing import Any


def failure_taxonomy_markdown(summary: dict[str, Any]) -> list[str]:
    rows = _rows(summary, "failure_taxonomy_counts")
    if not rows:
        return []
    lines = [
        "| Dataset | Failure Taxonomy | Unit | Count |",
        "| --- | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('dataset_name')} | "
            f"{row.get('failure_taxonomy')} | "
            f"{row.get('unit')} | "
            f"{row.get('count')} |"
        )
    return lines


def failure_taxonomy_by_route_markdown(summary: dict[str, Any]) -> list[str]:
    rows = _rows(summary, "failure_taxonomy_by_route")
    if not rows:
        return []
    lines = [
        "| Dataset | Route | Routing Taxonomy | Failure Taxonomy | Unit | Count |",
        "| --- | --- | --- | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('dataset_name')} | "
            f"{row.get('route')} | "
            f"{row.get('routing_taxonomy')} | "
            f"{row.get('failure_taxonomy')} | "
            f"{row.get('unit')} | "
            f"{row.get('count')} |"
        )
    return lines


def routing_taxonomy_markdown(summary: dict[str, Any]) -> list[str]:
    rows = _rows(summary, "routing_taxonomy_counts")
    if not rows:
        return []
    lines = [
        "| Dataset | Routing Taxonomy | Count |",
        "| --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('dataset_name')} | "
            f"{row.get('routing_taxonomy')} | "
            f"{row.get('count')} |"
        )
    return lines


def _rows(summary: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = summary.get(key) or []
    return [dict(row) for row in rows if isinstance(row, dict)]
