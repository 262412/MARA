from __future__ import annotations

from typing import Any

from benchmark.dataset_native_scores import native_metrics_for_prediction
from benchmark.metrics import safe_mean
from benchmark.qasper_semantic_state_matrix import qasper_candidate_bound_state_matrix
from benchmark.tests.qasper_debug_contract_fixtures import _qasper_debug_prediction
from scripts.slurm import qasper_debug_contract_audit as audit
from scripts.slurm.qasper_debug_contract import qasper_debug_contract_metrics


def _row_with_terminal_answer(example_id: str, answer: str) -> dict[str, Any]:
    row = _qasper_debug_prediction(example_id, "text_rag")
    row["gold_answers"] = ["yes"]
    row["predicted_answer"] = answer
    row["answer_for_scoring"] = answer
    row["terminal_outcome"] = (
        "answered" if answer != "unanswerable" else "safe_abstention"
    )
    row["answer_status"] = "answered" if answer != "unanswerable" else "abstained"
    row["terminal_semantic_commit"]["semantic_answer"] = answer
    row["terminal_semantic_commit"]["outcome"] = row["terminal_outcome"]
    return row


def _native_snapshot(rows: list[dict[str, Any]]) -> tuple[int, float | None]:
    scores = [
        native_metrics_for_prediction(row, dataset_name="qasper-dev")[0]["native_score"]
        for row in rows
    ]
    return len(scores), safe_mean(scores)


def _mark_semantically_unresolved(row: dict[str, Any]) -> None:
    metadata = row["evidence_metadata"]
    metadata.pop("semantic_proposition_authority", None)
    verifier = metadata["semantic_proposition_verifier"]
    verifier.update(
        candidate_verification_status="unknown",
        verdict="insufficient_evidence",
        explicit_contradiction=False,
        candidate_verifier_disagreement=False,
        unknown=True,
    )


def test_expected_ambiguity_unresolved_is_separate_from_unambiguous_gate_and_native_score() -> None:
    rows = [
        # The fixture's example-3 annotation is ambiguous and intentionally
        # unresolved, so its abstention must be diagnosed separately.
        _row_with_terminal_answer("example-3", "unanswerable"),
        # The fixture's example-2 annotation is unambiguous and unresolved, so
        # its abstention must remain in the hard false-abstention gate.
        _row_with_terminal_answer("example-2", "unanswerable"),
        _row_with_terminal_answer("example-1", "yes"),
    ]
    _mark_semantically_unresolved(rows[0])
    _mark_semantically_unresolved(rows[1])

    native_before = _native_snapshot(rows)
    metrics = qasper_debug_contract_metrics(rows)
    native_after = _native_snapshot(rows)

    assert metrics["qasper_quality_expected_ambiguity_unresolved_count"] == 1.0
    assert metrics["qasper_quality_unambiguous_false_abstention_count"] == 1.0
    assert metrics["qasper_quality_expected_ambiguity_row_count"] == 1.0
    assert metrics["qasper_quality_unambiguous_answerable_row_count"] == 2.0
    assert (
        metrics["qasper_quality_expected_ambiguity_required_slot_unverified_count"]
        == 1.0
    )
    assert (
        metrics["qasper_quality_unambiguous_answerable_required_slot_unverified_count"]
        == 1.0
    )
    # Compatibility hard-gate metrics are explicitly the unambiguous cohort.
    assert metrics["answerable_false_abstention_count"] == 1.0
    assert metrics["qasper_required_slot_unverified_count"] == 1.0
    assert metrics["qasper_quality_answerable_row_count"] == 3.0
    assert native_before == (3, 1 / 3)
    assert native_after == native_before


def test_semantic_auditor_rejection_is_not_counted_as_execution_failure() -> None:
    prediction = _qasper_debug_prediction("example-1", "text_rag")
    prediction["qasper_debug_lane"] = "quality"
    verifier = prediction["evidence_metadata"]["semantic_proposition_verifier"]
    verifier.update(
        audit_status="rejected",
        audit_reason="premise_proposition_binding_rejected",
    )
    candidate_audit = verifier["candidate_verification_audit"]
    candidate_audit.update(
        status="failed",
        reason="semantic_entailment_audit_rejected",
    )

    failed, rejected = audit._semantic_audit_failure_flags(
        verifier,
        candidate_audit,
        prediction,
    )
    metrics = qasper_debug_contract_metrics([prediction])

    assert (failed, rejected) == (False, True)
    assert metrics["qasper_semantic_entailment_audit_failure_count"] == 0.0
    assert metrics["qasper_semantic_entailment_audit_rejection_count"] == 1.0


def test_ambiguous_no_does_not_force_quality_candidate_label_but_probe_still_does() -> None:
    quality_yes = _qasper_debug_prediction("example-1", "text_rag")
    ambiguous_no = _qasper_debug_prediction(
        "example-3",
        "text_rag",
        candidate="unanswerable",
    )
    ambiguous_no["gold_answers"] = ["no"]
    ambiguous_no["qasper_annotation_diagnostics"].update(
        ambiguous=True,
        ambiguity_reasons=["boolean_no_requires_closed_world_inference"],
        canonical_answer_classes=[["no"]],
    )

    quality_matrix = qasper_candidate_bound_state_matrix(
        [quality_yes, ambiguous_no],
        quality_predictions=[quality_yes, ambiguous_no],
        contract_probe_predictions=[],
    )
    quality = quality_matrix["quality_observation"]

    assert quality["expected_annotation_labels"] == ["yes"]
    assert quality["observed_candidate_labels"] == ["unanswerable", "yes"]
    assert quality["missing_required_candidate_labels"] == []
    assert quality["single_label_collapse"] is False

    for row in (quality_yes, ambiguous_no):
        row["qasper_debug_lane"] = "contract_probe"
    probe_matrix = qasper_candidate_bound_state_matrix(
        [],
        quality_predictions=[],
        contract_probe_predictions=[quality_yes, ambiguous_no],
    )
    probe = probe_matrix["contract_probe_observation"]

    assert probe["missing_required_candidate_labels"] == ["no"]
    assert probe["single_label_collapse"] is True
