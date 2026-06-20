from __future__ import annotations

from typing import Any


def headline_score_lines(summary: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if "primary_score" in summary:
        lines.append(f"- Primary Score: `{summary.get('primary_score')}`")
    if "primary_score_metric" in summary:
        lines.append(f"- Primary Score Metric: `{summary.get('primary_score_metric')}`")
    if "primary_score_scope" in summary:
        lines.append(f"- Primary Score Scope: `{summary.get('primary_score_scope')}`")
    if "avg_mara_score" in summary:
        lines.append(f"- MARA Native Score: `{summary.get('avg_mara_score')}`")
    if "avg_mara_proxy_score" in summary:
        lines.append(f"- MARA Proxy Score: `{summary.get('avg_mara_proxy_score')}`")
    return lines
