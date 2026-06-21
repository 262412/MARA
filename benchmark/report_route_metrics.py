from __future__ import annotations

from typing import Any


def route_metrics_markdown(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Dataset | Route | N | Dataset-Native Local Score | "
        "MARA Diagnostic Proxy Score | "
        "Diagnostic F1 | Page Hit | Metadata Citation R/P | Inline Citation R/P | "
        "Unsupported Claim Rate | Total Seconds |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('dataset_name')} | "
            f"{row.get('route')} | "
            f"{row.get('num_predictions')} | "
            f"{row.get('avg_native_score')} | "
            f"{row.get('avg_mara_proxy_score')} | "
            f"{row.get('avg_f1')} | "
            f"{row.get('avg_page_hit')} | "
            f"{_citation_pair(row, 'metadata')} | "
            f"{_citation_pair(row, 'inline')} | "
            f"{row.get('avg_unsupported_claim_rate')} | "
            f"{row.get('avg_total_seconds')} |"
        )
    return lines


def _citation_pair(row: dict[str, Any], citation_kind: str) -> str:
    return (
        f"{row.get(f'avg_citation_{citation_kind}_recall')} / "
        f"{row.get(f'avg_citation_{citation_kind}_precision')}"
    )
