from __future__ import annotations

from typing import Any


def headline_score_lines(summary: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if "primary_score" in summary:
        label = str(summary.get("primary_score_label") or "Score").strip()
        lines.append(f"- Primary Score ({label}): `{summary.get('primary_score')}`")
    if "primary_score_metric" in summary:
        lines.append(f"- Primary Score Metric: `{summary.get('primary_score_metric')}`")
    if "primary_score_scope" in summary:
        lines.append(f"- Primary Score Scope: `{summary.get('primary_score_scope')}`")
    if "score_authority_level" in summary:
        lines.append(
            f"- Score Authority Level: `{summary.get('score_authority_level')}`"
        )
    if "paper_grade_score_available" in summary:
        lines.append(
            "- Paper-Grade External Score Available: "
            f"`{summary.get('paper_grade_score_available')}`"
        )
    if "avg_native_score" in summary:
        lines.append(
            f"- Dataset-Native Local Score: `{summary.get('avg_native_score')}`"
        )
    if "avg_mara_proxy_score" in summary:
        lines.append(
            f"- MARA Diagnostic Proxy Score: `{summary.get('avg_mara_proxy_score')}`"
        )
    return lines
