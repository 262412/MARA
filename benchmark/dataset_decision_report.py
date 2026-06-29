from __future__ import annotations

from typing import Any


def phase2_summary_markdown(summary: dict[str, Any]) -> list[str]:
    decision = summary.get("phase2_dataset_decision") or {}
    if not isinstance(decision, dict) or not decision:
        return []
    lines = [f"- Phase2 Decision: `{decision.get('decision')}`"]
    for label, key in (
        ("Headline Routes", "headline_routes"),
        ("Diagnostic Routes", "diagnostic_routes"),
        ("Blocked Routes", "blocked_routes"),
        ("Blockers", "blockers"),
    ):
        value = _inline_list(decision.get(key))
        if value:
            lines.append(f"- Phase2 {label}: `{value}`")
    return lines


def phase2_failure_counts_markdown(summary: dict[str, Any]) -> list[str]:
    rows = summary.get("phase2_failure_counts") or []
    rows = [dict(row) for row in rows if isinstance(row, dict)]
    if not rows:
        return []
    lines = [
        "| Dataset | Route | Dataset Decision | Phase2 Failure Type | Count |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('dataset_name')} | "
            f"{row.get('route')} | "
            f"{row.get('dataset_decision')} | "
            f"{row.get('phase2_failure_type')} | "
            f"{row.get('count')} |"
        )
    return lines


def _inline_list(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)
