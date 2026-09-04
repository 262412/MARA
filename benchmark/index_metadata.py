from __future__ import annotations

from typing import Any

from ktem.docqa.benchmark_evidence import benchmark_evidence_record


def normalize_retrieved_hit(item: dict[str, Any]) -> dict[str, Any]:
    return benchmark_evidence_record(item).as_dict()
