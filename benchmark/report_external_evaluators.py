from __future__ import annotations

from typing import Any


def external_evaluator_markdown(summary: dict[str, Any]) -> list[str]:
    metadata = summary.get("external_adapter_metric_metadata") or {}
    if not isinstance(metadata, dict):
        return []
    lines = []
    for adapter_name, item in metadata.items():
        if not isinstance(item, dict):
            continue
        lines.append(_external_evaluator_line(str(adapter_name), item))
    return lines


def external_evaluator_by_route_markdown(summary: dict[str, Any]) -> list[str]:
    metadata_by_route = summary.get("external_adapter_metric_metadata_by_route") or {}
    if not isinstance(metadata_by_route, dict):
        return []
    lines = []
    for route_id, metadata in metadata_by_route.items():
        if not isinstance(metadata, dict):
            continue
        for adapter_name, item in metadata.items():
            if isinstance(item, dict):
                lines.append(
                    _external_evaluator_route_line(
                        str(route_id),
                        str(adapter_name),
                        item,
                    )
                )
    return lines


def _external_evaluator_line(adapter_name: str, item: dict[str, Any]) -> str:
    status = str(item.get("status") or "not_configured")
    if status == "configured":
        backend = str(item.get("backend") or "").strip()
        paper_grade = item.get("paper_grade")
        metric_category = str(item.get("metric_category") or "external_metric")
        return (
            f"- `{adapter_name}`: configured via `{backend}`, "
            f"paper_grade=`{paper_grade}`, "
            f"metric_category=`{metric_category}`"
            f"{_paper_grade_contract_suffix(item)}"
        )
    excluded = item.get("excluded_from_summary")
    return (
        f"- `{adapter_name}`: {status}, excluded_from_summary=`{excluded}`"
        f"{_paper_grade_contract_suffix(item)}"
    )


def _external_evaluator_route_line(
    route_id: str,
    adapter_name: str,
    item: dict[str, Any],
) -> str:
    status = str(item.get("status") or "not_configured")
    if status == "configured":
        backend = str(item.get("backend") or "").strip()
        paper_grade = item.get("paper_grade")
        metric_category = str(item.get("metric_category") or "external_metric")
        return (
            f"- `{route_id}` / `{adapter_name}`: configured via `{backend}`, "
            f"paper_grade=`{paper_grade}`, "
            f"metric_category=`{metric_category}`"
            f"{_paper_grade_contract_suffix(item)}"
        )
    excluded = item.get("excluded_from_summary")
    return (
        f"- `{route_id}` / `{adapter_name}`: {status}, "
        f"excluded_from_summary=`{excluded}`"
        f"{_paper_grade_contract_suffix(item)}"
    )


def _paper_grade_contract_suffix(item: dict[str, Any]) -> str:
    fragments = []
    if "paper_grade_ready" in item:
        fragments.append(f"paper_grade_ready=`{item.get('paper_grade_ready')}`")
    primary_metric = str(item.get("primary_metric") or "").strip()
    if primary_metric:
        fragments.append(f"primary_metric=`{primary_metric}`")
    contract_id = str(item.get("contract_id") or "").strip()
    if contract_id:
        fragments.append(f"contract_id=`{contract_id}`")
    blockers = [str(item) for item in item.get("paper_grade_blockers") or []]
    if blockers:
        fragments.append(f"blockers=`{', '.join(blockers)}`")
    if not fragments:
        return ""
    return ", " + ", ".join(fragments)
