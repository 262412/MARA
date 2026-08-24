from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ktem.docqa.boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
)
from ktem.docqa.question_proposition import PROPOSITION_EVIDENCE_SLOTS


@dataclass(frozen=True)
class SemanticPropositionParse:
    value: dict[str, Any] | None
    failure_reason: str = ""


def semantic_proposition_response_format(
    _span_selectors: list[str],
    slot_ids: list[str],
) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "semantic_evidence_set_proposition",
            "strict": True,
            "schema": _semantic_proposition_schema(slot_ids),
        },
    }


def _semantic_proposition_schema(slot_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "candidate_judgment": {
                "type": "string",
                "enum": ["supported", "contradicted", "unknown"],
            },
            "evidence_relation": {
                "type": "string",
                "enum": [
                    "proposition_support",
                    "explicit_contradiction",
                    "undetermined",
                ],
            },
            "support_mode": {"type": "string", "enum": ["evidence_set"]},
            "proof_mode": {
                "type": "string",
                "enum": ["none", "atomic_semantic", "composite_conjunction"],
            },
            "jointly_complete": {"type": "boolean"},
            "each_premise_required": {"type": "boolean"},
            "premises": {
                "type": "array",
                "minItems": 0,
                "maxItems": 4,
                "items": _semantic_premise_schema(slot_ids),
            },
            "unknown_assessment": _unknown_assessment_schema(),
        },
        "required": [
            "candidate_judgment",
            "evidence_relation",
            "support_mode",
            "proof_mode",
            "jointly_complete",
            "each_premise_required",
            "premises",
        ],
        "additionalProperties": False,
    }


def _semantic_premise_schema(slot_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "span_selector": {"type": "string", "maxLength": 24},
            "proposition_fragment": {"type": "string", "maxLength": 320},
            "supports_slot_ids": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "enum": slot_ids},
            },
            "binds_proposition_slots": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "string",
                    "enum": list(PROPOSITION_EVIDENCE_SLOTS),
                },
            },
        },
        "required": [
            "span_selector",
            "proposition_fragment",
            "supports_slot_ids",
            "binds_proposition_slots",
        ],
        "additionalProperties": False,
    }


def _unknown_assessment_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "reviewed_span_selectors": {
                "type": "array",
                "minItems": 1,
                "maxItems": 12,
                "items": {"type": "string", "maxLength": 24},
            },
            "unresolved_proposition_slots": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "string",
                    "enum": list(PROPOSITION_EVIDENCE_SLOTS),
                },
            },
            "support_gap": {"type": "string", "maxLength": 320},
            "contradiction_gap": {"type": "string", "maxLength": 320},
        },
        "required": [
            "reviewed_span_selectors",
            "unresolved_proposition_slots",
            "support_gap",
            "contradiction_gap",
        ],
        "additionalProperties": False,
    }


def parse_semantic_proposition_result(
    response_text: str,
    *,
    packed: list[dict[str, Any]],
    slot_ids: set[str],
    model: str,
    seed: int,
    candidate: str = "",
) -> dict[str, Any] | None:
    return parse_semantic_proposition_response(
        response_text,
        packed=packed,
        slot_ids=slot_ids,
        model=model,
        seed=seed,
        candidate=candidate,
    ).value


def parse_semantic_proposition_response(
    response_text: str,
    *,
    packed: list[dict[str, Any]],
    slot_ids: set[str],
    model: str,
    seed: int,
    candidate: str = "",
) -> SemanticPropositionParse:
    try:
        payload = json.loads(response_text)
    except (TypeError, json.JSONDecodeError):
        return SemanticPropositionParse(None, "json_decode_error")
    (
        candidate_judgment,
        verdict,
        proof_mode,
        raw_premises,
        payload_reason,
    ) = _verdict_payload(payload, candidate=candidate)
    if payload_reason:
        return SemanticPropositionParse(None, payload_reason)
    assert verdict is not None and proof_mode is not None and raw_premises is not None
    selector_lookup = {
        str(selector["selector_id"]): {
            "evidence_id": value["evidence_id"],
            **selector,
        }
        for value in packed
        for selector in value.get("selectors", [])
    }
    premises, premise_reason = _parse_premises(raw_premises, selector_lookup, slot_ids)
    if premises is None:
        return SemanticPropositionParse(None, premise_reason)
    unknown_assessment: dict[str, Any] | None = None
    if verdict == "insufficient_evidence":
        unknown_assessment, assessment_reason = _parse_unknown_assessment(
            payload.get("unknown_assessment"), selector_lookup
        )
        if unknown_assessment is None:
            return SemanticPropositionParse(None, assessment_reason)
    elif "unknown_assessment" in payload:
        return SemanticPropositionParse(None, "unexpected_unknown_assessment")
    if verdict in {"yes", "no"} and {
        slot
        for premise in premises
        for slot in premise.get("binds_proposition_slots", [])
    } != set(PROPOSITION_EVIDENCE_SLOTS):
        return SemanticPropositionParse(None, "proposition_slot_coverage_incomplete")
    value = {
        "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "candidate_judgment": candidate_judgment,
        "verdict": verdict,
        "evidence_relation": payload["evidence_relation"],
        "support_mode": "evidence_set",
        "proof_mode": proof_mode,
        "jointly_complete": payload["jointly_complete"],
        "each_premise_required": payload["each_premise_required"],
        "premises": premises,
        "verifier": {
            "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
            "model": model,
            "seed": seed,
        },
    }
    if unknown_assessment is not None:
        value["unknown_assessment"] = unknown_assessment
    return SemanticPropositionParse(value)


def _verdict_payload_for_candidate(
    payload: Any,
    *,
    candidate: str,
) -> tuple[str | None, str | None, str | None, list[Any] | None, str]:
    if not isinstance(payload, dict):
        return None, None, None, None, "top_level_schema_invalid"
    candidate_judgment, direct, reason = _candidate_judgment_payload(
        payload,
        candidate=candidate,
    )
    if reason:
        return None, None, None, None, reason
    if payload.get("support_mode") != "evidence_set":
        return None, None, None, None, "support_mode_invalid"
    assert candidate_judgment is not None
    verdict, reason = _candidate_relative_verdict(
        payload,
        candidate=candidate,
        candidate_judgment=candidate_judgment,
        direct=direct,
    )
    if reason:
        return None, None, None, None, reason
    assert verdict is not None
    proof_mode, raw_premises, reason = _proof_payload(payload, verdict=verdict)
    if reason:
        return None, None, None, None, reason
    assert proof_mode is not None and raw_premises is not None
    if not _candidate_judgment_projection_valid(
        candidate,
        candidate_judgment,
        verdict,
    ):
        return (
            None,
            None,
            None,
            None,
            "candidate_judgment_unknown_inconsistent",
        )
    return candidate_judgment, verdict, proof_mode, raw_premises, ""


def _candidate_judgment_payload(
    payload: dict[str, Any],
    *,
    candidate: str,
) -> tuple[str | None, bool, str]:
    required_fields = {
        "candidate_judgment",
        "evidence_relation",
        "support_mode",
        "proof_mode",
        "jointly_complete",
        "each_premise_required",
        "premises",
    }
    legacy_required_fields = required_fields - {"candidate_judgment"} | {"verdict"}
    allowed_fields = required_fields | {"unknown_assessment"}
    legacy_allowed_fields = legacy_required_fields | {"unknown_assessment"}
    direct = "candidate_judgment" in payload
    if direct:
        if "verdict" in payload:
            return None, direct, "candidate_judgment_verdict_mixed"
        if not required_fields <= set(payload) or not set(payload) <= allowed_fields:
            return None, direct, "top_level_schema_invalid"
        candidate_judgment = payload.get("candidate_judgment")
        if candidate_judgment not in {"supported", "contradicted", "unknown"}:
            return None, direct, "candidate_judgment_invalid"
    else:
        # Keep parsing pre-v5 fixtures and older providers while the provider
        # schema itself exposes only the candidate-relative judgment. Legacy
        # payloads are still normalized deterministically below.
        if (
            not legacy_required_fields <= set(payload)
            or not set(payload) <= legacy_allowed_fields
        ):
            return None, direct, "top_level_schema_invalid"
        verdict = payload.get("verdict")
        if verdict not in {"yes", "no", "insufficient_evidence"}:
            return None, direct, "verdict_invalid"
        candidate_judgment = _candidate_judgment_for_verdict(
            candidate,
            str(verdict),
        )
    return str(candidate_judgment), direct, ""


def _candidate_relative_verdict(
    payload: dict[str, Any],
    *,
    candidate: str,
    candidate_judgment: str,
    direct: bool,
) -> tuple[str | None, str]:
    evidence_relation = payload.get("evidence_relation")
    if evidence_relation not in {
        "proposition_support",
        "explicit_contradiction",
        "undetermined",
    }:
        return None, "evidence_relation_invalid"
    expected_relation = {
        "proposition_support": "yes",
        "explicit_contradiction": "no",
        "undetermined": "insufficient_evidence",
    }[str(evidence_relation)]
    normalized_candidate = str(candidate or "").strip().casefold()
    if direct and normalized_candidate:
        if normalized_candidate == "unanswerable":
            if candidate_judgment != "contradicted":
                verdict = "insufficient_evidence"
            elif evidence_relation == "undetermined":
                return None, "candidate_judgment_relation_mismatch"
            else:
                verdict = expected_relation
        elif candidate_judgment == "unknown":
            verdict = "insufficient_evidence"
        else:
            verdict = _verdict_for_candidate_judgment(
                normalized_candidate,
                candidate_judgment,
            )
        if expected_relation != verdict:
            return None, "candidate_judgment_relation_mismatch"
    else:
        verdict = expected_relation
    return str(verdict), ""


def _proof_payload(
    payload: dict[str, Any],
    *,
    verdict: str,
) -> tuple[str | None, list[Any] | None, str]:
    proof_mode = payload.get("proof_mode")
    if proof_mode not in {
        "none",
        "atomic_semantic",
        "composite_conjunction",
    }:
        return None, None, "proof_mode_invalid"
    if not isinstance(payload.get("jointly_complete"), bool) or not isinstance(
        payload.get("each_premise_required"), bool
    ):
        return None, None, "entailment_flags_invalid"
    raw_premises = payload.get("premises")
    if not isinstance(raw_premises, list) or len(raw_premises) > 4:
        return None, None, "premise_collection_invalid"
    expected_count = {
        "atomic_semantic": (1, 1),
        "composite_conjunction": (2, 4),
    }.get(str(proof_mode))
    if verdict in {"yes", "no"} and (
        expected_count is None
        or not expected_count[0] <= len(raw_premises) <= expected_count[1]
        or payload["jointly_complete"] is not True
        or payload["each_premise_required"] is not True
    ):
        return None, None, "verdict_payload_inconsistent"
    if verdict == "insufficient_evidence" and (
        raw_premises
        or proof_mode != "none"
        or payload["jointly_complete"] is not False
        or payload["each_premise_required"] is not False
    ):
        return None, None, "verdict_payload_inconsistent"
    return str(proof_mode), raw_premises, ""


def _candidate_judgment_projection_valid(
    candidate: str,
    candidate_judgment: str,
    verdict: str,
) -> bool:
    candidate = str(candidate or "").strip().casefold()
    if not candidate:
        return True
    if verdict == "insufficient_evidence":
        expected = (
            {"supported", "unknown"} if candidate == "unanswerable" else {"unknown"}
        )
        return candidate_judgment in expected
    return candidate_judgment != "unknown"


def _verdict_payload(
    payload: Any,
    *,
    candidate: str = "",
) -> tuple[str | None, str | None, str | None, list[Any] | None, str]:
    return _verdict_payload_for_candidate(payload, candidate=candidate)


def _candidate_judgment_for_verdict(candidate: str, verdict: str) -> str:
    candidate = str(candidate or "").strip().casefold()
    verdict = str(verdict or "").strip().casefold()
    if verdict == "insufficient_evidence":
        return "supported" if candidate == "unanswerable" else "unknown"
    if candidate == "unanswerable":
        return "contradicted"
    if candidate == verdict:
        return "supported"
    return "contradicted"


def _verdict_for_candidate_judgment(candidate: str, judgment: str) -> str:
    candidate = str(candidate or "").strip().casefold()
    judgment = str(judgment or "").strip().casefold()
    if judgment == "unknown" or candidate == "unanswerable":
        return "insufficient_evidence"
    if judgment == "supported":
        return candidate
    return "no" if candidate == "yes" else "yes"


def _parse_premises(
    raw_premises: list[Any],
    selector_lookup: dict[str, dict[str, Any]],
    slot_ids: set[str],
) -> tuple[list[dict[str, Any]] | None, str]:
    premises: list[dict[str, Any]] = []
    for raw in raw_premises:
        if not isinstance(raw, dict) or set(raw) != {
            "span_selector",
            "proposition_fragment",
            "supports_slot_ids",
            "binds_proposition_slots",
        }:
            return None, "premise_schema_invalid"
        selector_id = str(raw.get("span_selector") or "")
        selector = selector_lookup.get(selector_id)
        fragment = raw.get("proposition_fragment")
        supports = raw.get("supports_slot_ids")
        proposition_slots = raw.get("binds_proposition_slots")
        if selector is None or not isinstance(fragment, str):
            return None, "premise_value_invalid"
        if (
            not isinstance(supports, list)
            or not supports
            or any(
                not isinstance(value, str) or value not in slot_ids
                for value in supports
            )
            or len(set(supports)) != len(supports)
        ):
            return None, "premise_slot_binding_invalid"
        if (
            not isinstance(proposition_slots, list)
            or not proposition_slots
            or any(
                value not in PROPOSITION_EVIDENCE_SLOTS for value in proposition_slots
            )
            or len(set(proposition_slots)) != len(proposition_slots)
        ):
            return None, "premise_proposition_binding_invalid"
        premises.append(
            {
                "evidence_id": str(selector["evidence_id"]),
                "span_selector": selector_id,
                "quote": str(selector["text"]),
                "span_start": int(selector["span_start"]),
                "span_end": int(selector["span_end"]),
                "canonical_start": selector.get("canonical_start"),
                "canonical_end": selector.get("canonical_end"),
                "proposition_fragment": fragment,
                "supports_slot_ids": list(supports),
                "binds_proposition_slots": list(proposition_slots),
            }
        )
    premise_spans = {value["span_selector"] for value in premises}
    if len(premise_spans) != len(premises):
        return None, "premise_span_duplicate"
    return premises, ""


def _parse_unknown_assessment(
    value: Any,
    selector_lookup: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(value, dict) or set(value) != {
        "reviewed_span_selectors",
        "unresolved_proposition_slots",
        "support_gap",
        "contradiction_gap",
    }:
        return None, "unknown_assessment_schema_invalid"
    selectors = value.get("reviewed_span_selectors")
    unresolved = value.get("unresolved_proposition_slots")
    support_gap = str(value.get("support_gap") or "").strip()
    contradiction_gap = str(value.get("contradiction_gap") or "").strip()
    if (
        not isinstance(selectors, list)
        or not selectors
        or len(selectors) > 12
        or len(set(selectors)) != len(selectors)
        or any(selector not in selector_lookup for selector in selectors)
    ):
        return None, "unknown_assessment_evidence_invalid"
    if (
        not isinstance(unresolved, list)
        or not unresolved
        or len(set(unresolved)) != len(unresolved)
        or any(slot not in PROPOSITION_EVIDENCE_SLOTS for slot in unresolved)
    ):
        return None, "unknown_assessment_slot_invalid"
    if (
        not support_gap
        or not contradiction_gap
        or len(support_gap) > 320
        or len(contradiction_gap) > 320
    ):
        return None, "unknown_assessment_gap_invalid"
    reviewed = [
        {
            "span_selector": selector,
            "evidence_id": str(selector_lookup[selector]["evidence_id"]),
            "quote": str(selector_lookup[selector]["text"]),
            "span_start": int(selector_lookup[selector]["span_start"]),
            "span_end": int(selector_lookup[selector]["span_end"]),
        }
        for selector in selectors
    ]
    return {
        "reviewed_span_selectors": list(selectors),
        "reviewed_evidence": reviewed,
        "unresolved_proposition_slots": list(unresolved),
        "support_gap": support_gap,
        "contradiction_gap": contradiction_gap,
    }, ""
