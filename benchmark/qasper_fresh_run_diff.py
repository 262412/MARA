from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ktem.docqa.evidence_identity import exact_evidence_aliases

from .dataset_native_scores import qasper_evidence_f1_for_prediction
from .jsonl import read_jsonl
from .qasper_evidence_identity import canonical_evidence_identity, canonical_quote_spans


def read_prediction_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [dict(value) for value in read_jsonl(path)]


def compare_prediction_runs(
    baseline_predictions: Iterable[dict[str, Any]],
    candidate_predictions: Iterable[dict[str, Any]],
    *,
    acceptance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    baseline = {_prediction_key(item): item for item in baseline_predictions}
    candidate = {_prediction_key(item): item for item in candidate_predictions}
    aligned_keys = sorted(baseline.keys() & candidate.keys())
    expected = _acceptance_lookup(acceptance or {})
    rows = [
        _prediction_diff(
            baseline[key],
            candidate[key],
            expected_change=expected.get(key),
        )
        for key in aligned_keys
    ]
    retrieval_set_examples = _example_drift_counts(
        rows,
        "canonical_retrieved_evidence_set_drift",
    )
    return {
        "contract_id": "qasper_fresh_run_diff.v1",
        "baseline_prediction_count": len(baseline),
        "candidate_prediction_count": len(candidate),
        "aligned_prediction_count": len(aligned_keys),
        "missing_from_candidate": [
            list(key) for key in sorted(baseline.keys() - candidate)
        ],
        "missing_from_baseline": [
            list(key) for key in sorted(candidate.keys() - baseline)
        ],
        "answer_status_drift_count": _count(rows, "answer_status_drift"),
        "canonical_prompt_fingerprint_drift_count": _count(
            rows, "canonical_prompt_fingerprint_drift"
        ),
        "canonical_retrieved_evidence_set_drift_count": _count(
            rows, "canonical_retrieved_evidence_set_drift"
        ),
        "canonical_retrieved_evidence_set_drift_by_route": _route_drift_counts(
            rows,
            "canonical_retrieved_evidence_set_drift",
        ),
        "canonical_retrieved_evidence_set_drift_example_count": (
            retrieval_set_examples["any_route"]
        ),
        "canonical_retrieved_evidence_set_drift_all_routes_example_count": (
            retrieval_set_examples["all_routes"]
        ),
        "canonical_retrieved_evidence_order_drift_count": _count(
            rows, "canonical_retrieved_evidence_order_drift"
        ),
        "candidate_state_drift_count": _count(rows, "candidate_state_drift"),
        "raw_verdict_drift_count": _count(rows, "raw_verdict_drift"),
        "quote_drift_count": _count(rows, "quote_drift"),
        "reason_drift_count": _count(rows, "reason_drift"),
        "scope_drift_count": _count(rows, "scope_drift"),
        "authority_drift_count": _count(rows, "authority_drift"),
        "unexpected_terminal_state_drift_count": _count(
            rows, "unexpected_terminal_state_drift"
        ),
        "verified_support_regression_count": _count(
            rows, "verified_support_regression"
        ),
        "runtime_only_identity_drift_count": _count(
            rows, "runtime_only_identity_drift"
        ),
        "stored_recomputed_qasper_evidence_f1_mismatch_count": sum(
            _stored_recomputed_mismatch(prediction) for prediction in candidate.values()
        ),
        "expected_change_counts": _expected_change_counts(rows),
        "rows": rows,
    }


def _prediction_diff(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    expected_change: dict[str, Any] | None,
) -> dict[str, Any]:
    baseline_retrieval = _canonical_retrieval(baseline)
    candidate_retrieval = _canonical_retrieval(candidate)
    baseline_runtime = _runtime_retrieval_ids(baseline)
    candidate_runtime = _runtime_retrieval_ids(candidate)
    baseline_trace = _qasper_trace(baseline)
    candidate_trace = _qasper_trace(candidate)
    baseline_terminal = _canonical_terminal_state(baseline)
    candidate_terminal = _canonical_terminal_state(candidate)
    expected_category = str((expected_change or {}).get("category") or "")
    terminal_drift = baseline_terminal != candidate_terminal
    expected_terminal = bool(
        expected_change and expected_change.get("allow_terminal_drift")
    )
    verified_support_regression = _verified_support_regression(
        baseline,
        candidate,
    )
    return {
        "example_id": str(baseline.get("example_id") or ""),
        "route": str(baseline.get("route") or ""),
        "expected_change_category": expected_category,
        "baseline_answer": _terminal_answer(baseline),
        "candidate_answer": _terminal_answer(candidate),
        "answer_status_drift": _answer_status(baseline) != _answer_status(candidate),
        "canonical_prompt_fingerprint_drift": _canonical_prompt_fingerprint(baseline)
        != _canonical_prompt_fingerprint(candidate),
        "canonical_retrieved_evidence_set_drift": set(baseline_retrieval)
        != set(candidate_retrieval),
        "canonical_retrieved_evidence_order_drift": baseline_retrieval
        != candidate_retrieval,
        "candidate_state_drift": _candidate_state(baseline)
        != _candidate_state(candidate),
        "raw_verdict_drift": _normalized(baseline_trace.get("raw_verifier_verdict"))
        != _normalized(candidate_trace.get("raw_verifier_verdict")),
        "quote_drift": _normalized(baseline_trace.get("evidence_quote"))
        != _normalized(candidate_trace.get("evidence_quote")),
        "reason_drift": _normalized(baseline_trace.get("reason"))
        != _normalized(candidate_trace.get("reason")),
        "scope_drift": _scope_state(baseline_trace) != _scope_state(candidate_trace),
        "authority_drift": _authority_state(baseline) != _authority_state(candidate),
        "terminal_state_drift": terminal_drift,
        "verified_support_regression": verified_support_regression,
        "unexpected_terminal_state_drift": verified_support_regression
        or (terminal_drift and not expected_terminal),
        "runtime_only_identity_drift": baseline_runtime != candidate_runtime
        and set(baseline_retrieval) == set(candidate_retrieval),
        "baseline_retrieved_evidence": baseline_retrieval,
        "candidate_retrieved_evidence": candidate_retrieval,
        "baseline_terminal_state_hash": _stable_hash(baseline_terminal),
        "candidate_terminal_state_hash": _stable_hash(candidate_terminal),
    }


def _prediction_key(prediction: dict[str, Any]) -> tuple[str, str]:
    return (
        str(prediction.get("example_id") or ""),
        str(prediction.get("route") or ""),
    )


def _canonical_retrieval(prediction: dict[str, Any]) -> list[str]:
    return [
        _canonical_evidence_key(item)
        for item in prediction.get("retrieved_hits") or []
        if isinstance(item, dict)
    ]


def _canonical_evidence_key(item: dict[str, Any]) -> str:
    text = _item_text(item)
    identity = canonical_evidence_identity(item, text=text)
    start = "" if identity.chunk_start is None else str(identity.chunk_start)
    end = "" if identity.chunk_end is None else str(identity.chunk_end)
    page = str(item.get("dataset_page") or item.get("page_label") or "")
    return "|".join((identity.source_id, page, start, end, identity.text_hash))


def _runtime_retrieval_ids(prediction: dict[str, Any]) -> list[str]:
    return [
        str(item.get("canonical_id") or item.get("evidence_id") or "")
        for item in prediction.get("retrieved_hits") or []
        if isinstance(item, dict)
    ]


def _canonical_prompt_fingerprint(prediction: dict[str, Any]) -> str:
    trace = _qasper_trace(prediction)
    recorded = str(trace.get("canonical_prompt_fingerprint") or "")
    if recorded:
        return recorded
    alias_lookup = _runtime_alias_lookup(prediction)
    raw_spans = trace.get("verifier_input_evidence_spans")
    try:
        spans = json.loads(raw_spans) if isinstance(raw_spans, str) else raw_spans
    except json.JSONDecodeError:
        spans = []
    canonical = []
    for entry in spans or []:
        if not isinstance(entry, dict):
            continue
        evidence_id = str(entry.get("evidence_id") or "")
        item = alias_lookup.get(evidence_id)
        if item is None:
            continue
        entry_spans = entry.get("spans")
        if not isinstance(entry_spans, list):
            entry_spans = [entry]
        canonical.append(
            {
                "evidence": _canonical_evidence_key(item),
                "spans": [
                    [span.get("span_start"), span.get("span_end")]
                    for span in entry_spans
                    if isinstance(span, dict)
                ],
            }
        )
    return _stable_hash(canonical)


def _runtime_alias_lookup(prediction: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for item in _all_evidence_items(prediction):
        try:
            aliases = exact_evidence_aliases(item)
        except ValueError:
            continue
        for alias in aliases:
            lookup.setdefault(alias, item)
    return lookup


def _all_evidence_items(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    items = [
        item
        for item in prediction.get("retrieved_hits") or []
        if isinstance(item, dict)
    ]
    metadata = prediction.get("evidence_metadata") or {}
    if isinstance(metadata, dict):
        for value in metadata.values():
            if isinstance(value, list):
                items.extend(item for item in value if isinstance(item, dict))
    return items


def _canonical_terminal_state(prediction: dict[str, Any]) -> dict[str, Any]:
    terminal = prediction.get("terminal_answer_state") or {}
    return {
        "answer": _terminal_answer(prediction),
        "status": str(prediction.get("status") or ""),
        "terminal_status": (
            str(terminal.get("status") or "") if isinstance(terminal, dict) else ""
        ),
        "support": sorted(_canonical_support(prediction)),
        "citations": sorted(_canonical_citations(prediction)),
    }


def _canonical_support(prediction: dict[str, Any]) -> set[str]:
    trace = _qasper_trace(prediction)
    quote = str(trace.get("evidence_quote") or "")
    if not quote:
        return set()
    support = set()
    for item in _all_evidence_items(prediction):
        for span in canonical_quote_spans(item, quote, text=_item_text(item)):
            support.add(span.identity)
    return support


def _canonical_citations(prediction: dict[str, Any]) -> set[str]:
    lookup = _runtime_alias_lookup(prediction)
    values = []
    for citation in prediction.get("structured_citations") or []:
        if isinstance(citation, dict):
            values.append(str(citation.get("evidence_id") or ""))
        else:
            values.append(str(citation or ""))
    for value in prediction.get("predicted_citations") or []:
        values.append(str(value or ""))
    canonical = set()
    for value in values:
        item = lookup.get(value)
        canonical.add(_canonical_evidence_key(item) if item is not None else value)
    return {value for value in canonical if value}


def _authority_state(prediction: dict[str, Any]) -> tuple[str, ...]:
    trace = _qasper_trace(prediction)
    authoritative_id = str(trace.get("authoritative_quote_evidence_id") or "")
    authoritative_item = _runtime_alias_lookup(prediction).get(authoritative_id)
    canonical_authoritative_id = (
        _canonical_evidence_key(authoritative_item)
        if authoritative_item is not None
        else authoritative_id
    )
    claim_key = trace.get("authoritative_claim_key")
    if isinstance(claim_key, (list, tuple, dict)):
        canonical_claim_key = json.dumps(
            claim_key,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    else:
        canonical_claim_key = _normalized(claim_key)
    return tuple(sorted(_canonical_support(prediction))) + (
        _normalized(trace.get("adjudicated_polarity")),
        canonical_authoritative_id,
        str(trace.get("authoritative_quote_span_id") or ""),
        canonical_claim_key,
        str(trace.get("binding_status") or ""),
        str(trace.get("evidence_ref_binding_status") or ""),
        str(trace.get("evidence_ref_rebound") or ""),
    )


def _typed_authority_state(prediction: dict[str, Any]) -> str:
    metadata = prediction.get("evidence_metadata") or {}
    terminal_state = prediction.get("engine_terminal_state") or {}
    terminal_verify = prediction.get("engine_verify_decision") or {}
    verify = prediction.get("verify_decision") or {}
    candidates = (
        prediction.get("typed_authority"),
        (
            terminal_state.get("typed_authority")
            if isinstance(terminal_state, dict)
            else None
        ),
        (
            terminal_verify.get("typed_authority")
            if isinstance(terminal_verify, dict)
            else None
        ),
        verify.get("typed_authority") if isinstance(verify, dict) else None,
        metadata.get("typed_authority") if isinstance(metadata, dict) else None,
    )
    for value in candidates:
        if isinstance(value, dict) and value.get("state") is not None:
            return _normalized(value.get("state"))
    trace = _qasper_trace(prediction)
    return _normalized(
        trace.get("runtime_typed_authority_state") or trace.get("typed_authority_state")
    )


def _answer_state_label(prediction: dict[str, Any]) -> str:
    for key in ("answer_status", "terminal_outcome"):
        value = _normalized(prediction.get(key))
        if value:
            return value
    terminal = prediction.get("terminal_answer_state") or {}
    if isinstance(terminal, dict):
        return _normalized(terminal.get("status") or terminal.get("outcome"))
    return ""


def _is_answered(prediction: dict[str, Any]) -> bool:
    return _answer_state_label(prediction) in {"answered", "answer"}


def _is_abstention(prediction: dict[str, Any]) -> bool:
    if _answer_state_label(prediction) in {
        "abstained",
        "safe_abstention",
        "unanswerable",
        "not_enough_evidence",
    }:
        return True
    return _terminal_answer(prediction) in {"", "unanswerable"}


def _verified_support_regression(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    candidate_authority = _typed_authority_state(candidate)
    return (
        _is_answered(baseline)
        and _typed_authority_state(baseline) == "verified_support"
        and (
            _is_abstention(candidate)
            or candidate_authority
            in {"", "missing", "retrieved_unverified", "retrieved_partial"}
        )
    )


def _scope_state(trace: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        _normalized(trace.get(key))
        for key in (
            "boolean_actor",
            "boolean_section_role",
            "boolean_quantifier",
            "boolean_scope_valid",
            "boolean_scope_reason",
        )
    )


def _qasper_trace(prediction: dict[str, Any]) -> dict[str, Any]:
    metadata = prediction.get("evidence_metadata") or {}
    trace = metadata.get("qasper_answerability") if isinstance(metadata, dict) else {}
    return trace if isinstance(trace, dict) else {}


def _candidate_state(prediction: dict[str, Any]) -> str:
    metadata = prediction.get("evidence_metadata") or {}
    trace = _qasper_trace(prediction)
    if isinstance(metadata, dict):
        candidate = metadata.get("pre_verification_answer")
        if candidate is not None:
            return _normalized(candidate)
    return _normalized(
        trace.get("candidate_for_answerability") or trace.get("primary_answer")
    )


def _answer_status(prediction: dict[str, Any]) -> tuple[str, str]:
    return _terminal_answer(prediction), str(prediction.get("status") or "")


def _terminal_answer(prediction: dict[str, Any]) -> str:
    terminal = prediction.get("terminal_answer_state") or {}
    if isinstance(terminal, dict) and terminal.get("answer") is not None:
        return _normalized(terminal.get("answer"))
    return _normalized(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer")
    )


def _stored_recomputed_mismatch(prediction: dict[str, Any]) -> int:
    stored = (prediction.get("metrics") or {}).get("qasper_evidence_f1")
    recomputed = qasper_evidence_f1_for_prediction(prediction)
    if stored is None or recomputed is None:
        return 0
    try:
        return int(abs(float(stored) - float(recomputed)) > 1e-9)
    except (TypeError, ValueError):
        return 1


def _acceptance_lookup(value: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(item.get("example_id") or ""), str(item.get("route") or "")): item
        for item in value.get("changes") or []
        if isinstance(item, dict)
    }


def _expected_change_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        category = str(row.get("expected_change_category") or "")
        if row.get("answer_status_drift") and category:
            counts[category] = counts.get(category, 0) + 1
    return counts


def _count(rows: list[dict[str, Any]], key: str) -> int:
    return sum(bool(row.get(key)) for row in rows)


def _route_drift_counts(
    rows: list[dict[str, Any]],
    key: str,
) -> dict[str, int]:
    routes = sorted({str(row.get("route") or "") for row in rows})
    return {
        route: sum(
            bool(row.get(key)) and str(row.get("route") or "") == route for row in rows
        )
        for route in routes
        if route
    }


def _example_drift_counts(
    rows: list[dict[str, Any]],
    key: str,
) -> dict[str, int]:
    route_states: dict[str, list[bool]] = {}
    for row in rows:
        example_id = str(row.get("example_id") or "")
        route_states.setdefault(example_id, []).append(bool(row.get(key)))
    return {
        "any_route": sum(any(states) for states in route_states.values()),
        "all_routes": sum(
            len(states) > 1 and all(states) for states in route_states.values()
        ),
    }


def _item_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "").strip()
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if str(item.get(field) or "").strip()
    )


def _normalized(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
