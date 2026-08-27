from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from .evidence_schema import EvidenceBundle

QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT = "qasper_canonical_semantic_pack.v1"
QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY = "qasper_canonical_semantic_pack"

_PROPOSITION_SLOTS = ("actor", "predicate", "object", "quantifier")


def canonical_payload_digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def qasper_canonical_span_universe_digest(
    records: Sequence[Mapping[str, Any]],
) -> str:
    universe = [
        {
            "evidence_id": str(record.get("evidence_id") or ""),
            "selector_id": str(selector.get("selector_id") or ""),
            "text": str(selector.get("text") or ""),
            "span_start": selector.get("span_start"),
            "span_end": selector.get("span_end"),
            "canonical_start": selector.get("canonical_start"),
            "canonical_end": selector.get("canonical_end"),
            "allowed_proposition_slots": list(
                selector.get("allowed_proposition_slots") or []
            ),
            "proposition_slot_spans": deepcopy(
                dict(selector.get("proposition_slot_spans") or {})
            ),
            "relation_bearing": selector.get("relation_bearing"),
            "candidate_relation_role": str(
                selector.get("candidate_relation_role") or ""
            ),
            "local_relation_state": str(selector.get("local_relation_state") or ""),
            "local_relation_analysis_digest": str(
                selector.get("local_relation_analysis_digest") or ""
            ),
        }
        for record in records
        for selector in record.get("selectors") or []
        if isinstance(selector, Mapping)
    ]
    return canonical_payload_digest(universe)


def qasper_canonical_records_reason(
    records: Sequence[Mapping[str, Any]],
) -> str:
    selector_ids: set[str] = set()
    for record in records:
        evidence_id = str(record.get("evidence_id") or "").strip()
        if not evidence_id:
            return "canonical_semantic_pack_record_invalid"
        for selector in record.get("selectors") or []:
            if not isinstance(selector, Mapping):
                return "canonical_semantic_pack_selector_invalid"
            selector_id = str(selector.get("selector_id") or "").strip()
            text = str(selector.get("text") or "")
            start = selector.get("span_start")
            end = selector.get("span_end")
            slots = selector.get("allowed_proposition_slots")
            if not isinstance(slots, list):
                return "canonical_semantic_pack_selector_invalid"
            relation_role = str(selector.get("candidate_relation_role") or "")
            local_state = str(selector.get("local_relation_state") or "")
            slots_valid = bool(
                len(set(slots)) == len(slots)
                and all(slot in _PROPOSITION_SLOTS for slot in slots)
            )
            uncertainty_only = bool(
                relation_role == "uncertainty_context"
                and local_state in {"mention_only", "unbound"}
                and selector.get("relation_bearing") is True
                and slots == []
            )
            if (
                not selector_id
                or selector_id in selector_ids
                or not text
                or not isinstance(start, int)
                or isinstance(start, bool)
                or not isinstance(end, int)
                or isinstance(end, bool)
                or start < 0
                or end <= start
                or end - start != len(text)
                or not slots_valid
                or not _proposition_slot_spans_valid(selector, slots)
                or (not slots and not uncertainty_only)
                or not isinstance(selector.get("relation_bearing"), bool)
                or relation_role not in {"polarity_evidence", "uncertainty_context"}
                or local_state
                not in {
                    "affirmative_assertion",
                    "explicit_contradiction",
                    "mention_only",
                    "unbound",
                }
                or not str(selector.get("local_relation_analysis_digest") or "")
            ):
                return "canonical_semantic_pack_selector_invalid"
            selector_ids.add(selector_id)
    return ""


def _proposition_slot_spans_valid(
    selector: Mapping[str, Any],
    slots: list[str],
) -> bool:
    raw = selector.get("proposition_slot_spans")
    if not isinstance(raw, Mapping) or set(raw) != set(slots):
        return False
    parent_id = str(selector.get("selector_id") or "")
    parent_text = str(selector.get("text") or "")
    parent_start = selector.get("span_start")
    parent_end = selector.get("span_end")
    if not isinstance(parent_start, int) or not isinstance(parent_end, int):
        return False
    parent_digest = canonical_payload_digest(parent_text)
    for slot in slots:
        child = raw.get(slot)
        if not isinstance(child, Mapping):
            return False
        text = str(child.get("text") or "")
        start = child.get("span_start")
        end = child.get("span_end")
        if (
            not text
            or not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < parent_start
            or end > parent_end
            or end <= start
            or end - start != len(text)
            or parent_text[start - parent_start : end - parent_start] != text
            or child.get("parent_selector_id") != parent_id
            or child.get("parent_span_start") != parent_start
            or child.get("parent_span_end") != parent_end
            or child.get("text_digest") != canonical_payload_digest(text)
            or child.get("parent_text_digest") != parent_digest
        ):
            return False
    return True


def qasper_semantic_pack_continuity_reason(
    bundle: EvidenceBundle,
    *,
    question: str,
    response: Mapping[str, Any],
) -> str:
    """Validate candidate, verifier, auditor, and authority object identity."""

    raw = bundle.metadata.get(QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY)
    if not isinstance(raw, Mapping):
        return "canonical_semantic_pack_missing"
    payload = deepcopy(dict(raw))
    identity_digest = str(payload.pop("pack_identity_digest", "") or "")
    if (
        payload.get("contract_id") != QASPER_CANONICAL_SEMANTIC_PACK_CONTRACT
        or not identity_digest
        or canonical_payload_digest(payload) != identity_digest
        or payload.get("immutable_after_candidate_generation") is not True
        or str(payload.get("question_digest") or "")
        != canonical_payload_digest(question.strip())
    ):
        return "canonical_semantic_pack_identity_mismatch"
    records = payload.get("records")
    if not isinstance(records, list):
        return "canonical_semantic_pack_identity_mismatch"
    record_reason = qasper_canonical_records_reason(records)
    if record_reason:
        return record_reason
    semantic_digest = str(payload.get("semantic_pack_digest") or "")
    span_digest = str(payload.get("span_universe_digest") or "")
    candidate_transaction_id = str(payload.get("candidate_transaction_id") or "")
    if (
        not semantic_digest
        or not candidate_transaction_id
        or span_digest != qasper_canonical_span_universe_digest(records)
    ):
        return "canonical_semantic_pack_identity_mismatch"
    expected_identity = {
        "semantic_pack_digest": semantic_digest,
        "span_universe_digest": span_digest,
        "candidate_transaction_id": candidate_transaction_id,
    }
    if _stage_identity_reason(bundle, response, expected_identity, payload):
        return "canonical_semantic_pack_stage_identity_mismatch"
    selector_lookup, lookup_reason = _selector_lookup(records)
    if lookup_reason:
        return lookup_reason
    selection_reason = _response_selection_reason(response, selector_lookup)
    if selection_reason:
        return selection_reason
    return ""


def _stage_identity_reason(
    bundle: EvidenceBundle,
    response: Mapping[str, Any],
    expected: Mapping[str, str],
    pack: Mapping[str, Any],
) -> str:
    candidate = bundle.metadata.get("qasper_candidate_generation")
    verifier_trace = bundle.metadata.get("semantic_proposition_verifier")
    response_verifier = response.get("verifier")
    if not isinstance(candidate, Mapping):
        return "stage_identity_missing"
    if not isinstance(verifier_trace, Mapping):
        return "stage_identity_missing"
    if not isinstance(response_verifier, Mapping):
        return "stage_identity_missing"
    candidate_expected = {
        "canonical_semantic_pack_digest": expected["semantic_pack_digest"],
        "canonical_span_universe_digest": expected["span_universe_digest"],
        "transaction_id": expected["candidate_transaction_id"],
    }
    if (
        any(candidate.get(key) != value for key, value in candidate_expected.items())
        or candidate.get("candidate_evidence_set_binding")
        != pack.get("proposition_binding")
        or candidate.get("required_slots") != pack.get("slots")
    ):
        return "candidate_stage_identity_mismatch"
    verifier_expected = {
        "semantic_pack_digest": expected["semantic_pack_digest"],
        "canonical_span_universe_digest": expected["span_universe_digest"],
        "candidate_transaction_id": expected["candidate_transaction_id"],
    }
    if (
        any(
            verifier_trace.get(key) != value for key, value in verifier_expected.items()
        )
        or verifier_trace.get("canonical_pack_continuity_status") != "preserved"
    ):
        return "verifier_trace_identity_mismatch"
    if (
        any(
            response_verifier.get(key) != value
            for key, value in verifier_expected.items()
        )
        or response_verifier.get("canonical_pack_continuity_status") != "preserved"
    ):
        return "verifier_response_identity_mismatch"
    audit = _auditor_identity_source(response)
    if not isinstance(audit, Mapping):
        return "auditor_identity_missing"
    if dict(audit.get("semantic_pack_identity") or {}) != dict(expected):
        return "auditor_identity_mismatch"
    return ""


def _selector_lookup(
    records: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], str]:
    output: dict[str, dict[str, Any]] = {}
    for record in records:
        for selector in record.get("selectors") or []:
            selector_id = str(selector.get("selector_id") or "")
            if selector_id in output:
                return {}, "canonical_semantic_pack_selector_invalid"
            output[selector_id] = {
                "evidence_id": str(record.get("evidence_id") or ""),
                **dict(selector),
            }
    return output, ""


def _response_selection_reason(
    response: Mapping[str, Any],
    selectors: Mapping[str, Mapping[str, Any]],
) -> str:
    verdict = str(response.get("verdict") or "")
    premises = response.get("premises")
    selected = premises if isinstance(premises, list) and premises else None
    rejected = response.get("rejected_transaction")
    if selected is None and isinstance(rejected, Mapping):
        rejected_premises = rejected.get("premises")
        if isinstance(rejected_premises, list) and rejected_premises:
            selected = rejected_premises
    if (
        selected is None
        and verdict == "insufficient_evidence"
        and isinstance(response.get("unknown_assessment"), Mapping)
    ):
        selected = (response.get("unknown_assessment") or {}).get("reviewed_evidence")
    if not isinstance(selected, list) or not selected:
        return "canonical_semantic_pack_selection_missing"
    for value in selected:
        if not isinstance(value, Mapping):
            return "canonical_semantic_pack_selection_mismatch"
        selector_id = str(value.get("span_selector") or "")
        selector = selectors.get(selector_id)
        if selector is None or any(
            value.get(field) != selector.get(source)
            for field, source in (
                ("evidence_id", "evidence_id"),
                ("quote", "text"),
                ("span_start", "span_start"),
                ("span_end", "span_end"),
            )
        ):
            return "canonical_semantic_pack_selection_mismatch"
        declared = value.get("binds_proposition_slots")
        if declared is not None and list(declared) != list(
            selector.get("allowed_proposition_slots") or []
        ):
            return "canonical_semantic_pack_slot_binding_mismatch"
    return ""


def _auditor_identity_source(
    response: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    for key in ("entailment_audit", "candidate_verification_audit"):
        value = response.get(key)
        if isinstance(value, Mapping) and isinstance(
            value.get("semantic_pack_identity"), Mapping
        ):
            return value
    rejected = response.get("rejected_transaction")
    if isinstance(rejected, Mapping) and isinstance(
        rejected.get("semantic_pack_identity"), Mapping
    ):
        return {"semantic_pack_identity": rejected["semantic_pack_identity"]}
    return None
