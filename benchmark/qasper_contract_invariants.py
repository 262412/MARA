from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_alias_lookup import unambiguous_evidence_alias_lookup
from ktem.docqa.evidence_identity import exact_evidence_aliases, identity_of
from ktem.docqa.evidence_locators import normalized_source_page_locators

from .metrics import is_abstention_answer
from .qasper_boolean_scope import scope_valid_support_items
from .qasper_deterministic_support import deterministic_support_ids
from .qasper_semantic_authority_metrics import semantic_evidence_set_authority_invalid
from .qasper_semantic_verifier_metrics import semantic_verifier_failure_metrics


def qasper_contract_metric_values(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    *,
    cited: list[dict[str, Any]],
    contract_items: list[dict[str, Any]],
) -> dict[str, float | None]:
    return {
        **_answerability_metrics(prediction, metadata),
        **_citation_support_metrics(
            prediction,
            metadata,
            cited,
            contract_items=contract_items,
        ),
    }


def _answerability_metrics(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, float | None]:
    trace = metadata.get("qasper_answerability")
    applicable = _qasper_boolean_applicable(prediction, trace)
    if not isinstance(trace, dict) and not applicable:
        return _empty_answerability_metrics()
    trace = trace if isinstance(trace, dict) else {}
    candidate = str(trace.get("candidate_for_answerability") or "")
    answer = _final_answer(prediction)
    scope_violation = bool(
        _answer_type(prediction) == "boolean"
        and answer
        and not is_abstention_answer(answer)
        and str(trace.get("boolean_scope_valid") or "").lower() == "false"
    )
    required_slot_ids = _trace_ids(trace.get("verifier_required_slot_ids"))
    required_evidence_ids = _trace_ids(trace.get("verifier_required_evidence_ids"))
    required_verification_applicable = _required_verification_applicable(
        trace,
        boolean_applicable=applicable,
        answerable=_gold_is_answerable(prediction),
        required_slot_ids=required_slot_ids,
        required_evidence_ids=required_evidence_ids,
    )
    required_coverage = (
        _required_authority_coverage(
            trace,
            required_slot_ids=required_slot_ids,
            required_evidence_ids=required_evidence_ids,
            required_verification_applicable=True,
        )
        if required_verification_applicable
        else None
    )
    authority = _required_authority_metrics(
        trace,
        required_verification_applicable=required_verification_applicable,
    )
    return {
        "abstention_candidate_sent_as_semantic_answer_count": float(
            bool(candidate and is_abstention_answer(candidate))
        ),
        "verifier_required_evidence_coverage": required_coverage,
        "answerable_false_abstention_count": float(
            _gold_is_answerable(prediction) and is_abstention_answer(answer)
        ),
        "boolean_scope_violation_count": float(scope_violation),
        "wrong_polarity_count": float(_wrong_boolean_polarity(prediction, answer)),
        **_runtime_audit_failure_metrics(prediction, trace),
        **authority,
    }


def _runtime_audit_failure_metrics(
    prediction: dict[str, Any],
    trace: dict[str, Any],
) -> dict[str, float]:
    contract_action = str(
        prediction.get("contract_action") or trace.get("contract_action") or ""
    )
    semantic_rewrite = bool(
        prediction.get("contract_semantic_rewrite")
        or trace.get("contract_semantic_rewrite")
    )
    engine_label = str(trace.get("engine_semantic_label") or "")
    scored_label = str(trace.get("scored_semantic_label") or "")
    runtime_failure = str(trace.get("runtime_authority_failure_kind") or "")
    qasper_audited = trace.get("contract_id") == "qasper_runtime_authority_audit.v1"
    return {
        "contract_semantic_rewrite_count": float(semantic_rewrite),
        "engine_scored_semantic_label_mismatch_count": float(
            bool(engine_label and scored_label and engine_label != scored_label)
        ),
        "qasper_invalid_typed_label_count": float(
            bool(trace.get("invalid_typed_label"))
        ),
        "qasper_terminal_state_missing_count": float(
            qasper_audited
            and not isinstance(prediction.get("terminal_answer_state"), dict)
        ),
        "qasper_post_engine_answerability_llm_call_count": float(
            prediction.get("post_engine_answerability_llm_call_count")
            or trace.get("post_engine_answerability_llm_call_count")
            or 0
        ),
        "qasper_runtime_authority_missing_count": float(
            contract_action == "hard_violation_missing_runtime_authority"
            and runtime_failure in {"", "authority_missing"}
        ),
        "qasper_runtime_semantic_verifier_failure_count": float(
            runtime_failure == "semantic_verifier"
        ),
        "qasper_runtime_scope_failure_count": float(runtime_failure == "scope"),
        "qasper_runtime_canonical_identity_mismatch_count": float(
            str(trace.get("runtime_typed_authority_identity_status") or "")
            in {"canonical_identity_unresolved", "canonical_ref_identity_mismatch"}
        ),
        "qasper_runtime_quote_grounding_failure_count": float(
            trace.get("runtime_typed_authority_quote_grounding_status")
            == "quote_semantic_grounding_failure"
        ),
        "qasper_runtime_authority_frame_incomplete_count": float(
            trace.get("runtime_typed_authority_frame_status") == "incomplete"
        ),
        "qasper_composite_authority_count": float(
            trace.get("runtime_typed_authority_kind") == "composite"
            and trace.get("runtime_typed_authority_derivation_status") == "bound"
            and bool(trace.get("runtime_typed_authority_complete"))
        ),
        "qasper_composite_authority_invalid_count": float(
            trace.get("runtime_typed_authority_kind") == "composite"
            and trace.get("runtime_typed_authority_derivation_status") != "bound"
        ),
        "qasper_semantic_evidence_set_authority_count": float(
            trace.get("runtime_typed_authority_kind") == "semantic_evidence_set"
            and trace.get("runtime_typed_authority_derivation_status") == "bound"
            and bool(trace.get("runtime_typed_authority_complete"))
        ),
        "qasper_semantic_evidence_set_authority_invalid_count": float(
            semantic_evidence_set_authority_invalid(trace)
        ),
        "qasper_semantic_proposition_verifier_call_count": float(
            trace.get("runtime_semantic_proposition_verifier_model_call_count") or 0
        ),
        **semantic_verifier_failure_metrics(trace),
    }


def _required_verification_applicable(
    trace: dict[str, Any],
    *,
    boolean_applicable: bool,
    answerable: bool,
    required_slot_ids: list[str],
    required_evidence_ids: list[str],
) -> bool:
    explicit = trace.get("runtime_boolean_authority_applicable")
    if explicit:
        return True
    if trace.get("runtime_typed_authority_applicable") is not None:
        return bool(trace.get("runtime_typed_authority_applicable") and answerable)
    if explicit is not None:
        return bool(explicit)
    return bool(
        boolean_applicable
        or required_slot_ids
        or required_evidence_ids
        or _trace_count(trace.get("verifier_required_slot_count"))
    )


def _required_authority_metrics(
    trace: dict[str, Any],
    *,
    required_verification_applicable: bool,
) -> dict[str, float]:
    if not required_verification_applicable:
        return _not_applicable_authority_metrics()
    slot_ids = _trace_ids(trace.get("verifier_required_slot_ids"))
    required_ids = _trace_ids(trace.get("verifier_required_evidence_ids"))
    missing_ids = _trace_ids(trace.get("verifier_missing_required_slot_ids"))
    status = str(trace.get("verifier_required_authority_status") or "")
    coverage = _required_authority_coverage(
        trace,
        required_slot_ids=slot_ids,
        required_evidence_ids=required_ids,
        required_verification_applicable=required_verification_applicable,
    )
    slot_count = max(
        len(slot_ids),
        _trace_count(trace.get("verifier_required_slot_count")),
    )
    authority_missing = bool(
        slot_count
        and (
            status in {"missing_required_evidence", "required_evidence_not_selected"}
            or (not required_ids and coverage != 1.0)
        )
    )
    missing_count = (
        len(missing_ids) if missing_ids else slot_count if authority_missing else 0
    )
    raw_verdict = str(trace.get("raw_verifier_verdict") or "")
    final_answer = str(trace.get("final_post_contract_answer") or "").strip()
    if not final_answer:
        final_answer = str(trace.get("post_contract_answer") or "").strip()
    complete_abstention = raw_verdict in {
        "yes_complete",
        "no_complete",
    } and is_abstention_answer(final_answer)
    reason = str(trace.get("reason") or "")
    semantic_veto = reason in _SEMANTIC_VETO_REASONS and complete_abstention
    identity_clear = complete_abstention and reason in {
        "quote_identity_unresolved",
        "evidence_ref_unresolved",
    }
    quote_status = str(trace.get("quote_ref_validation_status") or "")
    ref_mismatch = complete_abstention and (
        reason == "evidence_ref_quote_mismatch"
        or quote_status == "evidence_ref_quote_mismatch"
    )
    quote_validation_ref_mismatch = (
        reason == "evidence_ref_quote_mismatch"
        or quote_status == "evidence_ref_quote_mismatch"
    )
    semantic_audit_violation = semantic_veto and not (
        str(trace.get("evidence_ref") or "").strip()
        and str(trace.get("evidence_quote") or "").strip()
    )
    return _authority_metric_values(
        trace,
        slot_count=slot_count,
        required_ids=required_ids,
        authority_missing=authority_missing,
        missing_count=missing_count,
        complete_abstention=complete_abstention,
        identity_clear=identity_clear,
        ref_mismatch=ref_mismatch,
        quote_validation_ref_mismatch=quote_validation_ref_mismatch,
        semantic_audit_violation=semantic_audit_violation,
    )


def _authority_metric_values(
    trace: dict[str, Any],
    *,
    slot_count: int,
    required_ids: list[str],
    authority_missing: bool,
    missing_count: int,
    complete_abstention: bool,
    identity_clear: bool,
    ref_mismatch: bool,
    quote_validation_ref_mismatch: bool,
    semantic_audit_violation: bool,
) -> dict[str, float]:
    empty_slot_state = slot_count == 0
    coverage_missing = (
        _optional_float(trace.get("verifier_required_evidence_coverage")) is None
    )
    return {
        "qasper_required_verification_applicable_count": float(True),
        "qasper_required_slot_nonempty_state_count": float(slot_count > 0),
        "qasper_required_slot_empty_state_count": float(empty_slot_state),
        "qasper_required_evidence_coverage_missing_count": float(coverage_missing),
        "qasper_required_slot_authority_empty_count": float(
            1
            if empty_slot_state
            else slot_count if authority_missing and not required_ids else 0
        ),
        "qasper_required_slot_authority_missing_count": float(missing_count),
        "qasper_complete_to_unanswerable_empty_authority_count": float(
            complete_abstention and authority_missing
        ),
        "qasper_complete_to_unanswerable_identity_count": float(identity_clear),
        "qasper_complete_to_unanswerable_ref_mismatch_count": float(ref_mismatch),
        "qasper_quote_validation_ref_mismatch_count": float(
            quote_validation_ref_mismatch
        ),
        "qasper_semantic_veto_audit_violation_count": float(semantic_audit_violation),
    }


def _not_applicable_authority_metrics() -> dict[str, float]:
    keys = (
        "qasper_required_verification_applicable_count",
        "qasper_required_slot_nonempty_state_count",
        "qasper_required_slot_empty_state_count",
        "qasper_required_evidence_coverage_missing_count",
        "qasper_required_slot_authority_empty_count",
        "qasper_required_slot_authority_missing_count",
        "qasper_complete_to_unanswerable_empty_authority_count",
        "qasper_complete_to_unanswerable_identity_count",
        "qasper_complete_to_unanswerable_ref_mismatch_count",
        "qasper_quote_validation_ref_mismatch_count",
        "qasper_semantic_veto_audit_violation_count",
    )
    return {key: 0.0 for key in keys}


_SEMANTIC_VETO_REASONS = {
    "quantified_object_scope_incomplete",
    "quantified_scope_requires_current_paper_actor",
    "cited_work_does_not_establish_current_paper_claim",
    "language_scope_requires_current_experiment_evidence",
    "english_scope_not_closed",
    "no_non_english_counterexample",
    "current_paper_scope_not_established",
}


def _trace_ids(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return list(
            dict.fromkeys(str(item).strip() for item in value if str(item).strip())
        )
    return [token.strip() for token in str(value or "").split(",") if token.strip()]


def _required_authority_coverage(
    trace: dict[str, Any],
    *,
    required_slot_ids: list[str],
    required_evidence_ids: list[str],
    required_verification_applicable: bool = False,
) -> float | None:
    coverage = _optional_float(trace.get("verifier_required_evidence_coverage"))
    if coverage is not None:
        return coverage
    if required_slot_ids or required_evidence_ids:
        return 0.0
    if _trace_count(trace.get("verifier_required_slot_count")):
        return 0.0
    if str(trace.get("verifier_required_authority_status") or "") in {
        "missing_required_evidence",
        "required_evidence_not_selected",
    }:
        return 0.0
    if required_verification_applicable:
        return 0.0
    return None


def _trace_count(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _citation_support_metrics(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    cited: list[dict[str, Any]],
    *,
    contract_items: list[dict[str, Any]],
) -> dict[str, float]:
    verified = _verified_support_items(metadata, contract_items)
    verified_aliases = set().union(*(exact_evidence_aliases(item) for item in verified))
    verified_locators = set().union(
        *(normalized_source_page_locators(item) for item in verified)
    )
    support_violations = sum(
        _citation_lacks_claim_support(
            item,
            verified_aliases=verified_aliases,
            verified_locators=verified_locators,
        )
        for item in cited
    )
    answer = _final_answer(prediction)
    valid_scope_ids = {
        identity_of(item).key
        for item in _scope_valid_citations(prediction, answer, cited)
    }
    scope_violations = sum(
        identity_of(item).key not in valid_scope_ids for item in cited
    )
    minimum_citations = _required_boolean_citation_count(
        prediction,
        metadata,
        answer,
    )
    nonminimal = (
        max(0, len(cited) - minimum_citations)
        if _answer_type(prediction) == "boolean" and not is_abstention_answer(answer)
        else 0
    )
    return {
        "citation_claim_support_violation_count": float(support_violations),
        "citation_scope_violation_count": float(scope_violations),
        "citation_nonminimal_count": float(nonminimal),
    }


def _required_boolean_citation_count(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    answer: str,
) -> int:
    if _answer_type(prediction) != "boolean" or is_abstention_answer(answer):
        return 0
    trace = metadata.get("qasper_answerability")
    trace = trace if isinstance(trace, dict) else {}
    if (
        trace.get("runtime_typed_authority_kind")
        in {"composite", "semantic_evidence_set"}
        and trace.get("runtime_typed_authority_derivation_status") == "bound"
    ):
        return max(1, len(_trace_ids(trace.get("verifier_required_evidence_ids"))))
    return 1


def _citation_lacks_claim_support(
    item: dict[str, Any],
    *,
    verified_aliases: set[str],
    verified_locators: set[tuple[str, str]],
) -> bool:
    if exact_evidence_aliases(item) & verified_aliases:
        return False
    if identity_of(item).kind not in {"page", "source"}:
        return True
    return not bool(normalized_source_page_locators(item) & verified_locators)


def _verified_support_items(
    metadata: dict[str, Any],
    contract_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lookup = unambiguous_evidence_alias_lookup(contract_items)
    output: list[dict[str, Any]] = []
    by_claim = metadata.get("verified_claim_support_by_claim")
    if isinstance(by_claim, dict):
        for values in by_claim.values():
            for value in values or []:
                item = value if isinstance(value, dict) else lookup.get(str(value))
                if item is not None:
                    output.append(item)
    output.extend(
        item
        for item in metadata.get("verified_claim_support_evidence") or []
        if isinstance(item, dict)
    )
    return output


def _scope_valid_citations(
    prediction: dict[str, Any],
    answer: str,
    cited: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if _answer_type(prediction) != "boolean" or is_abstention_answer(answer):
        return cited
    metadata = prediction.get("evidence_metadata")
    trace = metadata.get("qasper_answerability") if isinstance(metadata, dict) else None
    support_ids = deterministic_support_ids(trace) if isinstance(trace, dict) else set()
    if support_ids:
        return [item for item in cited if identity_of(item).key in support_ids]
    return scope_valid_support_items(
        str(prediction.get("question") or ""),
        answer,
        cited,
    )


def _empty_answerability_metrics() -> dict[str, float | None]:
    return {
        "abstention_candidate_sent_as_semantic_answer_count": 0.0,
        "verifier_required_evidence_coverage": None,
        "answerable_false_abstention_count": 0.0,
        "boolean_scope_violation_count": 0.0,
        "wrong_polarity_count": 0.0,
        "contract_semantic_rewrite_count": 0.0,
        "engine_scored_semantic_label_mismatch_count": 0.0,
        "qasper_invalid_typed_label_count": 0.0,
        "qasper_terminal_state_missing_count": 0.0,
        "qasper_post_engine_answerability_llm_call_count": 0.0,
        "qasper_runtime_authority_missing_count": 0.0,
        "qasper_runtime_semantic_verifier_failure_count": 0.0,
        "qasper_runtime_scope_failure_count": 0.0,
        "qasper_runtime_canonical_identity_mismatch_count": 0.0,
        "qasper_runtime_quote_grounding_failure_count": 0.0,
        "qasper_runtime_authority_frame_incomplete_count": 0.0,
        "qasper_composite_authority_count": 0.0,
        "qasper_composite_authority_invalid_count": 0.0,
        "qasper_semantic_evidence_set_authority_count": 0.0,
        "qasper_semantic_evidence_set_authority_invalid_count": 0.0,
        "qasper_semantic_proposition_verifier_call_count": 0.0,
        "qasper_semantic_proposition_verifier_failure_count": 0.0,
        "qasper_semantic_proposition_verifier_context_overflow_count": 0.0,
        "qasper_semantic_proposition_verifier_schema_unsupported_count": 0.0,
        "qasper_required_verification_applicable_count": 0.0,
        "qasper_required_slot_nonempty_state_count": 0.0,
        "qasper_required_slot_empty_state_count": 0.0,
        "qasper_required_evidence_coverage_missing_count": 0.0,
        "qasper_required_slot_authority_empty_count": 0.0,
        "qasper_required_slot_authority_missing_count": 0.0,
        "qasper_complete_to_unanswerable_empty_authority_count": 0.0,
        "qasper_complete_to_unanswerable_identity_count": 0.0,
        "qasper_complete_to_unanswerable_ref_mismatch_count": 0.0,
        "qasper_quote_validation_ref_mismatch_count": 0.0,
        "qasper_semantic_veto_audit_violation_count": 0.0,
    }


def _qasper_boolean_applicable(
    prediction: dict[str, Any],
    trace: Any,
) -> bool:
    if _answer_type(prediction) != "boolean":
        return False
    if isinstance(trace, dict):
        explicit = trace.get("runtime_boolean_authority_applicable")
        return bool(explicit) if explicit is not None else True
    scoring_contract = str(prediction.get("mara_scoring_contract") or "")
    task_contract = prediction.get("task_answer_contract")
    task_contract_id = (
        str(task_contract.get("contract_id") or "")
        if isinstance(task_contract, dict)
        else ""
    )
    return "qasper" in scoring_contract.lower() or "qasper" in task_contract_id.lower()


def _gold_is_answerable(prediction: dict[str, Any]) -> bool:
    return any(
        str(answer or "").strip() and not is_abstention_answer(str(answer))
        for answer in prediction.get("gold_answers") or []
    )


def _wrong_boolean_polarity(
    prediction: dict[str, Any],
    answer: str,
) -> bool:
    if _answer_type(prediction) != "boolean":
        return False
    predicted = _boolean_polarity(answer)
    gold = {
        polarity
        for value in prediction.get("gold_answers") or []
        if (polarity := _boolean_polarity(str(value)))
    }
    return bool(predicted and len(gold) == 1 and predicted not in gold)


def _boolean_polarity(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"yes", "true"}:
        return "yes"
    if normalized in {"no", "false"}:
        return "no"
    return ""


def _final_answer(prediction: dict[str, Any]) -> str:
    return str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    )


def _answer_type(prediction: dict[str, Any]) -> str:
    return str(prediction.get("answer_type") or "").strip().lower()


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
