from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from benchmark.artifact_publication import atomic_write_text
from scripts.slurm.qasper_debug_contract_probe_cases import (
    _AUDITOR_STATUSES,
    _CANDIDATES,
    _JUDGMENTS,
    _PROBE_CASES,
    ProbeCase,
)
from scripts.slurm.qasper_debug_contract_probe_pre_audit import (  # noqa: F401
    _assert_pre_audit_case,
)

_MODEL_CONTRACT = "qasper_contract_probe_live_model.v3"


def _terminal_snapshot(execution: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    terminal_commit = deepcopy(execution.engine_terminal_commit)
    terminal_metadata = deepcopy(
        execution.engine_terminal_evidence_bundle.get("metadata") or {}
        if isinstance(execution.engine_terminal_evidence_bundle, dict)
        else {}
    )
    return terminal_commit, terminal_metadata


def _probe_annotation(
    case: ProbeCase,
    candidate: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    annotation = {
        "annotation_id": f"contract-probe:{case.case_id}",
        "yes_no": candidate.strip().casefold() == "yes",
    }
    example_metadata = {
        "qasper_answer_annotations": [annotation],
        "quality_lane_excluded": True,
        "contract_probe_case": {
            "case_id": case.case_id,
            "expected_candidate": case.expected_candidate,
            "expected_judgment": case.expected_judgment,
            "expected_audit_status": case.expected_audit_status,
            "expected_negative": case.expected_negative,
            "controlled_fault": case.controlled_fault,
            "proposal_judgment": case.proposal_judgment or case.expected_judgment,
            "payload_fixture": case.payload_fixture,
        },
    }
    annotation_scores = {
        "annotation_id": annotation["annotation_id"],
        "contract_id": "qasper_annotation_score.v1",
        "annotation_index": 1,
        "answer_f1": 0.0,
        "typed_accuracy": 0.0,
        "evidence_f1": 0.0,
        "ambiguity_marker": "",
    }
    diagnostics = {
        "contract_id": "qasper_annotation_diagnostics.v1",
        "annotation_count": 1,
        "ambiguous": False,
        "ambiguity_reasons": [],
        # This probe annotation records candidate-label coverage, not a
        # benchmark gold answer or the terminal abstention projection.
        "canonical_answer_classes": [[candidate]],
    }
    return example_metadata, {
        "annotation": annotation,
        "score": annotation_scores,
        "diagnostics": diagnostics,
    }


def _prediction_row(
    case: ProbeCase,
    generation_candidate: str,
    verifier_candidate: str,
    execution: Any,
    live_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    terminal_commit, terminal_metadata = _terminal_snapshot(execution)
    example_metadata, annotation_data = _probe_annotation(case, verifier_candidate)
    example_metadata["contract_probe_case"].update(
        {
            "generator_candidate": generation_candidate,
            "controlled_candidate": case.controlled_candidate,
        }
    )
    # Annotation/score fields make the row consumable by existing observability
    # readers, but the row is explicitly excluded from quality denominators.
    return {
        "contract_id": _MODEL_CONTRACT,
        "example_id": f"contract-probe-{case.case_id}",
        "route": "contract_probe",
        "qasper_debug_lane": "contract_probe",
        "quality_lane_excluded": True,
        "question": case.question,
        "answer_type": "boolean",
        "predicted_answer": verifier_candidate,
        "answer_for_scoring": verifier_candidate,
        "gold_answers": [],
        "raw_generated_answer": generation_candidate,
        "engine_terminal_answer": execution.engine_terminal_answer,
        "engine_terminal_state": deepcopy(execution.engine_terminal_state),
        "engine_verify_decision": deepcopy(execution.engine_verify_decision),
        "engine_terminal_guardrail_decision": deepcopy(
            execution.engine_terminal_guardrail_decision
        ),
        "engine_terminal_evidence_bundle": deepcopy(
            execution.engine_terminal_evidence_bundle
        ),
        "engine_terminal_projection_hash": execution.engine_terminal_projection_hash,
        "engine_terminal_commit": terminal_commit,
        "terminal_outcome": str(terminal_commit.get("outcome") or ""),
        "terminal_outcome_reason": str(terminal_commit.get("reason") or ""),
        "terminal_outcome_contract_violation": bool(
            terminal_commit.get("contract_violation") is True
        ),
        "terminal_semantic_commit": terminal_commit,
        "controller_decision": execution.controller_decision.as_dict(),
        "controller_trace": deepcopy(execution.controller_trace),
        "retrieve_decision": execution.retrieve_decision.as_dict(),
        "verify_decision": execution.verify_decision.as_dict(),
        "guardrail_decision": execution.guardrail_decision.as_dict(),
        "evidence_bundle": execution.evidence_bundle.as_dict(),
        "evidence_metadata": terminal_metadata,
        "contract_probe_live_calls": live_calls,
        "contract_probe_provider_identities": terminal_metadata.get(
            "contract_probe_provider_identities", {}
        ),
        "controlled_input": {
            "mode": "controlled_original_candidate"
            if case.controlled_candidate
            else "none",
            "generator_candidate": generation_candidate,
            "original_candidate": verifier_candidate,
            "evidence_switch": case.controlled_fault or "none",
            "payload_fixture": case.payload_fixture or "none",
            "quality_failure": False,
        },
        "contract_probe_expectation": (
            "auditor_fail" if case.controlled_fault else case.case_id
        ),
        "expected_negative_probe": case.expected_negative,
        "example_metadata": example_metadata,
        "qasper_annotation_scores": [annotation_data["score"]],
        "qasper_annotation_diagnostics": annotation_data["diagnostics"],
    }


def _trace_from_row(row: dict[str, Any], key: str) -> dict[str, Any]:
    metadata = row.get("evidence_metadata")
    value = metadata.get(key) if isinstance(metadata, dict) else None
    if not isinstance(value, dict):
        raise RuntimeError(f"{row.get('example_id')}: missing production trace {key}")
    return value


def _normalized_provider_identity(base_url: Any, model: Any) -> tuple[str, str]:
    return (
        str(base_url or "").strip().rstrip("/").casefold(),
        str(model or "").strip().casefold(),
    )


def _provider_identity_summary_violations(
    row: dict[str, Any],
    observed: dict[str, set[tuple[str, str]]],
) -> list[str]:
    metadata = row.get("evidence_metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    recorded = metadata.get("contract_probe_provider_identities")
    if not isinstance(recorded, dict):
        return ["provider_identity_summary_missing"]
    violations: list[str] = []
    for role in ("proposer", "auditor"):
        role_values = recorded.get(role)
        if not isinstance(role_values, list) or len(role_values) != 1:
            violations.append(f"provider_identity_summary_{role}_invalid")
            continue
        value = role_values[0]
        if not isinstance(value, dict):
            violations.append(f"provider_identity_summary_{role}_invalid")
            continue
        if (
            _normalized_provider_identity(value.get("base_url"), value.get("model"))
            not in observed[role]
        ):
            violations.append(f"provider_identity_summary_{role}_mismatch")
    return violations


def _provider_identity_violations(row: dict[str, Any]) -> list[str]:
    """Validate recorded proposer/auditor identities and runtime separation."""

    violations: list[str] = []
    calls = row.get("contract_probe_live_calls")
    if not isinstance(calls, list) or not calls:
        return ["provider_identity_calls_missing"]
    observed: dict[str, set[tuple[str, str]]] = {
        "proposer": set(),
        "auditor": set(),
    }
    for index, call in enumerate(calls):
        if not isinstance(call, dict):
            violations.append(f"provider_identity_call_invalid:{index}")
            continue
        role = str(call.get("provider_role") or "").strip().casefold()
        if role not in observed:
            violations.append(f"provider_identity_role_invalid:{index}")
            continue
        base_url = str(call.get("base_url") or "").strip()
        model = str(call.get("model") or "").strip()
        identity = call.get("provider_identity")
        if not base_url or not model:
            violations.append(f"provider_identity_fields_missing:{index}")
            continue
        normalized = _normalized_provider_identity(base_url, model)
        observed[role].add(normalized)
        if not isinstance(identity, dict):
            violations.append(f"provider_identity_declaration_missing:{index}")
        elif (
            _normalized_provider_identity(
                identity.get("base_url"), identity.get("model")
            )
            != normalized
            or str(identity.get("role") or "").casefold() != role
        ):
            violations.append(f"provider_identity_declaration_mismatch:{index}")

    for role in ("proposer", "auditor"):
        if not observed[role]:
            violations.append(f"provider_identity_{role}_missing")
        elif len(observed[role]) != 1:
            violations.append(f"provider_identity_{role}_not_stable")
    if observed["proposer"] and observed["auditor"]:
        proposer_models = {model for _, model in observed["proposer"]}
        auditor_models = {model for _, model in observed["auditor"]}
        if proposer_models & auditor_models:
            violations.append("provider_identity_same_model")

    violations.extend(_provider_identity_summary_violations(row, observed))

    try:
        verifier = _trace_from_row(row, "semantic_proposition_verifier")
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as exc:
        violations.append(
            f"provider_identity_verifier_trace_missing:{type(exc).__name__}"
        )
        return violations
    if verifier.get("auditor_relationship") != "distinct_model":
        violations.append("provider_identity_auditor_relationship_not_distinct_model")
    proposer_models = {model for _, model in observed["proposer"]}
    auditor_models = {model for _, model in observed["auditor"]}
    trace_model = str(verifier.get("model") or "").strip().casefold()
    trace_audit_model = str(verifier.get("audit_model") or "").strip().casefold()
    if not trace_model or trace_model not in proposer_models:
        violations.append("provider_identity_proposer_trace_mismatch")
    if not trace_audit_model or trace_audit_model not in auditor_models:
        violations.append("provider_identity_auditor_trace_mismatch")
    return violations


_SEMANTIC_AUDIT_BOOLEAN_FIELDS = frozenset(
    {
        "fragment_entailed",
        "scope_consistent",
        "proposition_bindings_valid",
        "evidence_relation_valid",
        "binding_valid",
        "jointly_entails",
        "each_premise_required",
        "contradiction_free",
        "conclusion_entailed",
        "actor_consistent",
        "predicate_consistent",
        "object_consistent",
        "polarity_consistent",
        "quantifier_consistent",
    }
)


def _accepted_semantic_auditor_rejection(row: dict[str, Any]) -> bool:
    """Require a parsed audit payload with an explicit semantic rejection."""

    verifier = _trace_from_row(row, "semantic_proposition_verifier")
    if (
        verifier.get("audit_parser_accepted") is not True
        or verifier.get("audit_semantic_rejection") is not True
        or verifier.get("audit_status") != "rejected"
    ):
        return False
    debug = verifier.get("debug_trace")
    events = debug.get("events") if isinstance(debug, dict) else []
    transactions = [
        event
        for event in events or []
        if isinstance(event, dict) and event.get("event") == "model_transaction"
    ]
    if not transactions:
        return False
    transaction = transactions[-1].get("transaction")
    transaction = transaction if isinstance(transaction, dict) else {}
    stage = transaction.get("audit")
    stage = stage if isinstance(stage, dict) else {}
    attempts = stage.get("attempts")
    if (
        stage.get("status") != "parsed"
        or not isinstance(attempts, list)
        or not attempts
    ):
        return False
    final_attempt = attempts[-1]
    if not isinstance(final_attempt, dict):
        return False
    if (
        not isinstance(final_attempt.get("parsed_value"), dict)
        or str(final_attempt.get("parse_failure_reason") or "")
        or str(final_attempt.get("provider_failure_reason") or "")
    ):
        return False
    return _semantic_audit_contains_false_boolean(final_attempt["parsed_value"])


def _semantic_audit_contains_false_boolean(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in _SEMANTIC_AUDIT_BOOLEAN_FIELDS and nested is False:
                return True
            if _semantic_audit_contains_false_boolean(nested):
                return True
    elif isinstance(value, list):
        return any(_semantic_audit_contains_false_boolean(item) for item in value)
    return False


def _observed_state(row: dict[str, Any]) -> tuple[str, str, str]:
    generation = _trace_from_row(row, "qasper_candidate_generation")
    verifier = _trace_from_row(row, "semantic_proposition_verifier")
    del generation
    candidate = str(verifier.get("candidate_label") or "").casefold()
    judgment = str(verifier.get("candidate_verification_status") or "").casefold()
    audit = verifier.get("candidate_verification_audit")
    audit = audit if isinstance(audit, dict) else {}
    audit_status = str(audit.get("status") or "").casefold()
    if audit_status not in _AUDITOR_STATUSES:
        audit_status = (
            "failed"
            if verifier.get("audit_status") in {"failed", "rejected"}
            else audit_status
        )
    return candidate, judgment, audit_status


def _observed_state_evidence(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Project the live states needed to diagnose a failed probe audit.

    This is an observation-only projection.  It does not create verifier or
    terminal state and therefore cannot turn a partial or failed probe into a
    passing row.
    """

    observed_rows: list[dict[str, Any]] = []
    candidates: set[str] = set()
    judgments: set[str] = set()
    auditor_statuses: set[str] = set()
    for row in rows:
        case_id = _probe_case_id(row)
        try:
            candidate, judgment, auditor_status = _observed_state(row)
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as exc:
            observed_rows.append(
                {
                    "example_id": str(row.get("example_id") or ""),
                    "case_id": case_id,
                    "state_error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        candidates.add(candidate)
        judgments.add(judgment)
        auditor_statuses.add(auditor_status)
        observed_rows.append(
            {
                "example_id": str(row.get("example_id") or ""),
                "case_id": case_id,
                "candidate": candidate,
                "judgment": judgment,
                "audit_status": auditor_status,
            }
        )
    return {
        "prediction_count": len(rows),
        "rows": observed_rows,
        "candidate_labels": sorted(candidates),
        "verifier_judgments": sorted(judgments),
        "auditor_statuses": sorted(auditor_statuses),
    }


def _probe_case_id(row: dict[str, Any]) -> str:
    metadata = row.get("example_metadata")
    if not isinstance(metadata, dict):
        return ""
    case = metadata.get("contract_probe_case")
    if not isinstance(case, dict):
        return ""
    return str(case.get("case_id") or "")


def _assert_live_case(case: ProbeCase, row: dict[str, Any]) -> tuple[str, str, str]:
    provider_identity_errors = _provider_identity_violations(row)
    if provider_identity_errors:
        raise RuntimeError(
            f"{case.case_id}: provider heterogeneity contract failed: "
            + ",".join(provider_identity_errors)
        )
    observed = _observed_state(row)
    expected = (
        case.expected_candidate,
        case.expected_judgment,
        case.expected_audit_status,
    )
    if observed != expected:
        raise RuntimeError(
            f"{case.case_id}: provider observed {observed!r}, expected {expected!r}"
        )
    if observed[0] not in _CANDIDATES or observed[1] not in _JUDGMENTS:
        raise RuntimeError(
            f"{case.case_id}: invalid observed production state {observed!r}"
        )
    calls = row.get("contract_probe_live_calls")
    if not isinstance(calls, list) or len(calls) < 3:
        raise RuntimeError(
            f"{case.case_id}: actual model/auditor call evidence is incomplete"
        )
    controlled = row.get("controlled_input")
    if not isinstance(controlled, dict):
        raise RuntimeError(f"{case.case_id}: controlled-input provenance is missing")
    if controlled.get("original_candidate") != observed[0]:
        raise RuntimeError(
            f"{case.case_id}: verifier candidate is not the recorded controlled input"
        )
    if (
        case.controlled_fault
        and controlled.get("evidence_switch") != case.controlled_fault
    ):
        raise RuntimeError(f"{case.case_id}: controlled evidence switch is missing")
    stages = {str(call.get("stage") or "") for call in calls if isinstance(call, dict)}
    if (
        "qasper_typed_candidate" not in stages
        or "semantic_evidence_set_proposition" not in stages
    ):
        raise RuntimeError(
            f"{case.case_id}: candidate/proposal provider calls are missing"
        )
    if not any(
        stage in {"semantic_entailment_audit", "candidate_bound_unknown_audit"}
        for stage in stages
    ):
        raise RuntimeError(f"{case.case_id}: independent auditor call is missing")
    verifier = _trace_from_row(row, "semantic_proposition_verifier")
    if int(verifier.get("audit_model_call_count") or 0) <= 0:
        raise RuntimeError(
            f"{case.case_id}: production verifier recorded no auditor attempt"
        )
    if case.controlled_fault:
        if case.expected_audit_status != "failed":
            raise RuntimeError(f"{case.case_id}: controlled fault must be negative")
        if not _accepted_semantic_auditor_rejection(row):
            raise RuntimeError(
                f"{case.case_id}: auditor failure lacks an accepted semantic auditor rejection"
            )
        commit = row.get("engine_terminal_commit") or {}
        if row.get("engine_terminal_answer") != "unanswerable":
            raise RuntimeError(
                f"{case.case_id}: rejected audit did not abstain at terminal"
            )
        if str(commit.get("outcome") or "") not in {"safe_abstention", "abstain"}:
            raise RuntimeError(
                f"{case.case_id}: rejected audit has unsafe terminal outcome"
            )
    return observed


def _assert_live_coverage(rows: list[dict[str, Any]]) -> None:
    if len(rows) != len(_PROBE_CASES):
        raise RuntimeError(
            f"live contract probe requires {len(_PROBE_CASES)} rows, observed {len(rows)}"
        )
    by_case = {
        str(
            (row.get("example_metadata") or {})
            .get("contract_probe_case", {})
            .get("case_id")
            or ""
        ): row
        for row in rows
    }
    observed_candidates: set[str] = set()
    observed_judgments: set[str] = set()
    observed_audits: set[str] = set()
    for case in _PROBE_CASES:
        row = by_case.get(case.case_id)
        if row is None:
            raise RuntimeError(f"live contract probe missing case {case.case_id}")
        observed = _assert_live_case(case, row)
        observed_candidates.add(observed[0])
        observed_judgments.add(observed[1])
        observed_audits.add(observed[2])
    required = {
        "candidate": {"no"},
        "judgment": {"contradicted", "unknown"},
        "audit": {"passed", "failed"},
    }
    if not required["candidate"] <= observed_candidates:
        raise RuntimeError("live contract probe is missing candidate label no")
    if not required["judgment"] <= observed_judgments:
        raise RuntimeError(
            "live contract probe is missing contradicted or unknown judgment"
        )
    if not required["audit"] <= observed_audits:
        raise RuntimeError(
            "live contract probe is missing passed or failed auditor outcome"
        )


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    atomic_write_text(
        path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
    )
