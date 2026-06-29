from __future__ import annotations

from typing import Any


def phase3_summary_markdown(summary: dict[str, Any]) -> list[str]:
    phase3 = summary.get("phase3_multimodal_summary") or {}
    if not isinstance(phase3, dict) or not phase3:
        return []
    page_image = _section(phase3, "page_image")
    element = _section(phase3, "element")
    graph = _section(phase3, "graph")
    return [
        f"- Phase3 Page-image Status: `{page_image.get('status')}`",
        f"- Phase3 Element Coverage: `{element.get('status')}`",
        f"- Phase3 Graph Scope: `{graph.get('scope')}`",
        f"- Phase3 Full GraphRAG Claim: `{bool(graph.get('full_graphrag_claim'))}`",
    ]


def phase3_hybrid_metrics_markdown(summary: dict[str, Any]) -> list[str]:
    phase3 = summary.get("phase3_multimodal_summary") or {}
    if not isinstance(phase3, dict):
        return []
    hybrid = phase3.get("hybrid") or {}
    if not isinstance(hybrid, dict):
        return []
    rows = [dict(row) for row in hybrid.get("question_type_route_metrics") or []]
    if not rows:
        return []
    lines = [
        "| Question Type | Route | Count | Avg F1 | Avg Native | Avg Page Hit |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('question_type')} | "
            f"{row.get('route')} | "
            f"{row.get('count')} | "
            f"{row.get('avg_f1')} | "
            f"{row.get('avg_native_score')} | "
            f"{row.get('avg_page_hit')} |"
        )
    return lines


def phase3_report_sections(summary: dict[str, Any]) -> list[tuple[str, list[str]]]:
    return [
        (
            "Phase3 Hybrid Question-Type Metrics",
            phase3_hybrid_metrics_markdown(summary),
        )
    ]


def _section(summary: dict[str, Any], key: str) -> dict[str, Any]:
    value = summary.get(key) or {}
    return dict(value) if isinstance(value, dict) else {}
