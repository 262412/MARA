from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from .boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
)
from .question_proposition import (
    applicable_proposition_evidence_slots,
    build_question_proposition,
    typed_conclusion,
    validate_candidate_typed_conclusion,
    validate_question_proposition,
    validate_typed_conclusion,
)
from .semantic_entailment_audit import semantic_entailment_audit_validation_reason


def validated_semantic_header(
    response: Mapping[str, Any],
    question: str,
    *,
    release_mode: bool,
) -> tuple[tuple[str, dict[str, Any]] | None, str]:
    verdict, proof_mode, premises, shape_reason = _semantic_response_shape(response)
    if shape_reason:
        return None, shape_reason
    proposition = build_question_proposition(question)
    question_reason = validate_question_proposition(
        response.get("question_proposition"), question
    )
    if question_reason:
        return None, question_reason
    conclusion = (
        typed_conclusion(proposition, verdict) if verdict in {"yes", "no"} else None
    )
    if conclusion is not None:
        if "unknown_assessment" in response:
            return None, "unexpected_unknown_assessment"
        conclusion_reason = validate_typed_conclusion(
            response.get("typed_conclusion"), proposition, verdict
        )
        if conclusion_reason:
            return None, conclusion_reason
    else:
        unknown_reason = _candidate_unknown_audit_validation_reason(
            response,
            proposition,
        )
        if unknown_reason:
            return None, unknown_reason
    verifier = response.get("verifier")
    if not isinstance(verifier, Mapping):
        return None, "semantic_verifier_attestation_missing"
    if verifier.get("release_mode") is not release_mode:
        return None, "semantic_release_mode_binding_invalid"
    if conclusion is not None:
        audit_reason = semantic_entailment_audit_validation_reason(
            question,
            verdict,
            premises,
            response.get("entailment_audit"),
            proof_mode=proof_mode,
            proposition=proposition,
            conclusion=conclusion,
            release_mode=release_mode,
        )
        if audit_reason:
            return None, audit_reason
    model = str(verifier.get("model") or "").strip()
    if verifier.get("contract_id") != GROUNDED_SEMANTIC_VERIFIER_CONTRACT or not model:
        return None, "semantic_verifier_attestation_invalid"
    return (
        verdict,
        _verifier_attestation(
            response,
            verifier,
            verdict=verdict,
            proof_mode=proof_mode,
            proposition=proposition.as_dict(),
            conclusion=conclusion.as_dict() if conclusion is not None else {},
            release_mode=release_mode,
        ),
    ), ""


def _semantic_response_shape(
    response: Mapping[str, Any],
) -> tuple[str, str, list[Mapping[str, Any]], str]:
    if response.get("contract_id") != SEMANTIC_PROPOSITION_VERDICT_CONTRACT:
        return "", "", [], "semantic_verdict_contract_mismatch"
    verdict = str(response.get("verdict") or "")
    if verdict not in {"yes", "no", "insufficient_evidence"}:
        return "", "", [], "semantic_verdict_invalid"
    if response.get("support_mode") != "evidence_set":
        return "", "", [], "semantic_support_mode_invalid"
    expected_relation = {
        "yes": "proposition_support",
        "no": "explicit_contradiction",
        "insufficient_evidence": "undetermined",
    }[verdict]
    if response.get("evidence_relation") != expected_relation:
        return "", "", [], "semantic_evidence_relation_invalid"
    proof_mode = str(response.get("proof_mode") or "")
    raw_premises = response.get("premises")
    premises = (
        [value for value in raw_premises if isinstance(value, Mapping)]
        if isinstance(raw_premises, list)
        else []
    )
    expected_count = {
        "atomic_semantic": (1, 1),
        "composite_conjunction": (2, 4),
    }.get(proof_mode)
    if verdict in {"yes", "no"} and (
        expected_count is None
        or not expected_count[0] <= len(premises) <= expected_count[1]
    ):
        return "", "", [], "semantic_proof_mode_invalid"
    if verdict == "insufficient_evidence" and (proof_mode != "none" or premises):
        return "", "", [], "semantic_proof_mode_invalid"
    if verdict in {"yes", "no"} and (
        response.get("jointly_complete") is not True
        or response.get("each_premise_required") is not True
    ):
        return "", "", [], "semantic_joint_entailment_incomplete"
    return verdict, proof_mode, premises, ""


def _candidate_unknown_audit_validation_reason(
    response: Mapping[str, Any],
    proposition: Any,
) -> str:
    candidate = str(response.get("verifier_input_candidate") or "").casefold()
    if candidate not in {"yes", "no", "unanswerable"}:
        return "candidate_unknown_input_invalid"
    judgment = "unknown"
    if (
        response.get("candidate_verification_status") != judgment
        or response.get("replacement_candidate_allowed") is not False
    ):
        return "candidate_unknown_relationship_invalid"
    audited_conclusion = response.get("audited_typed_conclusion")
    conclusion_reason = validate_candidate_typed_conclusion(
        audited_conclusion,
        proposition,
        candidate,
    )
    if conclusion_reason:
        return conclusion_reason
    assessment = response.get("unknown_assessment")
    if not isinstance(assessment, Mapping):
        return "candidate_unknown_assessment_missing"
    reviewed = assessment.get("reviewed_evidence")
    unresolved = assessment.get("unresolved_proposition_slots")
    support_gap = str(assessment.get("support_gap") or "").strip()
    contradiction_gap = str(assessment.get("contradiction_gap") or "").strip()
    audited_premises, audited_premise_digest = _unknown_audit_premises(reviewed)
    if not audited_premises:
        return "candidate_unknown_reviewed_evidence_missing"
    if (
        not isinstance(unresolved, list)
        or not unresolved
        or len(set(unresolved)) != len(unresolved)
        or any(
            slot not in set(applicable_proposition_evidence_slots(proposition))
            for slot in unresolved
        )
    ):
        return "candidate_unknown_unresolved_slots_invalid"
    if not support_gap or not contradiction_gap:
        return "candidate_unknown_gap_missing"
    audit = response.get("candidate_verification_audit")
    if not isinstance(audit, Mapping):
        return "candidate_unknown_audit_missing"
    expected_reviewed_ids = [str(item["evidence_id"]) for item in audited_premises]
    if (
        audit.get("contract_id") != "candidate_verifier_audit.v2"
        or audit.get("status") != "passed"
        or audit.get("mode") != "candidate_bound_unknown_audit"
        or audit.get("audited_candidate") != candidate
        or audit.get("audited_verdict") != "insufficient_evidence"
        or audit.get("audited_judgment") != judgment
        or audit.get("classification") != "unknown"
        or audit.get("audit_scope") != "original_candidate_and_verifier_unknown_only"
        or dict(audit.get("audited_typed_conclusion") or {})
        != dict(audited_conclusion or {})
        or list(audit.get("audited_premises") or []) != audited_premises
        or audit.get("audited_premise_digest") != audited_premise_digest
        or list(audit.get("reviewed_evidence_ids") or []) != expected_reviewed_ids
        or list(audit.get("unresolved_proposition_slots") or []) != list(unresolved)
        or audit.get("support_gap") != support_gap
        or audit.get("contradiction_gap") != contradiction_gap
        or audit.get("replacement_candidate_allowed") is not False
        or audit.get("reason") != "unknown_gap_audited"
    ):
        return "candidate_unknown_audit_binding_invalid"
    return ""


def _unknown_audit_premises(value: Any) -> tuple[list[dict[str, Any]], str]:
    if not isinstance(value, list) or not value:
        return [], ""
    premises: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            return [], ""
        premise = {
            "span_selector": str(item.get("span_selector") or ""),
            "evidence_id": str(item.get("evidence_id") or ""),
            "quote": str(item.get("quote") or ""),
            "span_start": item.get("span_start"),
            "span_end": item.get("span_end"),
        }
        if (
            not premise["span_selector"]
            or not premise["evidence_id"]
            or not premise["quote"]
            or not isinstance(premise["span_start"], int)
            or not isinstance(premise["span_end"], int)
            or premise["span_end"] <= premise["span_start"]
        ):
            return [], ""
        premises.append(premise)
    canonical = json.dumps(premises, sort_keys=True, separators=(",", ":"))
    return premises, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _verifier_attestation(
    response: Mapping[str, Any],
    verifier: Mapping[str, Any],
    *,
    verdict: str,
    proof_mode: str,
    proposition: dict[str, Any],
    conclusion: dict[str, Any],
    release_mode: bool,
) -> dict[str, Any]:
    return {
        "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
        "verdict_contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "model": str(verifier.get("model") or "").strip(),
        "seed": verifier.get("seed"),
        "verdict": verdict,
        "jointly_complete": response.get("jointly_complete") is True,
        "each_premise_required": response.get("each_premise_required") is True,
        "proof_mode": proof_mode,
        "question_proposition": proposition,
        "typed_conclusion": conclusion,
        "semantic_pack_digest": str(verifier.get("semantic_pack_digest") or ""),
        "auditor_relationship": str(verifier.get("auditor_relationship") or ""),
        "release_mode": release_mode,
        "entailment_audit": dict(response.get("entailment_audit") or {}),
    }
