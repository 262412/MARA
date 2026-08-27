from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any

_QUESTION = "Did the authors release the code for the evaluated system?"
_JUDGMENTS = ("supported", "contradicted", "unknown")
_AUDITOR_STATUSES = ("passed", "failed")
_CANDIDATES = ("yes", "no", "unanswerable")


@dataclass(frozen=True)
class ProbeCase:
    case_id: str
    evidence: str
    expected_candidate: str
    expected_judgment: str
    expected_audit_status: str
    expected_negative: bool = False
    controlled_fault: str = ""
    controlled_candidate: str = ""
    # A rejected supported proof is projected to final verifier judgment
    # ``unknown`` by the production transaction.  Keep that terminal
    # observation distinct from the proposal sent to the auditor.
    proposal_judgment: str = ""
    # Optional negative fixtures exercise the proposal contract before any
    # auditor request. They stay outside ``_PROBE_CASES`` so the live
    # heterogeneous-provider state matrix remains an online-only gate.
    question: str = _QUESTION
    evidence_element_type: str = ""
    payload_fixture: str = ""
    pre_audit_reasons: tuple[str, ...] = ()


# These are evidence/control inputs only.  No trace, authority, or terminal
# field is copied from these expectations into a row.
_PROBE_CASES: tuple[ProbeCase, ...] = (
    ProbeCase(
        "supported_yes",
        "The authors released the code for the evaluated system.",
        "yes",
        "supported",
        "passed",
    ),
    ProbeCase(
        "supported_no",
        "The authors did not release the code for the evaluated system.",
        "no",
        "supported",
        "passed",
    ),
    ProbeCase(
        "contradicted_yes",
        "The authors did not release the code for the evaluated system.",
        "yes",
        "contradicted",
        "passed",
        expected_negative=True,
        controlled_candidate="yes",
    ),
    ProbeCase(
        "contradicted_no",
        "The authors released the code for the evaluated system.",
        "no",
        "contradicted",
        "passed",
        expected_negative=True,
        controlled_candidate="no",
    ),
    ProbeCase(
        "unknown_audited",
        (
            "The paper reports the evaluation dataset and metrics, but it does "
            "not state whether the authors released code for the evaluated system."
        ),
        "yes",
        "unknown",
        "passed",
        expected_negative=True,
        controlled_candidate="yes",
    ),
    ProbeCase(
        "auditor_fail",
        (
            "The authors released code for a different baseline, but this sentence "
            "does not establish release for the evaluated system."
        ),
        "yes",
        "unknown",
        "failed",
        expected_negative=True,
        controlled_fault="non_entailing_proof",
        proposal_judgment="supported",
        controlled_candidate="yes",
    ),
)


# These payload fixtures are derived from natural evidence-quality failures.
# They are negative contract probes, not benchmark labels or gold answers.
_NATURAL_QUALITY_PRE_AUDIT_CASES: tuple[ProbeCase, ...] = (
    ProbeCase(
        "natural_overdeclared_actor_quantifier",
        "The authors released the code for the evaluated system.",
        "",
        "pre_audit_failed",
        "not_started",
        expected_negative=True,
        payload_fixture="proposer_over_declares_actor_quantifier",
        pre_audit_reasons=("premise_proposition_binding_invalid",),
    ),
    ProbeCase(
        "natural_title_only_relation_object_binding",
        "Code Release",
        "",
        "pre_audit_failed",
        "not_started",
        expected_negative=True,
        controlled_candidate="yes",
        evidence_element_type="title",
        payload_fixture="title_only_span_binds_relation_object",
        pre_audit_reasons=(
            "local_semantic_relation_mention_only",
            "local_semantic_slot_span_unbound",
            "pre_audit_slot_evidence_mismatch",
        ),
    ),
    ProbeCase(
        "natural_slot_expectation_evidence_mismatch",
        "The authors released it.",
        "",
        "pre_audit_failed",
        "not_started",
        expected_negative=True,
        controlled_candidate="yes",
        payload_fixture="proposer_slot_expectations_differ_from_verified_slot_evidence",
        pre_audit_reasons=(
            "local_semantic_slot_span_unbound",
            "local_semantic_slot_coverage_incomplete",
            "pre_audit_slot_evidence_mismatch",
        ),
    ),
    ProbeCase(
        "natural_duplicate_unknown_assessment_slots",
        (
            "The paper reports the evaluation dataset and metrics, but it does "
            "not state whether the authors released code for the evaluated system."
        ),
        "",
        "pre_audit_failed",
        "not_started",
        expected_negative=True,
        payload_fixture="unknown_assessment_duplicate_unresolved_slots",
        pre_audit_reasons=("unknown_assessment_slot_invalid",),
    ),
)

NATURAL_QUALITY_PRE_AUDIT_CASES = _NATURAL_QUALITY_PRE_AUDIT_CASES


def _digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_request_and_bundle(case: ProbeCase, index: int) -> tuple[Any, Any]:
    from ktem.docqa._runtime_models import DocQARequest
    from ktem.docqa.evidence_identity import identity_of
    from ktem.docqa.evidence_schema import EvidenceBundle, EvidenceElement
    from ktem.docqa.query_planning import build_query_plan
    from ktem.reasoning.mara_qasper_candidate_identity import (
        candidate_transaction_identity,
    )

    plan = build_query_plan(
        case.question,
        answer_type="boolean",
        verification_domain="qasper",
    )
    item = EvidenceElement(
        evidence_id=f"{case.case_id}-evidence",
        source_id=f"contract-probe-{case.case_id}",
        source_name="QASPER live contract probe evidence",
        span_id=f"{case.case_id}-span",
        element_id=f"{case.case_id}-element",
        page_label="1",
        chunk_start=0,
        chunk_end=len(case.evidence),
        evidence_level="span",
        text=case.evidence,
    ).as_dict()
    if case.evidence_element_type:
        item["element_type"] = case.evidence_element_type
    evidence_key = identity_of(item).key
    bound_slots = tuple(
        replace(slot, status="filled", evidence_ids=(evidence_key,))
        for slot in plan.evidence_slots
    )
    plan = replace(plan, evidence_slots=bound_slots)
    request = DocQARequest(
        prompt=case.question,
        controller_question=case.question,
        retrieval_query=case.question,
        dataset_family="qasper",
        task_type="boolean",
        answer_type="boolean",
        origin="benchmark",
        verification_domain="qasper",
        verification_mode="strict",
        route_policy="contract_probe",
        allowed_routes=["contract_probe"],
        query_plan=plan,
        planned_query_plan=plan,
        generation_seed=20260824 + index,
        trace_context={"contract_probe_case_id": case.case_id},
    )
    assert request.generation_seed is not None
    request.trace_context["trace_group_id"] = candidate_transaction_identity(
        request,
        "contract_probe",
        int(request.generation_seed),
    )["trace_group_id"]
    if case.controlled_candidate:
        request.trace_context["contract_probe_original_candidate"] = (
            case.controlled_candidate
        )
    bundle = EvidenceBundle(
        route="contract_probe",
        items=[item],
        metadata={
            "contract_probe_case_id": case.case_id,
            "contract_probe_evidence_digest": _digest(item),
        },
    )
    if case.payload_fixture:
        bundle.metadata["contract_probe_payload_fixture"] = case.payload_fixture
    if case.controlled_fault:
        bundle.metadata["contract_probe_controlled_proposal"] = {
            "contract_id": "qasper_controlled_verifier_negative_probe.v1",
            "fault": case.controlled_fault,
            "candidate_judgment": case.proposal_judgment,
            "evidence_relation": "proposition_support",
        }
    return request, bundle
