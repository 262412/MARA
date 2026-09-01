from __future__ import annotations

from typing import Any


def semantic_evidence_set_authority_invalid(trace: dict[str, Any]) -> bool:
    semantic_status = str(
        trace.get("runtime_semantic_proposition_authority_status") or ""
    )
    typed_complete = bool(
        trace.get("runtime_typed_authority_kind") == "semantic_evidence_set"
        and trace.get("runtime_typed_authority_derivation_status") == "bound"
        and trace.get("runtime_typed_authority_complete")
    )
    return bool(
        semantic_status in {"failed", "rejected"}
        or (semantic_status == "verified" and not typed_complete)
        or (
            trace.get("runtime_typed_authority_kind") == "semantic_evidence_set"
            and not typed_complete
        )
    )
