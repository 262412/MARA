from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ktem.docqa.evidence_alias_lookup import unambiguous_evidence_alias_lookup
from ktem.docqa.evidence_identity import exact_evidence_aliases, identity_of
from ktem.docqa.required_slot_selection import REQUIRED_SLOT_CANDIDATE_QUOTA


@dataclass(frozen=True)
class QasperEvidencePriorities:
    required_evidence_ids: tuple[str, ...]
    required_slot_ids: tuple[str, ...]
    missing_required_slot_ids: tuple[str, ...]
    missing_required_evidence_ids: tuple[str, ...]
    generation_evidence_ids: tuple[str, ...]
    claim_support_evidence_ids: tuple[str, ...]
    claim_contradiction_evidence_ids: tuple[str, ...]


def qasper_evidence_priorities(
    prediction: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    *,
    question: str,
    candidate_answer: str,
) -> QasperEvidencePriorities:
    support, contradiction = _claim_evidence_ids(prediction)
    generation = _stage_evidence_ids(prediction, "generation_context_evidence")
    (
        required,
        slot_ids,
        missing_slot_ids,
        missing_evidence_ids,
    ) = _required_slot_representatives(
        prediction,
        evidence_items,
        question=question,
        candidate_answer=candidate_answer,
        preferred_ids={*support, *generation},
    )
    return QasperEvidencePriorities(
        required_evidence_ids=tuple(required),
        required_slot_ids=tuple(slot_ids),
        missing_required_slot_ids=tuple(missing_slot_ids),
        missing_required_evidence_ids=tuple(missing_evidence_ids),
        generation_evidence_ids=tuple(generation),
        claim_support_evidence_ids=tuple(support),
        claim_contradiction_evidence_ids=tuple(contradiction),
    )


def _required_slot_representatives(
    prediction: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    *,
    question: str,
    candidate_answer: str,
    preferred_ids: set[str],
) -> tuple[list[str], list[str], list[str], list[str]]:
    payload = _query_plan_payload(prediction)
    if not isinstance(payload, dict):
        return [], [], [], []
    lookup = unambiguous_evidence_alias_lookup(evidence_items)
    query_tokens = _tokens(f"{question} {candidate_answer}")
    output: list[str] = []
    slot_ids: list[str] = []
    missing_slot_ids: list[str] = []
    missing_evidence_ids: list[str] = []
    for slot in payload.get("evidence_slots") or []:
        if not isinstance(slot, dict) or not _slot_required(slot):
            continue
        slot_id = str(slot.get("slot_id") or "").strip()
        if slot_id and slot_id not in slot_ids:
            slot_ids.append(slot_id)
        references = [
            str(value).strip()
            for value in slot.get("evidence_ids") or []
            if str(value).strip()
        ]
        if not references:
            if slot_id and slot_id not in missing_slot_ids:
                missing_slot_ids.append(slot_id)
            continue
        resolved = {
            identity_of(item).key: item
            for reference in references
            if (item := lookup.get(reference)) is not None
        }
        unresolved = [reference for reference in references if reference not in lookup]
        for reference in unresolved:
            if reference not in missing_evidence_ids:
                missing_evidence_ids.append(reference)
        if unresolved and slot_id and slot_id not in missing_slot_ids:
            missing_slot_ids.append(slot_id)
        candidate_limit = (
            REQUIRED_SLOT_CANDIDATE_QUOTA
            if str(slot.get("statement_kind") or "") == "boolean_proposition"
            else 1
        )
        if resolved:
            representatives = sorted(
                resolved,
                key=lambda identity: (
                    int(_aliases_overlap(resolved[identity], preferred_ids)),
                    len(query_tokens & _tokens(_item_text(resolved[identity]))),
                    -len(_item_text(resolved[identity])),
                    identity,
                ),
                reverse=True,
            )[:candidate_limit]
        else:
            representatives = []
            if slot_id and slot_id not in missing_slot_ids:
                missing_slot_ids.append(slot_id)
        for representative in representatives:
            if representative not in output:
                output.append(representative)
    return output, slot_ids, missing_slot_ids, missing_evidence_ids


def _claim_evidence_ids(
    prediction: dict[str, Any],
) -> tuple[list[str], list[str]]:
    support: list[str] = []
    contradiction: list[str] = []
    decisions: list[dict[str, Any]] = []
    for source in _metadata_sources(prediction):
        decision = source.get("verify_decision")
        if isinstance(decision, dict):
            decisions.append(decision)
    top_level = prediction.get("verify_decision")
    if isinstance(top_level, dict):
        decisions.append(top_level)
    for decision in decisions:
        for claim in decision.get("claim_results") or []:
            if not isinstance(claim, dict):
                continue
            _extend_unique(support, claim.get("supporting_evidence_ids"))
            _extend_unique(
                contradiction,
                claim.get("contradicting_evidence_ids"),
            )
    return support, contradiction


def _stage_evidence_ids(
    prediction: dict[str, Any],
    stage: str,
) -> list[str]:
    output: list[str] = []
    for source in _metadata_sources(prediction):
        for item in source.get(stage) or []:
            if not isinstance(item, dict):
                continue
            try:
                identity = identity_of(item).key
            except ValueError:
                continue
            if identity not in output:
                output.append(identity)
    return output


def _query_plan_payload(prediction: dict[str, Any]) -> dict[str, Any] | None:
    for source in _metadata_sources(prediction):
        payload = source.get("query_plan")
        if isinstance(payload, dict):
            return payload
    return None


def _metadata_sources(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    metadata = prediction.get("evidence_metadata")
    if isinstance(metadata, dict):
        sources.append(metadata)
    bundle = prediction.get("evidence_bundle")
    bundle_metadata = bundle.get("metadata") if isinstance(bundle, dict) else None
    if isinstance(bundle_metadata, dict):
        sources.append(bundle_metadata)
    return sources


def _slot_required(slot: dict[str, Any]) -> bool:
    return any(
        bool(slot.get(field))
        for field in (
            "required",
            "required_for_retrieval",
            "required_for_execution",
            "required_for_verification",
        )
    )


def _aliases_overlap(item: dict[str, Any], values: set[str]) -> bool:
    return bool(exact_evidence_aliases(item) & values)


def _item_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "").strip()
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if str(item.get(field) or "").strip()
    )


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if len(token) > 3
    }


def _extend_unique(output: list[str], values: Any) -> None:
    for value in values or []:
        normalized = str(value or "").strip()
        if normalized and normalized not in output:
            output.append(normalized)
