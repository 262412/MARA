from __future__ import annotations

from typing import Any


def verifier_observability_markdown(summary: dict[str, Any]) -> list[str]:
    rows = summary.get("verifier_observability_by_route") or []
    rows = [dict(row) for row in rows if isinstance(row, dict)]
    if not rows:
        return []
    lines = [
        "| Dataset | Route | N | True Abstain | False Abstain | "
        "Unsupported Rows | Unsupported Claims | Retry Rows | Retry Count | "
        "Route Switch Rows | Route Switch Count |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('dataset_name')} | "
            f"{row.get('route')} | "
            f"{row.get('num_predictions')} | "
            f"{row.get('num_true_abstention')} | "
            f"{row.get('num_false_abstention')} | "
            f"{row.get('num_unsupported_claim')} | "
            f"{row.get('total_unsupported_claim_count')} | "
            f"{row.get('num_retry')} | "
            f"{row.get('total_retry_count')} | "
            f"{row.get('num_route_switch')} | "
            f"{row.get('total_route_switch_count')} |"
        )
    return lines
