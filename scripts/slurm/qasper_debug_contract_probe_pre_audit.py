from __future__ import annotations

from typing import Any

from scripts.slurm.qasper_debug_contract_probe_cases import ProbeCase


def _assert_pre_audit_case(case: ProbeCase, row: dict[str, Any]) -> None:
    """Require a negative proposal contract to stop before an auditor call."""

    from scripts.slurm.qasper_debug_contract_probe_artifact import _trace_from_row

    if not case.payload_fixture:
        raise RuntimeError(f"{case.case_id}: pre-audit fixture identity is missing")
    verifier = _trace_from_row(row, "semantic_proposition_verifier")
    if verifier.get("status") != "failed":
        raise RuntimeError(f"{case.case_id}: invalid proposal did not fail")
    if verifier.get("candidate_verification_status") != "pre_audit_failed":
        raise RuntimeError(
            f"{case.case_id}: proposal failure was not marked pre_audit_failed"
        )
    if verifier.get("audit_status") != "not_started":
        raise RuntimeError(f"{case.case_id}: invalid proposal started an audit")
    audit = verifier.get("candidate_verification_audit")
    if not isinstance(audit, dict) or audit.get("status") != "not_started":
        raise RuntimeError(f"{case.case_id}: candidate audit is not not_started")
    if audit.get("classification") != "pre_audit_failed":
        raise RuntimeError(f"{case.case_id}: pre-audit classification is missing")
    if int(verifier.get("audit_model_call_count") or 0) != 0:
        raise RuntimeError(f"{case.case_id}: verifier recorded an auditor call")
    calls = row.get("contract_probe_live_calls")
    if not isinstance(calls, list):
        raise RuntimeError(f"{case.case_id}: provider call evidence is missing")
    auditor_calls = [
        call
        for call in calls
        if isinstance(call, dict)
        and str(call.get("provider_role") or "").casefold() == "auditor"
    ]
    if auditor_calls:
        raise RuntimeError(f"{case.case_id}: actual auditor call count is not zero")
    stages = {str(call.get("stage") or "") for call in calls if isinstance(call, dict)}
    if (
        not {
            "qasper_typed_candidate",
            "semantic_evidence_set_proposition",
        }
        <= stages
    ):
        raise RuntimeError(
            f"{case.case_id}: candidate/proposal call evidence is missing"
        )
    if row.get("engine_terminal_answer") != "unanswerable":
        raise RuntimeError(f"{case.case_id}: pre-audit failure did not abstain")
    commit = row.get("engine_terminal_commit")
    if (
        not isinstance(commit, dict)
        or str(commit.get("outcome") or "") != "execution_failed"
    ):
        raise RuntimeError(
            f"{case.case_id}: pre-audit failure has unsafe terminal outcome"
        )
    if case.pre_audit_reasons:
        observed_reasons = {
            str(verifier.get(field) or "")
            for field in (
                "audit_reason",
                "parse_failure_reason",
                "initial_parse_failure_reason",
                "audit_parse_failure_reason",
                "audit_initial_parse_failure_reason",
            )
        }
        if not observed_reasons.intersection(case.pre_audit_reasons):
            raise RuntimeError(
                f"{case.case_id}: expected pre-audit reason is missing; "
                f"observed {sorted(observed_reasons)}"
            )
