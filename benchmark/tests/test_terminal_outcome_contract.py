from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from ktem.docqa.terminal_semantic_commit import (
    terminal_commit_outcome,
    terminal_commit_projection_present,
)

from benchmark.qasper_runtime_projection import runtime_projection_present
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


def _route_config() -> BenchmarkConfig:
    return BenchmarkConfig(
        suite_name="terminal-outcome-contract-test",
        output_dir=Path("."),
        engine="mara",
        route="text_rag",
        scope="document",
        route_timeout_seconds=12.0,
    )


def _error(exc: Exception) -> dict:
    return _error_prediction(
        example=_example(),
        document=SimpleNamespace(document_id="document-1", path="paper.pdf"),
        route_config=_route_config(),
        exc=exc,
    )


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

    metrics = score_prediction(prediction)

    assert metrics["f1"] == 0.0
    assert prediction["gold_answers"] == ["yes"]
    assert prediction["predicted_answer"] == ""
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


def test_legacy_v2_commit_adapter_preserves_semantics_without_new_format_fallback() -> (
    None
):
    current = _error(RuntimeError("backend failed"))["engine_terminal_commit"]
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

    assert terminal_commit_projection_present(legacy)
    assert terminal_commit_outcome(legacy) == "safe_abstention"
    assert legacy["semantic_answer"] == current["semantic_answer"]

    missing_new_projection = {
        "engine_terminal_state": {
            "contract_id": "engine_terminal_state.v1",
            "terminal_semantic_commit": {},
        },
        "engine_terminal_commit": {},
    }
    record = terminal_outcome_record(missing_new_projection)
    assert record["applicable"] is True
    assert record["contract_violation"] is True
    assert record["outcome"] == ""


def test_summary_and_csv_route_fields_share_one_mutually_exclusive_source() -> None:
    answered = _error(RuntimeError("placeholder"))
    commit = answered["engine_terminal_commit"]
    commit["outcome"] = "answered"
    commit["outcome_reason"] = ""
    commit["answer_status"] = "answered"
    commit["semantic_answer"] = "yes"
    commit["presentation_answer"] = "yes"
    commit["projection_hash"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in commit.items() if key != "projection_hash"},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    answered["engine_terminal_state"]["terminal_semantic_commit"] = commit
    answered["engine_terminal_commit"] = commit
    answered["terminal_semantic_commit"] = commit
    answered["route"] = "text_rag"
    answered["metrics"] = {"false_abstention": 0.0}

    true_abstention = _error(RuntimeError("placeholder"))
    safe_commit = true_abstention["engine_terminal_commit"]
    safe_commit["outcome"] = "safe_abstention"
    safe_commit["outcome_reason"] = "insufficient_authority"
    safe_commit["projection_hash"] = hashlib.sha256(
        json.dumps(
            {
                key: value
                for key, value in safe_commit.items()
                if key != "projection_hash"
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    true_abstention["engine_terminal_state"]["terminal_semantic_commit"] = safe_commit
    true_abstention["engine_terminal_commit"] = safe_commit
    true_abstention["terminal_semantic_commit"] = safe_commit
    true_abstention["route"] = "text_rag"
    true_abstention["metrics"] = {"false_abstention": 0.0}

    false_abstention = deepcopy(true_abstention)
    false_abstention["metrics"] = {"false_abstention": 1.0}
    execution_failed = _error(RuntimeError("backend failed"))
    execution_failed["route"] = "text_rag"
    timeout = _error(RouteExecutionTimeout(12.0))
    timeout["route"] = "controller_auto"
    predictions = [
        answered,
        true_abstention,
        false_abstention,
        execution_failed,
        timeout,
    ]
    for prediction in predictions:
        apply_benchmark_outcome_classification(prediction)

    summary = terminal_outcome_summary_fields(predictions)
    route = terminal_outcome_route_fields(predictions[:4])

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
    assert route["num_terminal_true_abstention"] == 1
    assert route["num_terminal_false_abstention"] == 1
    assert route["num_terminal_execution_failed"] == 1


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
    assert (
        replay["score_projection_hash_before"] == replay["score_projection_hash_after"]
    )
