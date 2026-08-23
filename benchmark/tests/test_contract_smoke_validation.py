from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from ktem.docqa.terminal_semantic_commit import build_terminal_semantic_commit

from benchmark.artifact_publication import publish_artifact_contract
from scripts.slurm.validate_contract_smoke import QASPER_HARD_GATES, validate

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = PROJECT_ROOT / "scripts/slurm/validate_contract_smoke.py"
CORE_STAGES = (
    "canonical_candidate_evidence",
    "fused_evidence",
    "reranker_input_evidence",
    "selected_evidence",
    "generation_context_evidence",
    "verified_claim_support_evidence",
    "emitted_citation_evidence",
)
QASPER_REQUIREMENTS = (
    "ordinary_free_text",
    "yes_no",
    "support_and_contradiction",
    "cross_page_required_slots",
    "runtime_authority_pass_through",
)


def _evidence() -> dict[str, Any]:
    return {
        "canonical_id": "span:paper:s1",
        "source_id": "paper",
        "page_label": "1",
        "span_id": "s1",
        "evidence_level": "span",
        "text": "The paper reports the result.",
    }


def _prediction(requirements: list[str]) -> dict[str, Any]:
    item = _evidence()
    metadata: dict[str, Any] = {stage: [item] for stage in CORE_STAGES}
    metadata.update(
        {
            "ranking_trace": {"backend_execution": False},
            "query_plan": {
                "evidence_slots": [
                    {
                        "slot_id": "support:answer",
                        "role": "support",
                        "required": True,
                        "status": "filled",
                        "evidence_ids": ["span:paper:s1"],
                    }
                ]
            },
        }
    )
    return {
        "example_id": "smoke",
        "document_id": "paper",
        "document_ids": ["paper"],
        "question": "What result is reported?",
        "answer_type": "free_text",
        "gold_answers": ["The result."],
        "gold_evidence": [{"document_id": "paper", "page": 1}],
        "gold_source_ids": ["paper"],
        "gold_evidence_texts": ["The paper reports the result."],
        "source_identity_crosswalk": [
            {
                "canonical_dataset_id": "paper",
                "runtime_file_id": "paper-runtime",
                "runtime_source_id": "paper-runtime",
                "document_path": "/datasets/paper.pdf",
                "filename": "paper.pdf",
                "aliases": ["paper"],
            }
        ],
        "predicted_answer": "The result.",
        "answer_for_scoring": "The result.",
        "example_metadata": {
            "contract_smoke_requirements": requirements,
        },
        "evidence_metadata": metadata,
    }


def _write_run(
    run_dir: Path,
    *,
    predictions: list[dict[str, Any]],
    artifact_detail: str = "full",
) -> None:
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"artifact_detail": artifact_detail}),
        encoding="utf-8",
    )
    (run_dir / "predictions.jsonl").write_text(
        "".join(f"{json.dumps(row)}\n" for row in predictions),
        encoding="utf-8",
    )
    publish_artifact_contract(run_dir)


def _attach_terminal_commit(prediction: dict[str, Any]) -> None:
    terminal_commit = build_terminal_semantic_commit(
        "yes",
        {
            "status": "supported",
            "action": "return",
            "canonical_answer_polarity": "yes",
            "verified_citations": ["span:paper:s1"],
        },
        {"status": "ok", "action": "return"},
        {
            "items": [_evidence()],
            "metadata": {"verified_claim_support_evidence": [_evidence()]},
        },
        presentation_answer="yes",
    ).as_dict()
    prediction["engine_terminal_state"]["terminal_semantic_commit"] = terminal_commit
    prediction["engine_terminal_commit"] = terminal_commit
    prediction["terminal_semantic_commit"] = terminal_commit


def test_contract_smoke_validator_accepts_full_auditable_artifact(tmp_path):
    run_dir = tmp_path / "run"
    requirements = list(QASPER_REQUIREMENTS)
    first = _prediction(requirements)
    first.update(
        {
            "question": "Did the paper report the result?",
            "answer_type": "boolean",
            "gold_answers": ["yes"],
            "predicted_answer": "yes",
            "answer_for_scoring": "yes",
            "engine_terminal_answer": "yes",
            "engine_terminal_state": {
                "contract_id": "engine_terminal_state.v1",
                "answer": "yes",
            },
            "engine_verify_decision": {"status": "supported"},
            "engine_terminal_projection_hash": "verified-projection",
            "contract_action": "pass_through",
            "contract_semantic_rewrite": False,
            "post_engine_answerability_llm_call_count": 0,
        }
    )
    _attach_terminal_commit(first)
    first["evidence_metadata"].update(
        {
            "qasper_answerability": {
                "status": "ok",
                "contract_action": "pass_through",
                "contract_semantic_rewrite": False,
                "engine_terminal_answer": "yes",
                "engine_semantic_label": "yes",
                "scored_semantic_label": "yes",
                "runtime_projection_present": True,
                "runtime_boolean_authority_applicable": True,
                "runtime_authority_failure_kind": "",
                "post_engine_answerability_llm_call_count": 0,
                "raw_verifier_verdict": "yes_complete",
                "final_post_contract_answer": "yes",
                "boolean_scope_valid": "true",
                "verifier_required_slot_ids": "support:boolean_proposition",
                "verifier_required_slot_count": "1",
                "verifier_required_slot_authority_count": "1",
                "verifier_required_evidence_ids": "span:paper:s1",
                "verifier_missing_required_slot_ids": "",
                "verifier_missing_required_evidence_ids": "",
                "verifier_required_authority_status": "complete",
                "verifier_required_evidence_coverage": "1.000000",
                "quote_ref_validation_status": "bound",
            },
        }
    )
    second = _prediction([])
    second["example_id"] = "smoke-2"
    _write_run(run_dir, predictions=[first, second])

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(run_dir),
            "--suite-kind",
            "qasper",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "contract_smoke_status=passed" in result.stdout
    audit = json.loads((run_dir / "contract_smoke_audit.json").read_text())
    assert audit["artifact_detail"] == "full"
    assert audit["hard_gates"]["identity_collision_count"]["passed"] is True
    assert audit["stage_audits"][0]["reranked_evidence"]["status"] == (
        "truthfully_not_executed"
    )


def test_contract_smoke_validator_rejects_compact_or_incomplete_artifact(tmp_path):
    run_dir = tmp_path / "run"
    prediction = _prediction(["ordinary_free_text"])
    prediction["evidence_metadata"].pop("selected_evidence")
    second = _prediction([])
    second["example_id"] = "smoke-2"
    _write_run(
        run_dir,
        predictions=[prediction, second],
        artifact_detail="compact",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(run_dir),
            "--suite-kind",
            "qasper",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "artifact_detail must be full" in result.stderr
    audit = json.loads((run_dir / "contract_smoke_audit.json").read_text())
    assert audit["status"] == "failed"
    assert (
        "artifact_detail must be full for contract smoke"
        in audit["precondition_violations"]
    )


def test_contract_smoke_validator_rejects_missing_required_case(tmp_path):
    run_dir = tmp_path / "run"
    first = _prediction(["ordinary_free_text"])
    second = _prediction([])
    second["example_id"] = "smoke-2"
    _write_run(run_dir, predictions=[first, second])

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(run_dir),
            "--suite-kind",
            "qasper",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "missing contract smoke requirements" in result.stderr


def test_qasper_contract_smoke_requires_runtime_authority_pass_through(tmp_path):
    run_dir = tmp_path / "run"
    requirements = list(QASPER_REQUIREMENTS)
    first = _prediction(requirements)
    second = _prediction([])
    second["example_id"] = "smoke-2"
    _write_run(run_dir, predictions=[first, second])

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(run_dir),
            "--suite-kind",
            "qasper",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "runtime_authority_pass_through_not_observed" in result.stderr


def test_qasper_contract_smoke_declares_runtime_authority_hard_gates():
    assert {
        "abstention_candidate_sent_as_semantic_answer_count",
        "verifier_required_evidence_coverage",
        "qasper_required_slot_empty_state_count",
        "qasper_required_evidence_coverage_missing_count",
        "answerable_false_abstention_count",
        "boolean_scope_violation_count",
        "wrong_polarity_count",
        "citation_claim_support_violation_count",
        "citation_scope_violation_count",
        "contract_semantic_rewrite_count",
        "engine_scored_semantic_label_mismatch_count",
        "qasper_post_engine_answerability_llm_call_count",
        "qasper_runtime_authority_missing_count",
        "qasper_runtime_semantic_verifier_failure_count",
        "qasper_runtime_scope_failure_count",
        "qasper_composite_authority_invalid_count",
        "qasper_semantic_evidence_set_authority_invalid_count",
        "qasper_semantic_proposition_verifier_failure_count",
        "qasper_quote_validation_ref_mismatch_count",
        "qasper_terminal_state_missing_count",
        "qasper_invalid_typed_label_count",
    } <= set(QASPER_HARD_GATES)


def _qasper_debug_prediction(example_id: str, route: str) -> dict[str, Any]:
    prediction = _prediction([])
    group_id = f"group:{example_id}"
    metadata = prediction["evidence_metadata"]
    metadata.update(
        {
            "qasper_candidate_generation": _debug_generator_trace(
                example_id, route, group_id
            ),
            "semantic_proposition_verifier": _debug_verifier_trace(
                example_id, route, group_id
            ),
        }
    )
    prediction.update(
        {
            "example_id": example_id,
            "route": route,
            "answer_type": "boolean",
            "gold_answers": ["yes"],
            "predicted_answer": "yes",
            "answer_for_scoring": "yes",
            "controller_trace": [
                {
                    "stage": "claim_aggregation",
                    "input_text": "yes",
                    "output_text": "yes",
                    "input_digest": "claim-input",
                    "output_digest": "claim-output",
                }
            ],
            "example_metadata": {
                "qasper_answer_annotations": [
                    {
                        "annotation_id": f"annotation:{example_id}",
                        "yes_no": True,
                    }
                ]
            },
            "qasper_annotation_scores": [
                {
                    "contract_id": "qasper_annotation_score.v1",
                    "annotation_index": 1,
                    "annotation_id": f"annotation:{example_id}",
                    "answer_f1": 1.0,
                    "typed_accuracy": 1.0,
                    "evidence_f1": 1.0,
                    "ambiguity_marker": "",
                }
            ],
            "qasper_annotation_diagnostics": {
                "contract_id": "qasper_annotation_diagnostics.v1",
                "annotation_count": 1,
                "ambiguous": False,
                "ambiguity_reasons": [],
                "canonical_answer_classes": [["yes"]],
            },
            "terminal_outcome": "answered",
            "terminal_outcome_reason": "",
            "terminal_outcome_contract_violation": False,
            "terminal_semantic_commit": {
                "contract_id": "terminal_semantic_commit.v3",
                "semantic_answer": "yes",
                "outcome": "answered",
            },
        }
    )
    return prediction


def _debug_generator_trace(
    example_id: str,
    route: str,
    group_id: str,
) -> dict[str, Any]:
    transaction_id = f"generator:{example_id}:{route}"
    return {
        "contract_id": "qasper_typed_candidate_generation.v1",
        "status": "parsed",
        "model": "Qwen/Qwen3-8B",
        "message_stack": [
            {"index": 0, "role": "system", "content": "verify"},
            {"index": 1, "role": "user", "content": "question"},
        ],
        "raw_response": '{"candidate":"yes"}',
        "cleaned_response": '{"candidate":"yes"}',
        "typed_candidate": "yes",
        "typed_proposition": {
            "actor": "current_paper",
            "predicate": "use",
            "object_surface": "the method",
            "quantifier": "none",
        },
        "question_proposition_resolution": {"status": "complete"},
        "required_slots": [
            {
                "slot_id": "support:boolean_proposition",
                "binding_status": "bound",
                "evidence_ids": ["span:paper:s1"],
                "evidence_refs": ["E1:S1"],
            }
        ],
        "finish_reason": "stop",
        "failure_reason": "",
        "transformation_stages": [
            {
                "stage": "raw_response",
                "value": '{"candidate":"yes"}',
                "digest": "raw-digest",
                "failure_reason": "",
            },
            {
                "stage": "cleaning",
                "value": '{"candidate":"yes"}',
                "digest": "clean-digest",
                "changed": False,
                "failure_reason": "",
            },
            {
                "stage": "typed_candidate",
                "value": "yes",
                "digest": "typed-digest",
                "failure_reason": "",
            },
        ],
        "trace_group_id": group_id,
        "transaction_id": transaction_id,
        "attempt_id": f"{transaction_id}:1",
        "effective_seed": 20260724,
        "input_digest": f"generator-input:{route}",
        "output_digest": f"generator-output:{route}",
    }


def _debug_verifier_trace(
    example_id: str,
    route: str,
    group_id: str,
) -> dict[str, Any]:
    transaction_id = f"verifier:{example_id}:{route}"
    return {
        "contract_id": "semantic_proposition_verifier_runtime.v2",
        "status": "parsed",
        "model": "Qwen/Qwen3-8B",
        "candidate_label": "yes",
        "candidate_verification_status": "supported",
        "replacement_candidate_allowed": False,
        "explicit_contradiction": False,
        "candidate_verifier_disagreement": False,
        "unknown": False,
        "proposal_model_call_count": 1,
        "audit_model_call_count": 1,
        "candidate_verification_audit": {
            "contract_id": "candidate_verifier_audit.v1",
            "status": "passed",
            "mode": "semantic_entailment_audit",
            "audited_candidate": "yes",
            "audited_judgment": "supported",
            "replacement_candidate_allowed": False,
        },
        "debug_trace": _debug_semantic_trace(),
        "trace_group_id": group_id,
        "transaction_id": transaction_id,
        "attempt_id": f"{transaction_id}:proposal:1",
        "auditor_attempt_id": f"{transaction_id}:auditor:1",
        "effective_seed": 20260724,
        "input_digest": f"verifier-input:{route}",
        "output_digest": f"verifier-output:{route}",
    }


def _debug_semantic_trace() -> dict[str, Any]:
    return {
        "contract_id": "semantic_proposition_debug_trace.v2",
        "event_count": 1,
        "dropped_event_count": 0,
        "events": [
            {
                "event": "model_transaction",
                "transaction": {
                    "proposal": {
                        "status": "parsed",
                        "attempts": [
                            {
                                "attempt": 1,
                                "raw_response": '{"verdict":"yes"}',
                                "finish_reason": "stop",
                                "parse_failure_reason": "",
                                "provider_failure_reason": "",
                            }
                        ],
                    },
                    "audit": {
                        "status": "parsed",
                        "attempts": [
                            {
                                "attempt": 1,
                                "raw_response": '{"status":"verified"}',
                                "finish_reason": "stop",
                                "parse_failure_reason": "",
                                "provider_failure_reason": "",
                            }
                        ],
                    },
                },
            }
        ],
    }


def test_qasper_debug_contract_smoke_audits_6x3_observability(tmp_path):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    _write_run(run_dir, predictions=predictions)

    audit = validate(run_dir, suite_kind="qasper_debug")

    assert audit["contract"] == "contract_smoke_audit.v2"
    assert audit["prediction_count"] == 18
    assert audit["status"] == "passed"
    assert audit["observability_coverage"]["complete"] is True
    assert all(
        value == 18
        for value in audit["observability_coverage"]["covered_counts"].values()
    )
    matrix = audit["structural_state_matrix"]
    assert matrix["contract_id"] == "qasper_candidate_bound_state_matrix.v1"
    assert matrix["complete"] is True
    assert matrix["replacement_candidate_allowed"] is False
    assert len(matrix["cells"]) == 12
    assert {
        (
            cell["verifier_judgment"],
            cell["auditor_status"],
            cell["annotation_ambiguous"],
        )
        for cell in matrix["cells"]
    } == {
        (judgment, auditor_status, ambiguous)
        for judgment in ("supported", "contradicted", "unknown")
        for auditor_status in ("passed", "failed")
        for ambiguous in (False, True)
    }
    assert matrix["online_observation"]["prediction_count"] == 18
    assert matrix["online_observation"]["verifier_judgments"] == {
        "supported": 18,
        "contradicted": 0,
        "unknown": 0,
    }
    manifest = json.loads((run_dir / "artifact_manifest.json").read_text())
    assert "contract_smoke_audit.json" in manifest["required_files"]
    assert manifest["files"]["contract_smoke_audit.json"]["sha256"]


def test_qasper_debug_contract_smoke_fails_closed_on_missing_raw_response(
    tmp_path,
):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    del predictions[0]["evidence_metadata"]["qasper_candidate_generation"][
        "raw_response"
    ]
    _write_run(run_dir, predictions=predictions)

    with pytest.raises(ValueError, match="generator_field_missing:raw_response"):
        validate(run_dir, suite_kind="qasper_debug")

    audit = json.loads((run_dir / "contract_smoke_audit.json").read_text())
    assert audit["status"] == "failed"
    assert any(
        violation.startswith("generator_field_missing:raw_response")
        for violation in audit["behavior_violations"]
    )


def test_qasper_debug_contract_accepts_candidate_bound_unknown_audit(tmp_path):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    for prediction in predictions:
        verifier = prediction["evidence_metadata"]["semantic_proposition_verifier"]
        verifier["candidate_verification_status"] = "unknown"
        verifier["unknown"] = True
        verifier["candidate_verification_audit"]["audited_judgment"] = "unknown"
        prediction["predicted_answer"] = "unanswerable"
        prediction["answer_for_scoring"] = "unanswerable"
        prediction["terminal_semantic_commit"]["semantic_answer"] = "unanswerable"
        prediction["terminal_semantic_commit"]["outcome"] = "safe_abstention"
    _write_run(run_dir, predictions=predictions)

    audit = validate(run_dir, suite_kind="qasper_debug")

    assert audit["status"] == "passed"
    assert audit["structural_state_matrix"]["online_observation"][
        "verifier_judgments"
    ] == {"supported": 0, "contradicted": 0, "unknown": 18}


def test_qasper_debug_contract_rejects_invalid_relation_flags(tmp_path):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    predictions[0]["evidence_metadata"]["semantic_proposition_verifier"][
        "explicit_contradiction"
    ] = True
    _write_run(run_dir, predictions=predictions)

    with pytest.raises(ValueError, match="candidate_relation_flags_invalid"):
        validate(run_dir, suite_kind="qasper_debug")


def test_qasper_debug_contract_requires_online_candidate_bound_auditor(tmp_path):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    verifier = predictions[0]["evidence_metadata"]["semantic_proposition_verifier"]
    verifier["audit_model_call_count"] = 0
    verifier["candidate_verification_audit"]["mode"] = "deterministic_schema_audit"
    verifier["debug_trace"]["events"][0]["transaction"]["audit"] = {
        "status": "not_run",
        "attempts": [],
    }
    _write_run(run_dir, predictions=predictions)

    with pytest.raises(ValueError, match="online_auditor_not_observed"):
        validate(run_dir, suite_kind="qasper_debug")


def test_qasper_debug_contract_detects_candidate_single_label_collapse(tmp_path):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    for prediction in predictions:
        if prediction["example_id"] not in {"example-4", "example-5", "example-6"}:
            continue
        prediction["gold_answers"] = ["no"]
        prediction["example_metadata"]["qasper_answer_annotations"][0]["yes_no"] = False
        prediction["qasper_annotation_diagnostics"]["canonical_answer_classes"] = [
            ["no"]
        ]
    _write_run(run_dir, predictions=predictions)

    with pytest.raises(ValueError, match="candidate_single_label_collapse"):
        validate(run_dir, suite_kind="qasper_debug")

    audit = json.loads((run_dir / "contract_smoke_audit.json").read_text())
    observation = audit["structural_state_matrix"]["online_observation"]
    assert observation["generator_candidates"] == {
        "yes": 18,
        "no": 0,
        "unanswerable": 0,
    }
    assert observation["expected_annotation_labels"] == ["no", "yes"]
    assert observation["single_label_collapse"] is True


def test_qasper_debug_contract_requires_proposition_slot_binding_trace(tmp_path):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    generator = predictions[0]["evidence_metadata"]["qasper_candidate_generation"]
    del generator["typed_proposition"]["object_surface"]
    _write_run(run_dir, predictions=predictions)

    with pytest.raises(ValueError, match="candidate_proposition_binding_invalid"):
        validate(run_dir, suite_kind="qasper_debug")


def test_qasper_debug_contract_rejects_answer_with_missing_required_slot(tmp_path):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    slot = predictions[0]["evidence_metadata"]["qasper_candidate_generation"][
        "required_slots"
    ][0]
    slot.update(binding_status="missing", evidence_ids=[], evidence_refs=[])
    _write_run(run_dir, predictions=predictions)

    with pytest.raises(ValueError, match="candidate_required_slot_policy_mismatch"):
        validate(run_dir, suite_kind="qasper_debug")
