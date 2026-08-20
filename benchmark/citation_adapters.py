from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_alias_lookup import unambiguous_evidence_alias_lookup
from ktem.docqa.evidence_identity import identity_of

from .alce_answer_grounding import _supported_answer_consistent


def project_alce_grounding_support(
    prediction: dict[str, Any],
    *,
    final_answer: str,
) -> bool:
    """Project one accepted ALCE grounding result into citation authority."""

    trace = _metadata_value(prediction, "alce_answer_grounding")
    if not isinstance(trace, dict):
        return False
    if (
        str(trace.get("status") or "") != "ok"
        or str(trace.get("verdict") or "") != "supported"
        or bool(trace.get("answer_changed"))
    ):
        return False

    expected_answer = str(trace.get("grounded_answer") or "")
    if not expected_answer or not _supported_answer_consistent(
        expected_answer,
        final_answer,
    ):
        return False
    candidate = _resolve_evidence_alias(
        _citation_candidates(prediction),
        str(trace.get("evidence_id") or ""),
    )
    if candidate is None:
        return False
    _record_support(
        prediction,
        items=[candidate],
        by_claim={"alce:grounding": [identity_of(candidate).key]},
    )
    return True


def project_ragtruth_claim_support(prediction: dict[str, Any]) -> bool:
    """Bridge supported RAGTruth claims to unique canonical evidence."""

    supported = _metadata_value(prediction, "ragtruth_supported_claim_indices")
    claims = _metadata_value(prediction, "ragtruth_claims")
    if not isinstance(supported, list) or not isinstance(claims, list):
        return False
    if not supported or not claims:
        return False
    try:
        supported_indices = [int(index) for index in supported]
    except (TypeError, ValueError):
        return False
    if any(index < 0 or index >= len(claims) for index in supported_indices):
        return False
    if any(
        not isinstance(claims[index], str) or not claims[index].strip()
        for index in supported_indices
    ):
        return False

    # Emitted indices are an output of the hallucination contract, never a
    # source of citation authority. A contradictory overlap is fail-closed.
    emitted = _metadata_value(prediction, "ragtruth_emitted_claim_indices")
    if _integer_indices(emitted) & set(supported_indices):
        return False

    source_item = _resolve_evidence_alias(
        _citation_candidates(prediction),
        str(_metadata_value(prediction, "ragtruth_source_evidence_id") or ""),
    )
    if source_item is None:
        return False
    source_identity = identity_of(source_item).key
    _record_support(
        prediction,
        items=[source_item],
        by_claim={
            f"ragtruth:claim:{index}": [source_identity]
            for index in dict.fromkeys(supported_indices)
        },
    )
    return True


def _metadata_value(prediction: dict[str, Any], key: str) -> Any:
    values = [
        metadata[key] for metadata in _metadata_sources(prediction) if key in metadata
    ]
    if not values or any(value != values[0] for value in values[1:]):
        return None
    return values[0]


def _metadata_sources(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    evidence_bundle = prediction.get("evidence_bundle")
    if isinstance(evidence_bundle, dict):
        metadata = evidence_bundle.get("metadata")
        if isinstance(metadata, dict):
            sources.append(metadata)
    evidence_metadata = prediction.get("evidence_metadata")
    if isinstance(evidence_metadata, dict):
        sources.append(evidence_metadata)
    return sources


def _citation_candidates(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    evidence_bundle = prediction.get("evidence_bundle")
    if isinstance(evidence_bundle, dict):
        items.extend(
            item
            for item in evidence_bundle.get("items") or []
            if isinstance(item, dict)
        )
    evidence_metadata = prediction.get("evidence_metadata")
    if isinstance(evidence_metadata, dict):
        for key in (
            "execution_operand_evidence",
            "selected_evidence",
            "generation_context_evidence",
            "evidence",
        ):
            items.extend(
                item
                for item in evidence_metadata.get(key) or []
                if isinstance(item, dict)
            )
    items.extend(
        item
        for item in prediction.get("retrieved_hits") or []
        if isinstance(item, dict)
    )
    return items


def _resolve_evidence_alias(
    candidates: list[dict[str, Any]],
    evidence_id: str,
) -> dict[str, Any] | None:
    target = str(evidence_id or "").strip()
    if not target:
        return None
    direct = unambiguous_evidence_alias_lookup(candidates).get(target)
    if direct is not None:
        return direct
    by_identity: dict[str, dict[str, Any]] = {}
    for item in candidates:
        if not any(
            str(item.get(key) or "").strip() == target
            for key in (
                "evidence_id",
                "canonical_id",
                "runtime_identity",
                "evaluation_identity",
            )
        ):
            continue
        try:
            by_identity[identity_of(item).key] = item
        except (TypeError, ValueError):
            continue
    return next(iter(by_identity.values())) if len(by_identity) == 1 else None


def _record_support(
    prediction: dict[str, Any],
    *,
    items: list[dict[str, Any]],
    by_claim: dict[str, list[str]],
) -> None:
    targets = _metadata_sources(prediction)
    if not targets:
        targets = [prediction.setdefault("evidence_metadata", {})]
    for metadata in targets:
        metadata["verified_claim_support_evidence"] = list(items)
        metadata["verified_claim_support_by_claim"] = dict(by_claim)


def _integer_indices(value: Any) -> set[int]:
    if not isinstance(value, list):
        return set()
    try:
        return {int(index) for index in value}
    except (TypeError, ValueError):
        return set()
