from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ktem.docqa.question_proposition import (
    QuestionProposition,
    candidate_typed_conclusion,
)

# The compact assessment carries each exact selector quote once. Keep the
# original fail-closed request bound so prompt growth cannot silently consume
# the verifier's 4K-token context budget.
UNKNOWN_AUDIT_MAX_PROMPT_CHARS = 8_000
UNKNOWN_AUDIT_MAX_TOKENS = 512
UNKNOWN_AUDIT_SCOPE = "original_candidate_and_verifier_unknown_only"
UNKNOWN_AUDIT_GAP_MAX_CHARS = 192
UNKNOWN_AUDIT_TYPED_CONCLUSION_MISSING = "candidate_unknown_typed_conclusion_missing"
UNKNOWN_AUDIT_REVIEWED_EVIDENCE_MISSING = "candidate_unknown_reviewed_evidence_missing"
UNKNOWN_AUDIT_PROMPT_BOUND_EXCEEDED = "candidate_unknown_audit_prompt_bound_exceeded"

UNKNOWN_AUDIT_SYSTEM_PROMPT = (
    "You are the independent candidate-bound auditor for a verifier uncertainty "
    "judgment. Audit only the original candidate, the verifier's "
    "insufficient_evidence judgment, the deterministic typed candidate conclusion, "
    "and the reviewed evidence-gap assessment. Determine whether the reviewed "
    "evidence truly fails both to establish the candidate proposition and to provide "
    "an explicit contradiction. Do not answer the question, replace the candidate, "
    "or propose another verdict. Empty reviewed evidence or an empty typed conclusion "
    "must fail. Return only the required JSON object."
)


@dataclass(frozen=True)
class CandidateUnknownAuditParse:
    value: dict[str, Any] | None
    failure_reason: str = ""


def candidate_unknown_audit_prompt(
    proposition: QuestionProposition,
    candidate: str,
    unknown_assessment: dict[str, Any],
    *,
    verifier_judgment: str = "",
    semantic_pack_identity: Mapping[str, str] | None = None,
) -> tuple[str, dict[str, Any]]:
    conclusion = candidate_typed_conclusion(proposition, candidate)
    audited_premises = _unknown_audit_premises(unknown_assessment)
    if not conclusion:
        raise ValueError(UNKNOWN_AUDIT_TYPED_CONCLUSION_MISSING)
    if not audited_premises:
        raise ValueError(UNKNOWN_AUDIT_REVIEWED_EVIDENCE_MISSING)
    payload = {
        "audit_scope": UNKNOWN_AUDIT_SCOPE,
        "original_candidate": str(candidate or "").strip().casefold(),
        "verifier_verdict": "insufficient_evidence",
        "verifier_judgment": _candidate_status(candidate, verifier_judgment),
        "replacement_candidate_allowed": False,
        "question_proposition": proposition.as_dict(),
        "audited_typed_conclusion": conclusion,
        "semantic_pack_identity": dict(semantic_pack_identity or {}),
        "audited_premises": audited_premises,
        # The reviewed evidence is carried once, in audited_premises. Keeping
        # the full parser projection here used to duplicate every quote and
        # routinely prevented the real auditor call from being attempted.
        "unknown_assessment": _compact_unknown_assessment(unknown_assessment),
    }
    prompt = "/no_think\nAUDIT THIS VERIFIER UNCERTAINTY:\n" + json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    if len(prompt) > UNKNOWN_AUDIT_MAX_PROMPT_CHARS:
        raise ValueError(UNKNOWN_AUDIT_PROMPT_BOUND_EXCEEDED)
    return prompt, conclusion


def candidate_unknown_audit_response_format(
    candidate: str,
    *,
    verifier_judgment: str = "",
) -> dict[str, Any]:
    judgment = _candidate_status(candidate, verifier_judgment)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "candidate_bound_unknown_audit",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "audit_scope": {"type": "string", "enum": [UNKNOWN_AUDIT_SCOPE]},
                    "audited_candidate": {
                        "type": "string",
                        "enum": [str(candidate or "").strip().casefold()],
                    },
                    "audited_verdict": {
                        "type": "string",
                        "enum": ["insufficient_evidence"],
                    },
                    "audited_judgment": {"type": "string", "enum": [judgment]},
                    "typed_conclusion_present": {"type": "boolean"},
                    "reviewed_evidence_present": {"type": "boolean"},
                    "support_gap_valid": {"type": "boolean"},
                    "contradiction_gap_valid": {"type": "boolean"},
                    "relationship_consistent": {"type": "boolean"},
                    "replacement_candidate_allowed": {
                        "type": "boolean",
                        "enum": [False],
                    },
                    "replacement_candidate": {"type": "string", "enum": [""]},
                },
                "required": [
                    "audit_scope",
                    "audited_candidate",
                    "audited_verdict",
                    "audited_judgment",
                    "typed_conclusion_present",
                    "reviewed_evidence_present",
                    "support_gap_valid",
                    "contradiction_gap_valid",
                    "relationship_consistent",
                    "replacement_candidate_allowed",
                    "replacement_candidate",
                ],
                "additionalProperties": False,
            },
        },
    }


def parse_candidate_unknown_audit(
    response_text: str,
    *,
    candidate: str,
    verifier_judgment: str = "",
) -> CandidateUnknownAuditParse:
    try:
        payload = json.loads(response_text)
    except (TypeError, json.JSONDecodeError):
        return CandidateUnknownAuditParse(None, "json_decode_error")
    required = {
        "audit_scope",
        "audited_candidate",
        "audited_verdict",
        "audited_judgment",
        "typed_conclusion_present",
        "reviewed_evidence_present",
        "support_gap_valid",
        "contradiction_gap_valid",
        "relationship_consistent",
        "replacement_candidate_allowed",
        "replacement_candidate",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        return CandidateUnknownAuditParse(None, "top_level_schema_invalid")
    normalized = str(candidate or "").strip().casefold()
    if (
        payload.get("audit_scope") != UNKNOWN_AUDIT_SCOPE
        or payload.get("audited_candidate") != normalized
        or payload.get("audited_verdict") != "insufficient_evidence"
        or payload.get("audited_judgment")
        != _candidate_status(normalized, verifier_judgment)
        or payload.get("replacement_candidate_allowed") is not False
        or payload.get("replacement_candidate") != ""
    ):
        return CandidateUnknownAuditParse(
            None, "candidate_unknown_audit_binding_invalid"
        )
    boolean_fields = required - {
        "audit_scope",
        "audited_candidate",
        "audited_verdict",
        "audited_judgment",
        "replacement_candidate",
    }
    if any(not isinstance(payload.get(field), bool) for field in boolean_fields):
        return CandidateUnknownAuditParse(None, "candidate_unknown_audit_flags_invalid")
    return CandidateUnknownAuditParse(dict(payload))


def candidate_unknown_audit_rejection_reason(value: dict[str, Any]) -> str:
    for field, reason in (
        ("typed_conclusion_present", "candidate_unknown_typed_conclusion_missing"),
        ("reviewed_evidence_present", "candidate_unknown_reviewed_evidence_missing"),
        ("support_gap_valid", "candidate_unknown_support_gap_rejected"),
        ("contradiction_gap_valid", "candidate_unknown_contradiction_gap_rejected"),
        ("relationship_consistent", "candidate_unknown_relationship_rejected"),
    ):
        if value.get(field) is not True:
            return reason
    return ""


def candidate_unknown_audit_attestation(
    value: dict[str, Any],
    *,
    typed_conclusion_value: dict[str, Any],
    unknown_assessment: dict[str, Any],
) -> dict[str, Any]:
    audited_premises = _unknown_audit_premises(unknown_assessment)
    if not typed_conclusion_value or not audited_premises:
        raise ValueError(
            "Candidate-bound unknown audit cannot attest empty conclusion/evidence."
        )
    return {
        "contract_id": "candidate_verifier_audit.v2",
        "status": "passed",
        "mode": "candidate_bound_unknown_audit",
        "audited_candidate": str(value.get("audited_candidate") or ""),
        "audited_verdict": "insufficient_evidence",
        "audited_judgment": str(value.get("audited_judgment") or ""),
        "classification": "unknown",
        "audit_scope": UNKNOWN_AUDIT_SCOPE,
        "audited_typed_conclusion": dict(typed_conclusion_value),
        "audited_premises": audited_premises,
        "audited_premise_digest": _payload_digest(audited_premises),
        "reviewed_evidence_ids": [
            str(item["evidence_id"]) for item in audited_premises
        ],
        "unresolved_proposition_slots": list(
            unknown_assessment.get("unresolved_proposition_slots") or []
        ),
        "support_gap": str(unknown_assessment.get("support_gap") or ""),
        "contradiction_gap": str(unknown_assessment.get("contradiction_gap") or ""),
        "replacement_candidate_allowed": False,
        "reason": "unknown_gap_audited",
    }


def _candidate_status(candidate: str, verifier_judgment: str = "") -> str:
    del candidate
    supplied = str(verifier_judgment or "").strip().casefold()
    if supplied == "unknown":
        return supplied
    return "unknown"


def _unknown_audit_premises(
    unknown_assessment: dict[str, Any],
) -> list[dict[str, Any]]:
    reviewed = unknown_assessment.get("reviewed_evidence") or []
    premises: list[dict[str, Any]] = []
    for item in reviewed:
        if not isinstance(item, dict):
            continue
        selector = str(item.get("span_selector") or "").strip()
        evidence_id = str(item.get("evidence_id") or "").strip()
        quote = str(item.get("quote") or "")
        start = _optional_int(item.get("span_start"))
        end = _optional_int(item.get("span_end"))
        if not selector or not evidence_id or not quote or start is None or end is None:
            continue
        if start < 0 or end <= start or end - start != len(quote):
            continue
        premises.append(
            {
                "span_selector": selector,
                "evidence_id": evidence_id,
                "quote": quote,
                "span_start": start,
                "span_end": end,
            }
        )
    return premises


def _compact_unknown_assessment(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "unresolved_proposition_slots": [
            str(slot).strip()
            for slot in value.get("unresolved_proposition_slots") or []
            if str(slot).strip()
        ],
        "support_gap": _compact_gap(value.get("support_gap")),
        "contradiction_gap": _compact_gap(value.get("contradiction_gap")),
    }


def _compact_gap(value: Any) -> str:
    return " ".join(str(value or "").split())[:UNKNOWN_AUDIT_GAP_MAX_CHARS]


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _payload_digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
