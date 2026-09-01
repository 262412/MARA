from __future__ import annotations

from typing import Any

from .mara_semantic_proposition_packing_support import optional_int
from .mara_semantic_proposition_span_selectors import canonical_span_selector_projection


def label_evidence_records(
    records: list[dict[str, Any]],
    *,
    question: str,
    selector_max_chars: int,
    max_selectors: int,
) -> list[dict[str, Any]]:
    labeled: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        label = f"E{index}"
        selectors, selector_trace = canonical_span_selector_projection(
            label,
            str(record["text"]),
            int(record.get("text_start") or 0),
            optional_int(record.get("canonical_start")),
            selector_max_chars=selector_max_chars,
            question=question,
            max_selectors=max_selectors,
        )
        labeled.append(
            {
                **record,
                "label": label,
                "selectors": selectors,
                "source_selector_projection_trace": selector_trace,
            }
        )
    return labeled
