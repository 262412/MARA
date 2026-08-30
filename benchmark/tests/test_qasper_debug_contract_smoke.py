from __future__ import annotations

import json
from copy import deepcopy

import pytest
from ktem.docqa.qasper_semantic_pack_contract import (
    qasper_canonical_span_universe_digest,
)

from benchmark.tests.contract_smoke_fixtures import _fixture_digest, _write_run
from benchmark.tests.qasper_debug_contract_fixtures import (
    _debug_candidate_audit,
    _debug_unknown_assessment,
    _qasper_contract_probe_predictions,
)
from benchmark.tests.qasper_debug_contract_fixtures import (
    _qasper_debug_prediction as _base_qasper_debug_prediction,
)
from benchmark.tests.qasper_debug_semantic_pack_fixtures import _debug_semantic_pack
from scripts.slurm.qasper_debug_contract_pre_audit_provider import (
    controlled_pre_audit_model_factory,
)
from scripts.slurm.qasper_debug_contract_probe import run_pre_audit_probes
from scripts.slurm.qasper_debug_contract_semantic_pack import _pack_identity_valid
from scripts.slurm.validate_contract_smoke import QASPER_DEBUG_HARD_GATES, validate
from scripts.slurm.validate_qasper_contract_probe import validate_contract_probe


def _qasper_debug_prediction(example_id: str, route: str):
    state = ("unknown", "passed", True) if example_id == "example-5" else None
    candidate = "no" if example_id == "example-5" else None
    return _base_qasper_debug_prediction(
        example_id,
        route,
        state=state,
        candidate=candidate,
    )


def _write_qasper_run(run_dir, *, predictions):
    _write_run(run_dir, predictions=predictions)
    probe_path = run_dir / "contract_probe_predictions.jsonl"
    probe_path.write_text(
        "".join(
            f"{json.dumps(row, ensure_ascii=False)}\n"
            for row in _qasper_contract_probe_predictions()
        ),
        encoding="utf-8",
    )
    pre_audit_path = run_dir / "contract_pre_audit_predictions.jsonl"
    run_pre_audit_probes(
        "http://pre-audit-proposer.invalid/v1",
        "pre-audit-proposer",
        auditor_base_url="http://pre-audit-auditor.invalid/v1",
        auditor_model="pre-audit-auditor",
        model_factory=controlled_pre_audit_model_factory,
        output_path=pre_audit_path,
    )
    validate_contract_probe(
        probe_path,
        output_path=run_dir / "contract_probe_audit.json",
        pre_audit_predictions_path=pre_audit_path,
    )


def test_qasper_debug_contract_declares_special_hard_gates():
    assert {
        "answerable_false_abstention_count",
        "qasper_candidate_verifier_auditor_label_set_mismatch_count",
        "qasper_online_required_candidate_label_missing_count",
        "qasper_online_required_verifier_judgment_missing_count",
        "qasper_online_required_auditor_status_missing_count",
        "qasper_online_required_annotation_ambiguity_missing_count",
        "qasper_online_auditor_attempt_missing_count",
        "qasper_online_verifier_missing_count",
        "qasper_contract_probe_structural_state_matrix_complete",
        "qasper_contract_probe_required_online_states_complete",
        "qasper_candidate_raw_identity_mismatch_count",
        "qasper_controlled_candidate_transport_mismatch_count",
        "qasper_empty_candidate_audit_count",
        "qasper_empty_typed_conclusion_count",
        "qasper_semantic_entailment_audit_failure_count",
        "qasper_semantic_entailment_audit_rejection_count",
        "qasper_required_slot_unverified_count",
        "qasper_reverify_without_semantic_state_change_count",
        "qasper_canonical_semantic_pack_mismatch_count",
        "qasper_unexpected_unknown_assessment_count",
        "qasper_contract_probe_unexpected_false_abstention_count",
    } <= set(QASPER_DEBUG_HARD_GATES)


def test_formal_pack_audit_rejects_rehashed_invalid_child_span() -> None:
    pack = _debug_semantic_pack("candidate-transaction")
    child = pack["records"][0]["selectors"][0]["proposition_slot_spans"]["predicate"]
    child["text_digest"] = "invalid-child-digest"
    pack["span_universe_digest"] = qasper_canonical_span_universe_digest(
        pack["records"]
    )
    payload = deepcopy(pack)
    payload.pop("pack_identity_digest")
    pack["pack_identity_digest"] = _fixture_digest(payload)

    assert (
        _pack_identity_valid(pack, question="Does the paper use the method?") is False
    )


def test_qasper_debug_contract_smoke_audits_6x3_observability(tmp_path):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    _write_qasper_run(run_dir, predictions=predictions)

    audit = validate(run_dir, suite_kind="qasper_debug")

    assert audit["contract"] == "contract_smoke_audit.v2"
    assert audit["prediction_count"] == 18
    assert audit["status"] == "passed"
    assert audit["observability_coverage"]["complete"] is True
    covered = audit["observability_coverage"]["covered_counts"]
    assert covered["candidate_verifier_audit"] == 18
    assert covered["auditor_failed_safe_abstention"] == 0
    assert audit["observability_coverage"]["auditor_outcome_coverage"] == 18
    assert all(
        value == 18
        for key, value in covered.items()
        if key not in {"auditor_failed_safe_abstention"}
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
        "supported": 9,
        "contradicted": 3,
        "unknown": 6,
    }
    manifest = json.loads((run_dir / "artifact_manifest.json").read_text())
    assert "contract_smoke_audit.json" in manifest["required_files"]
    assert manifest["files"]["contract_smoke_audit.json"]["sha256"]
    assert "contract_probe_predictions.jsonl" in manifest["required_files"]
    assert manifest["files"]["contract_probe_predictions.jsonl"]["line_count"] == len(
        _qasper_contract_probe_predictions()
    )
    assert "contract_probe_audit.json" in manifest["required_files"]
    assert "contract_pre_audit_predictions.jsonl" in manifest["required_files"]
    assert manifest["files"]["contract_pre_audit_predictions.jsonl"]["line_count"] == 4


def test_qasper_debug_contract_smoke_requires_live_probe_artifact(tmp_path):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    _write_run(run_dir, predictions=predictions)

    with pytest.raises(
        ValueError,
        match="qasper_contract_probe_required_online_states_complete",
    ):
        validate(run_dir, suite_kind="qasper_debug")

    audit = json.loads((run_dir / "contract_smoke_audit.json").read_text())
    assert audit["contract_probe_artifact"]["status"] == "missing"
    assert audit["contract_probe_artifact"]["prediction_count"] == 0


def test_qasper_debug_contract_smoke_rejects_stale_provider_probe_audit(tmp_path):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    _write_qasper_run(run_dir, predictions=predictions)
    with (run_dir / "contract_probe_predictions.jsonl").open("a") as handle:
        handle.write("{}\n")

    with pytest.raises(
        ValueError,
        match="provider_contract_probe_audit_digest_mismatch",
    ):
        validate(run_dir, suite_kind="qasper_debug")


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
    _write_qasper_run(run_dir, predictions=predictions)

    with pytest.raises(ValueError, match="generator_field_missing:raw_response"):
        validate(run_dir, suite_kind="qasper_debug")

    audit = json.loads((run_dir / "contract_smoke_audit.json").read_text())
    assert audit["status"] == "failed"
    assert any(
        violation.startswith("generator_field_missing:raw_response")
        for violation in audit["behavior_violations"]
    )


def test_qasper_debug_contract_fails_closed_on_semantic_pack_drift(tmp_path):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    predictions[0]["evidence_metadata"]["semantic_proposition_verifier"][
        "semantic_pack_digest"
    ] = "different-pack"
    _write_qasper_run(run_dir, predictions=predictions)

    with pytest.raises(
        ValueError,
        match="qasper_canonical_semantic_pack_mismatch_count",
    ):
        validate(run_dir, suite_kind="qasper_debug")

    audit = json.loads((run_dir / "contract_smoke_audit.json").read_text())
    assert audit["status"] == "failed"
    assert (
        audit["debug_gate_metrics"]["qasper_canonical_semantic_pack_mismatch_count"]
        == 1.0
    )


def test_qasper_debug_contract_accepts_candidate_bound_unknown_audit(tmp_path):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    for prediction in predictions:
        if prediction["example_id"] != "example-1":
            continue
        verifier = prediction["evidence_metadata"]["semantic_proposition_verifier"]
        verifier["candidate_verification_status"] = "unknown"
        verifier["explicit_contradiction"] = False
        verifier["candidate_verifier_disagreement"] = False
        verifier["unknown"] = True
        verifier["audit_contract_id"] = "candidate_verifier_audit.v2"
        verifier["audit_status"] = "candidate_bound"
        verifier["candidate_verification_audit"] = _debug_candidate_audit(
            verifier["candidate_label"],
            "unknown",
            verifier["candidate_verification_audit"]["status"],
            verifier["typed_conclusion"],
        )
        verifier["unknown_assessment"] = _debug_unknown_assessment("unknown")
        prediction["gold_answers"] = ["unanswerable"]
        prediction["predicted_answer"] = "unanswerable"
        prediction["answer_for_scoring"] = "unanswerable"
        prediction["terminal_semantic_commit"]["semantic_answer"] = "unanswerable"
        prediction["terminal_semantic_commit"]["outcome"] = "safe_abstention"
    _write_qasper_run(run_dir, predictions=predictions)

    audit = validate(run_dir, suite_kind="qasper_debug")

    assert audit["status"] == "passed"
    assert audit["structural_state_matrix"]["online_observation"][
        "verifier_judgments"
    ] == {"supported": 6, "contradicted": 3, "unknown": 9}


def test_qasper_debug_rejects_empty_unknown_audit_premises(tmp_path):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    for prediction in predictions:
        verifier = prediction["evidence_metadata"]["semantic_proposition_verifier"]
        if verifier["candidate_verification_status"] == "unknown":
            verifier["candidate_verification_audit"]["audited_premises"] = []
            break
    _write_qasper_run(run_dir, predictions=predictions)

    with pytest.raises(ValueError, match="candidate_verifier_audit_empty"):
        validate(run_dir, suite_kind="qasper_debug")


def test_qasper_debug_accepts_recovery_stop_without_reverify(tmp_path):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    verifier = predictions[0]["evidence_metadata"]["semantic_proposition_verifier"]
    verifier["recovery_transitions"] = [
        {
            "recovery_action": "stop_without_reverify",
            "stop_reason": "recovery_no_progress",
            "semantic_pack_digest_changed": False,
            "evidence_digest_before": "evidence",
            "evidence_digest_after": "evidence",
            "evidence_digest_changed": False,
            "slot_state_digest_before": "slots",
            "slot_state_digest_after": "slots",
            "slot_state_digest_changed": False,
            "proposition_binding_digest_before": "binding",
            "proposition_binding_digest_after": "binding",
            "proposition_binding_digest_changed": False,
        }
    ]
    _write_qasper_run(run_dir, predictions=predictions)

    audit = validate(run_dir, suite_kind="qasper_debug")

    assert (
        audit["debug_gate_metrics"][
            "qasper_reverify_without_semantic_state_change_count"
        ]
        == 0.0
    )


def test_qasper_debug_rejects_reaudit_without_changed_binding(tmp_path):
    run_dir = tmp_path / "run"
    predictions = [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    verifier = predictions[0]["evidence_metadata"]["semantic_proposition_verifier"]
    verifier["recovery_transitions"] = [
        {
            "recovery_action": "reaudit_changed_proposition_binding",
            "proposition_binding_digest_before": "same",
            "proposition_binding_digest_after": "same",
            "proposition_binding_digest_changed": False,
        }
    ]
    _write_qasper_run(run_dir, predictions=predictions)

    with pytest.raises(
        ValueError,
        match="qasper_reverify_without_semantic_state_change_count",
    ):
        validate(run_dir, suite_kind="qasper_debug")


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
    _write_qasper_run(run_dir, predictions=predictions)

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
    _write_qasper_run(run_dir, predictions=predictions)

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
        if prediction["example_id"] != "example-1":
            continue
        prediction["gold_answers"] = ["unanswerable"]
        prediction["example_metadata"]["qasper_answer_annotations"][0]["yes_no"] = False
        prediction["qasper_annotation_diagnostics"]["canonical_answer_classes"] = [
            ["unanswerable"]
        ]
    _write_qasper_run(run_dir, predictions=predictions)

    with pytest.raises(ValueError, match="candidate_single_label_collapse"):
        validate(run_dir, suite_kind="qasper_debug")

    audit = json.loads((run_dir / "contract_smoke_audit.json").read_text())
    observation = audit["structural_state_matrix"]["online_observation"]
    assert observation["generator_candidates"] == {
        "yes": 12,
        "no": 6,
        "unanswerable": 0,
    }
    assert observation["expected_annotation_labels"] == ["unanswerable", "yes"]
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
    _write_qasper_run(run_dir, predictions=predictions)

    with pytest.raises(ValueError, match="candidate_proposition_binding_invalid"):
        validate(run_dir, suite_kind="qasper_debug")


def test_qasper_debug_contract_rejects_generator_pack_slot_divergence(tmp_path):
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
    candidate = predictions[0]["evidence_metadata"]["qasper_candidate_generation"][
        "typed_candidate"
    ]
    _write_qasper_run(run_dir, predictions=predictions)

    with pytest.raises(
        ValueError,
        match="qasper_canonical_semantic_pack_mismatch_count",
    ):
        validate(run_dir, suite_kind="qasper_debug")

    assert (
        predictions[0]["evidence_metadata"]["qasper_candidate_generation"][
            "typed_candidate"
        ]
        == candidate
    )
    audit = json.loads((run_dir / "contract_smoke_audit.json").read_text())
    assert audit["status"] == "failed"
