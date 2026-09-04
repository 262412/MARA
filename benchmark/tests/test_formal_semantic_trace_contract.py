from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from benchmark.artifact_publication import publish_artifact_contract
from benchmark.jsonl import read_jsonl
from benchmark.qasper_causal_transaction import QASPER_CAUSAL_TRANSACTION_STAGES
from benchmark.qasper_semantic_debug_artifact import qasper_semantic_debug_rows
from benchmark.reports import write_reports

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEXT_SLURM_SCRIPT = PROJECT_ROOT / "scripts/slurm/text_route_rerun.sbatch"
SUBMIT_FULLSYSTEM = PROJECT_ROOT / "scripts/slurm/submit_fullsystem_jobs.sh"


def _pre_route_failure_prediction() -> dict:
    return {
        "example_id": "pre-route-failure",
        "route": "hybrid_rag",
        "question": "Did the authors use the method?",
        "gold_answers": ["yes"],
        "predicted_answer": "",
        "answer_status": "failed",
        "terminal_outcome": "execution_failed",
        "terminal_outcome_reason": "route failed before candidate generation",
        "evidence_metadata": {},
    }


def _pre_verifier_failure_prediction() -> dict:
    prediction = _pre_route_failure_prediction()
    prediction.update(
        {
            "example_id": "pre-verifier",
            "terminal_outcome_reason": "candidate generation failed",
            "evidence_metadata": {
                "qasper_candidate_generation": {
                    "contract_id": "qasper_typed_candidate_generation.v2",
                    "status": "failed",
                    "failure_reason": "provider_context_length_exceeded",
                }
            },
        }
    )
    return prediction


def test_formal_qasper_launcher_enables_and_requires_semantic_trace_capture():
    launcher = SUBMIT_FULLSYSTEM.read_text(encoding="utf-8")

    assert 'if [[ "$dataset" == "qasper" ]]; then' in launcher
    assert (
        'semantic_trace_exports=",MARA_SEMANTIC_PROPOSITION_DEBUG_TRACE=1,' in launcher
    )
    assert "MARA_REQUIRE_SEMANTIC_DEBUG_TRACE=1" in launcher
    assert "MARA_SEMANTIC_PROPOSITION_DEBUG_TRACE=1" in launcher
    assert "MARA_TEXT_ARTIFACT_DETAIL=compact${semantic_trace_exports}" in launcher


def test_text_runner_fails_closed_when_trace_is_required_but_disabled():
    text = TEXT_SLURM_SCRIPT.read_text(encoding="utf-8")

    assert (
        'if [[ "$REQUIRE_SEMANTIC_DEBUG_TRACE" == "1" && '
        '"$SEMANTIC_DEBUG_TRACE" != "1" ]]; then'
    ) in text
    assert "required semantic debug trace requires" in text


def test_required_qasper_trace_has_one_transaction_row_per_prediction(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MARA_SEMANTIC_PROPOSITION_DEBUG_TRACE", "1")
    monkeypatch.setenv("MARA_REQUIRE_SEMANTIC_DEBUG_TRACE", "1")
    predictions = [
        _pre_verifier_failure_prediction(),
        _pre_route_failure_prediction(),
    ]
    assert [row["example_id"] for row in qasper_semantic_debug_rows(predictions)] == [
        "pre-verifier"
    ]
    rows = qasper_semantic_debug_rows(predictions, include_missing=True)

    assert [row["example_id"] for row in rows] == [
        "pre-verifier",
        "pre-route-failure",
    ]
    for row in rows:
        transaction = row["causal_transaction"]
        assert transaction["stage_order"] == list(QASPER_CAUSAL_TRANSACTION_STAGES)
        assert transaction["stage_count"] == len(QASPER_CAUSAL_TRANSACTION_STAGES)
        assert transaction["status"] == "incomplete"
        assert transaction["incompleteness_reasons"]
        assert transaction["transaction_key"] == {
            "example_id": row["example_id"],
            "route": row["route"],
        }
        assert transaction["terminal_chain_digest"]
        assert transaction["transaction_digest"]
        assert len(transaction["stages"]) == len(QASPER_CAUSAL_TRANSACTION_STAGES)
        for index, (name, stage) in enumerate(
            zip(QASPER_CAUSAL_TRANSACTION_STAGES, transaction["stages"]),
            start=1,
        ):
            assert stage["stage_index"] == index
            assert stage["stage"] == name
            assert stage["status"] in {"complete", "incomplete"}
            assert isinstance(stage["payload"], dict)
            assert "status" in stage["payload"]
            assert stage["payload_digest"]
            assert stage["comparison_digest"]
            assert "previous_chain_digest" in stage
            assert stage["chain_digest"]

    report = {
        "summary": {
            "suite_name": "Formal QASPER",
            "dataset_name": "qasper",
            "num_examples": len(predictions),
            "num_documents": 0,
        },
        "predictions": predictions,
        "documents": [],
    }
    run_dir = write_reports(
        report,
        tmp_path,
        "Formal QASPER",
        artifact_detail="compact",
    )

    assert len(read_jsonl(run_dir / "predictions.jsonl")) == len(predictions)
    traces = read_jsonl(run_dir / "semantic_debug_traces.jsonl")
    assert len(traces) == len(predictions)
    assert [(row["example_id"], row["route"]) for row in traces] == [
        (prediction["example_id"], prediction["route"]) for prediction in predictions
    ]
    marker = json.loads((run_dir / "artifact_complete.json").read_text())
    assert marker["complete"] is True


def test_publisher_keeps_semantic_trace_line_count_gate(tmp_path):
    run_dir = tmp_path / "sparse-trace"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"artifact_detail": "full"}), encoding="utf-8"
    )
    (run_dir / "predictions.jsonl").write_text("{}\n{}\n", encoding="utf-8")
    (run_dir / "semantic_debug_traces.jsonl").write_text("{}\n", encoding="utf-8")

    marker = publish_artifact_contract(
        run_dir,
        run_requirements={"semantic_debug_traces": True},
    )

    assert marker["complete"] is False
    assert "semantic_debug_traces.jsonl" in marker["required_file_failures"]


def test_publisher_rejects_duplicate_trace_key_when_line_count_matches(tmp_path):
    predictions = [
        _pre_verifier_failure_prediction(),
        _pre_route_failure_prediction(),
    ]
    traces = qasper_semantic_debug_rows(predictions, include_missing=True)
    run_dir = tmp_path / "duplicate-trace-key"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"artifact_detail": "full"}), encoding="utf-8"
    )
    (run_dir / "predictions.jsonl").write_text(
        "".join(f"{json.dumps(row)}\n" for row in predictions), encoding="utf-8"
    )
    (run_dir / "semantic_debug_traces.jsonl").write_text(
        "".join(f"{json.dumps(row)}\n" for row in (traces[0], traces[0])),
        encoding="utf-8",
    )

    marker = publish_artifact_contract(
        run_dir,
        run_requirements={"semantic_debug_traces": True},
    )

    assert marker["complete"] is False
    assert "semantic_debug_traces.jsonl" in marker["required_file_failures"]


def test_publisher_rejects_equal_count_trace_without_transaction_structure(
    tmp_path,
):
    predictions = [
        _pre_verifier_failure_prediction(),
        _pre_route_failure_prediction(),
    ]
    run_dir = tmp_path / "incomplete-trace-structure"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"artifact_detail": "full"}), encoding="utf-8"
    )
    (run_dir / "predictions.jsonl").write_text(
        "".join(f"{json.dumps(row)}\n" for row in predictions), encoding="utf-8"
    )
    (run_dir / "semantic_debug_traces.jsonl").write_text(
        "".join(
            f"{json.dumps({'example_id': row['example_id'], 'route': row['route']})}\n"
            for row in predictions
        ),
        encoding="utf-8",
    )

    marker = publish_artifact_contract(
        run_dir,
        run_requirements={"semantic_debug_traces": True},
    )

    assert marker["complete"] is False
    assert "semantic_debug_traces.jsonl" in marker["required_file_failures"]


def test_publisher_rejects_required_trace_without_predictions(tmp_path):
    run_dir = tmp_path / "missing-predictions"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"artifact_detail": "full"}), encoding="utf-8"
    )
    (run_dir / "semantic_debug_traces.jsonl").write_text("{}\n", encoding="utf-8")

    marker = publish_artifact_contract(
        run_dir,
        run_requirements={"semantic_debug_traces": True},
    )

    assert marker["complete"] is False
    assert "semantic_debug_traces.jsonl" in marker["required_file_failures"]


def test_publisher_rejects_tampered_stage_payload_chain_or_status(tmp_path):
    predictions = [
        _pre_verifier_failure_prediction(),
        _pre_route_failure_prediction(),
    ]
    traces = qasper_semantic_debug_rows(predictions, include_missing=True)
    for name in ("payload", "chain", "status"):
        run_dir = tmp_path / f"tampered-{name}"
        run_dir.mkdir()
        (run_dir / "summary.json").write_text(
            json.dumps({"artifact_detail": "full"}), encoding="utf-8"
        )
        (run_dir / "predictions.jsonl").write_text(
            "".join(f"{json.dumps(row)}\n" for row in predictions), encoding="utf-8"
        )
        tampered = deepcopy(traces[0])
        if name == "payload":
            tampered["causal_transaction"]["stages"][0]["payload"]["tampered"] = True
        elif name == "chain":
            tampered["causal_transaction"]["stages"][0]["chain_digest"] = "0" * 64
        else:
            stage = tampered["causal_transaction"]["stages"][0]
            stage["status"] = (
                "complete" if stage["status"] == "incomplete" else "incomplete"
            )
        (run_dir / "semantic_debug_traces.jsonl").write_text(
            "".join(f"{json.dumps(row)}\n" for row in (tampered, traces[1])),
            encoding="utf-8",
        )

        marker = publish_artifact_contract(
            run_dir,
            run_requirements={"semantic_debug_traces": True},
        )

        assert marker["complete"] is False
        assert "semantic_debug_traces.jsonl" in marker["required_file_failures"]
