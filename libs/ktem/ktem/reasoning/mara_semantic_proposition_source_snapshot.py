from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from ktem.docqa.evidence_schema import EvidenceBundle


def source_input_snapshot(
    request: Any,
    question: str,
    slots: list[dict[str, Any]],
    bundle: EvidenceBundle,
    source_decisions: list[dict[str, Any]],
    *,
    candidate_priority: bool,
    item_char_limit: int,
) -> dict[str, Any]:
    """Freeze the exact inputs that can affect source packing."""

    source_items = [
        {
            "source_item_index": decision.get("source_item_index"),
            "evidence_id": str(decision.get("evidence_id") or ""),
            "text_digest": str(decision.get("text_digest") or ""),
            "text_chars": decision.get("text_chars"),
            "identity_decision": str(decision.get("decision") or ""),
            "identity_reason": str(decision.get("reason") or ""),
        }
        for decision in source_decisions
    ]
    ranked_evidence = _ranked_evidence(bundle)
    query_plan = _plain_value(getattr(request, "query_plan", None))
    payload = {
        "contract_id": "semantic_source_input_snapshot.v1",
        "complete": bool(
            len(source_items) == len(bundle.items)
            and all(item["source_item_index"] for item in source_items)
            and all(item["text_digest"] for item in source_items)
        ),
        "route": str(bundle.route or ""),
        "candidate_priority": candidate_priority,
        "question": question.strip(),
        "question_digest": _digest(question.strip()),
        "query_plan": query_plan,
        "query_plan_digest": _digest(query_plan),
        "required_slots": deepcopy(slots),
        "required_slots_digest": _digest(slots),
        "max_context_length": _plain_value(
            getattr(request, "max_context_length", None)
        ),
        "item_char_limit": item_char_limit,
        "source_item_count": len(source_items),
        "source_items_digest": _digest(source_items),
        "source_items": source_items,
        "ranked_evidence_present": "candidate_ranked_evidence" in bundle.metadata,
        "ranked_evidence_count": len(ranked_evidence),
        "ranked_evidence_digest": _digest(ranked_evidence),
        "ranked_evidence": ranked_evidence,
    }
    payload["snapshot_digest"] = _digest(payload)
    return payload


def _ranked_evidence(bundle: EvidenceBundle) -> list[dict[str, Any]]:
    raw = bundle.metadata.get("candidate_ranked_evidence")
    values = raw if isinstance(raw, list) else []
    return [
        {
            "ranked_position": index,
            "canonical_id": (
                str(value.get("canonical_id") or "").strip()
                if isinstance(value, Mapping)
                else ""
            ),
        }
        for index, value in enumerate(values)
    ]


def _plain_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _plain_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain_value(item) for item in value]
    if is_dataclass(value):
        return _plain_value(asdict(value))
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _plain_value(model_dump(mode="json"))
    as_dict = getattr(value, "dict", None)
    if callable(as_dict):
        return _plain_value(as_dict())
    return str(value)


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
