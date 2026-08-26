from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace
from typing import Any, cast

from ktem.docqa.execution_contracts import ABSTAIN_MESSAGE
from ktem.docqa.terminal_semantic_commit import (
    build_terminal_semantic_commit,
    terminal_commit_outcome,
    terminal_commit_projection_present,
)

from benchmark.benchmark_taxonomy import classify_failure_taxonomy
from benchmark.qasper_runtime_projection import runtime_projection_present
from benchmark.report_csv_schema import _CSV_FIELD_ORDER
from benchmark.reports import _summary_markdown_lines
from benchmark.route_timeout import RouteExecutionTimeout
from benchmark.runner import _error_prediction, _retrieval_trace_row
from benchmark.schemas import BenchmarkConfig
from benchmark.scoring import score_prediction
from benchmark.terminal_outcome_contract import (
    apply_benchmark_outcome_classification,
    terminal_outcome_record,
    terminal_outcome_route_fields,
    terminal_outcome_summary_fields,
)
from benchmark.terminal_outcome_replay import replay_terminal_outcome_adapter
from benchmark.verifier_observability import prediction_verifier_observability
from scripts.slurm.validate_contract_smoke import HARD_GATES


def _example() -> SimpleNamespace:
    return SimpleNamespace(
        example_id="example-1",
        document_id="document-1",
        document_ids=["document-1"],
        question="Did the authors evaluate the dataset?",
        answers=["yes"],
        evidence_pages=[],
        evidence_sources=[],
        gold_source_ids=[],
        gold_evidence_texts=[],
        gold_evidence=[],
        gold_evidence_records=[],
        expected_formats=[],
        expected_guardrails=[],
    )


def _route_config() -> SimpleNamespace:
    return SimpleNamespace(
        engine="mara",
        route="text_rag",
        scope="document",
        route_timeout_seconds=12.0,
    )


def _error(error: Exception) -> dict[str, Any]:
    return _error_prediction(
        example=_example(),
        document=SimpleNamespace(document_id="document-1", path="paper.pdf"),
        route_config=cast(BenchmarkConfig, _route_config()),
        exc=error,
    )


def _commit(outcome: str) -> dict[str, Any]:
    if outcome == "answered":
        evidence = {
            "evidence_id": "support",
            "source_id": "paper",
            "text": "The authors evaluated the dataset.",
        }
        return build_terminal_semantic_commit(
            "yes",
            {
                "status": "supported",
                "action": "return",
                "canonical_answer_polarity": "yes",
                "verified_citations": ["support"],
            },
            {"status": "ok", "action": "return"},
            {
                "items": [evidence],
                "metadata": {"verified_claim_support_evidence": [evidence]},
            },
            presentation_answer="yes",
        ).as_dict()
    return build_terminal_semantic_commit(
        ABSTAIN_MESSAGE,
        {
            "status": "not_enough_evidence",
            "action": "abstain",
            "reason": "insufficient_authority",
        },
        {
            "status": "not_enough_evidence",
            "action": "abstain",
            "reason": "insufficient_authority",
        },
        {"items": [], "metadata": {}},
        presentation_answer=ABSTAIN_MESSAGE,
    ).as_dict()


def _prediction(commit: dict[str, Any], **updates: Any) -> dict[str, Any]:
    prediction = {
        "engine_terminal_state": {
            "contract_id": "engine_terminal_state.v1",
            "terminal_semantic_commit": deepcopy(commit),
        },
        "engine_terminal_commit": deepcopy(commit),
        "terminal_semantic_commit": deepcopy(commit),
        "metrics": {"false_abstention": 0.0},
        "route": "text_rag",
    }
    prediction.update(updates)
    return prediction


def test_error_rows_carry_complete_mutually_exclusive_runtime_outcomes() -> None:
    timeout = _error(RouteExecutionTimeout(12.0))
    failed = _error(RuntimeError("backend failed"))

    assert timeout["terminal_outcome"] == "timeout"
    assert failed["terminal_outcome"] == "execution_failed"
    for prediction in (timeout, failed):
        assert runtime_projection_present(prediction)
        assert terminal_commit_projection_present(prediction["engine_terminal_commit"])
        record = terminal_outcome_record(prediction)
        assert record["contract_violation"] is False
        assert (
            sum(
                record[key]
                for key in (
                    "answered",
                    "safe_abstention",
                    "execution_failed",
                    "timeout",
                    "cancelled",
                )
            )
            == 1
        )


def test_operational_failure_remains_in_denominator_and_scores_zero() -> None:
    prediction = _error(RuntimeError("backend failed"))
    prediction["predicted_answer"] = "unanswerable"

    metrics = score_prediction(prediction)
    prediction["metrics"] = metrics
    observability = prediction_verifier_observability(prediction)

    assert metrics["f1"] == 0.0
    assert metrics["false_abstention"] == 0.0
    assert observability["false_abstention"] == 0
    assert observability["true_abstention"] == 0
    assert prediction["gold_answers"] == ["yes"]
    assert prediction["predicted_answer"] == "unanswerable"
    assert prediction["terminal_outcome"] == "execution_failed"


def test_retrieval_trace_uses_the_same_terminal_outcome_source() -> None:
    prediction = {
        **_error(RouteExecutionTimeout(12.0)),
        "benchmark_role": "qa_quality",
        "agent_mode": None,
        "route_policy": "doc",
    }

    trace = _retrieval_trace_row(prediction)

    assert trace["terminal_outcome"] == prediction["terminal_outcome"]
    assert trace["terminal_outcome_reason"] == prediction["terminal_outcome_reason"]
    assert trace["engine_terminal_state"] == prediction["engine_terminal_state"]
    assert (
        trace["engine_terminal_projection_hash"]
        == prediction["engine_terminal_projection_hash"]
    )
    assert trace["terminal_outcome_contract_violation"] is False


def test_state_commit_is_canonical_and_alias_drift_is_a_contract_violation() -> None:
    answered = _commit("answered")
    prediction = _prediction(answered)
    prediction["engine_terminal_commit"] = _commit("safe_abstention")

    record = terminal_outcome_record(prediction)

    assert record["outcome"] == "answered"
    assert record["alias_consistent"] is False
    assert record["contract_violation"] is True


def test_legacy_v2_commit_adapter_preserves_semantics() -> None:
    current = _commit("safe_abstention")
    legacy = deepcopy(current)
    for key in ("presentation_answer", "outcome", "outcome_reason"):
        legacy.pop(key)
    legacy["contract_id"] = "terminal_semantic_commit.v2"
    legacy["state_version"] = 2
    legacy["projection_hash"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in legacy.items() if key != "projection_hash"},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    prediction = _prediction(legacy)

    record = terminal_outcome_record(prediction)

    assert terminal_commit_projection_present(legacy)
    assert terminal_commit_outcome(legacy) == "safe_abstention"
    assert record["outcome"] == "safe_abstention"
    assert record["contract_violation"] is False


def test_summary_csv_and_report_share_one_mutually_exclusive_source() -> None:
    answered = _prediction(_commit("answered"))
    true_abstention = _prediction(_commit("safe_abstention"))
    false_abstention = _prediction(
        _commit("safe_abstention"),
        metrics={"false_abstention": 1.0},
    )
    failed = _error(RuntimeError("backend failed"))
    failed["route"] = "text_rag"
    timeout = _error(RouteExecutionTimeout(12.0))
    timeout["route"] = "controller_auto"
    predictions = [answered, true_abstention, false_abstention, failed, timeout]
    for prediction in predictions:
        apply_benchmark_outcome_classification(prediction)

    summary = terminal_outcome_summary_fields(predictions)
    route = terminal_outcome_route_fields(predictions[:4])
    markdown = _summary_markdown_lines(
        {"num_examples": 5, "num_documents": 1, **summary},
        "qasper",
    )

    assert summary["terminal_outcome_counts"] == {
        "answered": 1,
        "true_abstention": 1,
        "false_abstention": 1,
        "execution_failed": 1,
        "timeout": 1,
        "cancelled": 0,
        "unclassified": 0,
    }
    assert sum(summary["terminal_outcome_counts"].values()) == len(predictions)
    assert summary["terminal_outcome_contract_violation_count"] == 0
    assert route["num_terminal_answered"] == 1
    assert route["num_terminal_false_abstention"] == 1
    assert "num_terminal_timeout" in _CSV_FIELD_ORDER
    assert any("Terminal outcomes" in line for line in markdown)


def test_terminal_outcome_replay_preserves_scores_and_denominator_exactly() -> None:
    predictions = [
        {
            **_error(RuntimeError("backend failed")),
            "metrics": {"f1": 0.0, "native_score": 0.0},
            "product_metrics": {"f1": 0.0},
            "mara_score": 0.0,
        },
        {
            **_error(RouteExecutionTimeout(12.0)),
            "metrics": {"f1": 0.0, "native_score": 0.0},
            "product_metrics": {"f1": 0.0},
            "mara_score": 0.0,
        },
    ]

    replay = replay_terminal_outcome_adapter(predictions)

    assert replay["denominator_before"] == 2
    assert replay["denominator_after"] == 2
    assert replay["per_row_score_match_count"] == 2
    assert replay["per_row_score_mismatch_count"] == 0
    assert (
        replay["score_projection_hash_before"] == replay["score_projection_hash_after"]
    )


def test_terminal_outcome_controls_taxonomy_and_contract_smoke_gate() -> None:
    assert (
        classify_failure_taxonomy({"terminal_outcome": "timeout", "error_type": ""})
        == "timeout"
    )
    assert (
        classify_failure_taxonomy({"terminal_outcome": "execution_failed", "error": ""})
        == "execution_error"
    )
    assert (
        classify_failure_taxonomy({"terminal_outcome": "cancelled", "error": ""})
        == "cancelled"
    )
    assert "terminal_outcome_contract_violation_count" in HARD_GATES
