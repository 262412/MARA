from __future__ import annotations

import re
from typing import Any

from ktem.docqa.evidence_identity import identity_of

from .qasper_boolean_scope import scope_valid_support_items
from .qasper_deterministic_support import deterministic_support_ids
from .task_answer_contracts import runtime_boolean_authority
from .verified_claim_citations import verified_claim_support_groups


def minimum_verified_claim_support_items(
    prediction: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    span: str,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    derived_ids = _runtime_derived_support_ids(prediction)
    for group in verified_claim_support_groups(prediction, candidates):
        scoped = _scope_valid_group(prediction, group, span=span)
        if not scoped:
            continue
        if derived_ids:
            proof = _ordered_support_items(scoped, derived_ids)
            if len(proof) != len(derived_ids):
                continue
            selected.extend(proof)
        else:
            selected.append(_best_item(prediction, scoped, span=span))
    return _deduplicated_items(selected)


def _runtime_derived_support_ids(prediction: dict[str, Any]) -> list[str]:
    authority = runtime_boolean_authority(prediction)
    if not authority["complete"] or authority["authority_kind"] not in {
        "composite_polarity",
        "semantic_evidence_set_polarity",
    }:
        return []
    return list(
        dict.fromkeys(str(value) for value in authority["required_evidence_ids"])
    )


def _ordered_support_items(
    items: list[dict[str, Any]],
    evidence_ids: list[str],
) -> list[dict[str, Any]]:
    by_id = {identity_of(item).key: item for item in items}
    return [by_id[evidence_id] for evidence_id in evidence_ids if evidence_id in by_id]


def _deduplicated_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for item in items:
        output.setdefault(identity_of(item).key, item)
    return list(output.values())


def _scope_valid_group(
    prediction: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    span: str,
) -> list[dict[str, Any]]:
    if str(prediction.get("answer_type") or "").strip().lower() != "boolean":
        return items
    runtime_authoritative = _runtime_authoritative_qasper_support(prediction, items)
    if runtime_authoritative:
        return runtime_authoritative
    deterministic = _deterministic_qasper_support(prediction, items)
    if deterministic:
        return deterministic
    authoritative = _authoritative_qasper_support(prediction, items)
    if authoritative:
        return authoritative
    return scope_valid_support_items(
        str(prediction.get("question") or ""),
        span,
        items,
    )


def _runtime_authoritative_qasper_support(
    prediction: dict[str, Any],
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    authority = runtime_boolean_authority(prediction)
    if not authority["complete"]:
        return []
    if authority["authority_kind"] in {
        "composite_polarity",
        "semantic_evidence_set_polarity",
    }:
        return _ordered_support_items(items, authority["required_evidence_ids"])
    evidence_id = str(authority["evidence_id"])
    matches = [item for item in items if identity_of(item).key == evidence_id]
    return matches if len(matches) == 1 else []


def _deterministic_qasper_support(
    prediction: dict[str, Any],
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    metadata = prediction.get("evidence_metadata")
    trace = metadata.get("qasper_answerability") if isinstance(metadata, dict) else None
    if not isinstance(trace, dict):
        return []
    support_ids = deterministic_support_ids(trace)
    return [item for item in items if identity_of(item).key in support_ids]


def _authoritative_qasper_support(
    prediction: dict[str, Any],
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    metadata = prediction.get("evidence_metadata")
    trace = metadata.get("qasper_answerability") if isinstance(metadata, dict) else None
    if not isinstance(trace, dict):
        return []
    support_id = str(trace.get("authoritative_quote_evidence_id") or "").strip()
    if not support_id:
        return []
    return [item for item in items if identity_of(item).key == support_id]


def _best_item(
    prediction: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    span: str,
) -> dict[str, Any]:
    query_tokens = _tokens(f"{prediction.get('question') or ''} {span}")
    return max(
        items,
        key=lambda item: (
            len(query_tokens & _tokens(_item_text(item))),
            -len(_item_text(item)),
        ),
    )


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _item_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "")
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if item.get(field)
    )
