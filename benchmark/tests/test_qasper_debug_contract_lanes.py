from __future__ import annotations

import hashlib
import json
from typing import Any

from benchmark.qasper_semantic_state_matrix import split_qasper_debug_predictions
from benchmark.tests.qasper_debug_contract_fixtures import _qasper_debug_prediction
from scripts.slurm.qasper_debug_contract import (
    _audit_relation_consistent,
    _recovery_transition_invalid,
    _relation_flags_valid,
    _required_slot_state_unverified,
    _reverify_state_changed,
    _verifier_observed,
    qasper_debug_audit_extensions,
    qasper_debug_contract_metrics,
)


def _rows() -> list[dict]:
    return [
        _qasper_debug_prediction(f"example-{example_index}", route)
        for example_index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]


def _required_slot_fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    prediction = _qasper_debug_prediction("example-1", "controller_auto")
    metadata = prediction["evidence_metadata"]
    verifier = metadata["semantic_proposition_verifier"]
    authority = metadata["semantic_proposition_authority"]
    audit = verifier["candidate_verification_audit"]
    return verifier, audit, authority


def _refresh_proposition_evidence_digest(authority: dict[str, Any]) -> None:
    payload = {
        "evidence_relation": authority["evidence_relation"],
        "proposition_slot_bindings": authority["proposition_slot_bindings"],
        "proposition_slot_evidence_refs": authority["proposition_slot_evidence_refs"],
        "proposition_binding_evidence_set_refs": authority[
            "proposition_binding_evidence_set_refs"
        ],
        "not_applicable_proposition_slots": authority[
            "not_applicable_proposition_slots"
        ],
    }
    authority["proposition_evidence_set_digest"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def test_lane_split_keeps_contract_probes_out_of_quality_rows() -> None:
    rows = _rows()
    for row in rows[:3]:
        row["qasper_debug_lane"] = "contract_probe"

    quality, probes = split_qasper_debug_predictions(rows)

    assert len(quality) == 15
    assert len(probes) == 3
    assert all(row.get("qasper_debug_lane") != "contract_probe" for row in quality)


def test_false_abstention_metric_uses_quality_rows_only() -> None:
    quality = _rows()[:3]
    probes = _rows()[3:4]
    for row in probes:
        row["qasper_debug_lane"] = "contract_probe"
        row["gold_answers"] = ["yes"]
        row["terminal_semantic_commit"]["semantic_answer"] = "unanswerable"

    metrics = qasper_debug_contract_metrics(
        quality,
        contract_probe_predictions=probes,
    )

    assert metrics["answerable_false_abstention_count"] == 0.0
    assert metrics["qasper_quality_prediction_count"] == 3.0
    assert metrics["qasper_contract_probe_prediction_count"] == 1.0


def test_lane_audit_exposes_quality_and_contract_probe_sections() -> None:
    rows = _rows()
    quality = rows[:3]
    probes = rows[3:]
    audit = qasper_debug_audit_extensions(
        quality,
        contract_probe_predictions=probes,
    )

    assert audit["quality_audit"]["prediction_count"] == 3
    assert audit["contract_probe_audit"]["prediction_count"] == 15
    assert audit["quality_lane"]["prediction_count"] == 3
    assert audit["contract_probe_lane"]["prediction_count"] == 15


def test_contract_probe_lane_is_non_vacuous_without_live_probe_rows() -> None:
    audit = qasper_debug_audit_extensions(_rows())

    probe = audit["contract_probe_audit"]
    assert probe["prediction_count"] == 0
    assert probe["execution"] == "live_model_rows"
    assert probe["non_vacuous"] is False
    assert probe["covered_state_cell_count"] == 0
    assert probe["status"] == "missing"
    assert audit["contract_probe_artifact"]["status"] == "missing"
    assert audit["contract_probe_artifact"]["source"] == "missing_live_prediction_rows"
    assert (
        audit["debug_gate_metrics"]["qasper_contract_probe_state_matrix_complete"]
        == 0.0
    )
    assert (
        audit["debug_gate_metrics"][
            "qasper_contract_probe_required_online_states_complete"
        ]
        == 0.0
    )
    assert (
        audit["debug_gate_metrics"]["qasper_contract_probe_live_state_matrix_complete"]
        == 0.0
    )


def test_quality_lane_uses_unambiguous_annotation_labels_for_requirements() -> None:
    rows = _rows()[:3]
    for row in rows:
        row["qasper_debug_lane"] = "quality"

    audit = qasper_debug_audit_extensions(rows)

    quality = audit["quality_audit"]
    assert quality["status"] == "passed"
    observation = quality["structural_state_matrix"]["quality_observation"]
    assert observation["missing_required_candidate_labels"] == []
    assert observation["missing_required_verifier_judgments"] == []
    assert observation["missing_required_auditor_statuses"] == []


def test_contract_probe_requires_live_negative_and_failed_audit_states() -> None:
    probes = _rows()[:3]
    for row in probes:
        row["qasper_debug_lane"] = "contract_probe"

    audit = qasper_debug_audit_extensions([], contract_probe_predictions=probes)

    probe = audit["contract_probe_audit"]
    assert probe["status"] == "failed"
    observation = probe["structural_state_matrix"]["contract_probe_observation"]
    assert observation["missing_required_candidate_labels"] == ["no"]
    assert observation["missing_required_verifier_judgments"] == [
        "contradicted",
        "unknown",
    ]
    assert observation["missing_required_auditor_statuses"] == ["failed"]
    assert (
        audit["debug_gate_metrics"][
            "qasper_contract_probe_online_required_auditor_status_missing_count"
        ]
        == 1.0
    )


def test_contract_probe_requires_actual_auditor_attempts() -> None:
    probes = _rows()[:3]
    for row in probes:
        row["qasper_debug_lane"] = "contract_probe"
    verifier = probes[0]["evidence_metadata"]["semantic_proposition_verifier"]
    verifier["audit_model_call_count"] = 0
    verifier["candidate_verification_audit"]["mode"] = "deterministic_schema_audit"
    verifier["debug_trace"]["events"][0]["transaction"]["audit"] = {
        "status": "not_run",
        "attempts": [],
    }

    audit = qasper_debug_audit_extensions([], contract_probe_predictions=probes)

    assert audit["contract_probe_audit"]["status"] == "failed"
    assert (
        audit["debug_gate_metrics"][
            "qasper_contract_probe_online_auditor_attempt_missing_count"
        ]
        == 1.0
    )


def test_contract_probe_passes_required_live_states_without_twelve_cell_cartesian() -> (
    None
):
    probes = _rows()
    for row in probes:
        row["qasper_debug_lane"] = "contract_probe"

    audit = qasper_debug_audit_extensions([], contract_probe_predictions=probes)

    probe = audit["contract_probe_audit"]
    assert probe["status"] == "passed"
    assert probe["live_state_matrix_complete"] is False
    metrics = audit["debug_gate_metrics"]
    assert metrics["qasper_contract_probe_required_online_states_complete"] == 1.0
    assert metrics["qasper_contract_probe_structural_state_matrix_complete"] == 1.0


def test_provider_only_metrics_ignore_absent_quality_label_observation() -> None:
    probes = _rows()
    for row in probes:
        row["qasper_debug_lane"] = "contract_probe"

    audit = qasper_debug_audit_extensions([], contract_probe_predictions=probes)

    metrics = audit["debug_gate_metrics"]
    assert metrics["qasper_candidate_verifier_auditor_label_set_mismatch_count"] == 0.0
    assert (
        audit["contract_probe_audit"]["debug_gate_metrics"][
            "qasper_candidate_verifier_auditor_label_set_mismatch_count"
        ]
        == 0.0
    )
    assert metrics["qasper_quality_prediction_count"] == 0.0
    assert metrics["qasper_quality_answerable_denominator_missing_count"] == 1.0


def test_provider_probe_rejects_any_conflicting_unknown_assessment_attempt() -> None:
    probes = _rows()
    for row in probes:
        row["qasper_debug_lane"] = "contract_probe"
    verifier = probes[0]["evidence_metadata"]["semantic_proposition_verifier"]
    proposal = verifier["debug_trace"]["events"][0]["transaction"]["proposal"]
    proposal["attempts"][0]["parse_failure_reason"] = "unexpected_unknown_assessment"

    audit = qasper_debug_audit_extensions([], contract_probe_predictions=probes)

    assert audit["contract_probe_audit"]["status"] == "failed"
    assert (
        audit["debug_gate_metrics"]["qasper_unexpected_unknown_assessment_count"] == 1.0
    )


def test_quality_online_observation_does_not_require_negative_probe_states() -> None:
    rows = _rows()[:3]
    for row in rows:
        row["qasper_debug_lane"] = "quality"

    audit = qasper_debug_audit_extensions(rows)
    online = audit["structural_state_matrix"]["online_observation"]

    assert online["lane"] == "quality"
    assert online["missing_required_verifier_judgments"] == []
    assert online["missing_required_auditor_statuses"] == []
    assert online["missing_required_annotation_ambiguity_states"] == []
    assert (
        audit["debug_gate_metrics"][
            "qasper_online_required_verifier_judgment_missing_count"
        ]
        == 0.0
    )


def test_verifier_observation_does_not_require_an_auditor_attempt() -> None:
    verifier = {"model": "test-model", "proposal_model_call_count": 1}

    assert _verifier_observed(verifier) is True


def test_raw_evidence_digest_only_does_not_trigger_reverify() -> None:
    assert (
        _reverify_state_changed(
            {
                "raw_evidence_digest_changed": True,
                "evidence_digest_before": "old",
                "evidence_digest_after": "new",
            }
        )
        is False
    )


def test_reverify_scans_all_semantic_change_signals() -> None:
    assert (
        _reverify_state_changed(
            {
                "semantic_pack_digest_before": "same",
                "semantic_pack_digest_after": "same",
                "semantic_pack_digest_changed": False,
                "proposition_binding_digest_before": "old",
                "proposition_binding_digest_after": "new",
            }
        )
        is True
    )


def test_empty_stop_without_reverify_is_invalid() -> None:
    assert (
        _recovery_transition_invalid(
            {
                "recovery_action": "stop_without_reverify",
                "stop_reason": "recovery_no_progress",
            }
        )
        is True
    )


def test_stop_without_reverify_requires_all_three_semantic_domains() -> None:
    transition = {
        "recovery_action": "stop_without_reverify",
        "stop_reason": "recovery_no_progress",
        "semantic_pack_digest_before": "pack",
        "semantic_pack_digest_after": "pack",
        "slot_state_digest_before": "slots",
        "slot_state_digest_after": "slots",
        "proposition_binding_digest_before": "binding",
        "proposition_binding_digest_after": "binding",
    }

    assert _recovery_transition_invalid(transition) is False
    transition.pop("proposition_binding_digest_after")
    assert _recovery_transition_invalid(transition) is True


def test_binding_reaudit_requires_a_binding_change() -> None:
    transition = {
        "recovery_action": "reaudit_changed_proposition_binding",
        "semantic_pack_digest_before": "old-pack",
        "semantic_pack_digest_after": "new-pack",
        "proposition_binding_digest_before": "same-binding",
        "proposition_binding_digest_after": "same-binding",
    }

    assert _recovery_transition_invalid(transition) is True
    transition["proposition_binding_digest_after"] = "new-binding"
    assert _recovery_transition_invalid(transition) is False


def test_unknown_relation_flags_follow_audited_relation() -> None:
    verifier = {
        "candidate_verification_status": "unknown",
        "verdict": "insufficient_evidence",
        "candidate_verification_audit": {
            "audited_judgment": "unknown",
            "classification": "unknown",
            "audited_verdict": "insufficient_evidence",
        },
        "explicit_contradiction": False,
        "candidate_verifier_disagreement": False,
        "unknown": True,
    }

    assert _relation_flags_valid(verifier, "unknown") is True


def test_relation_flags_distinguish_polarity_from_candidate_disagreement() -> None:
    cases = (
        ("yes", "supported", "yes", False, False, False),
        ("yes", "contradicted", "no", True, True, False),
        ("no", "supported", "no", True, False, False),
        ("no", "contradicted", "yes", False, True, False),
        ("yes", "unknown", "insufficient_evidence", False, False, True),
        ("unanswerable", "unknown", "insufficient_evidence", False, False, True),
    )
    for candidate, relation, verdict, explicit, disagreement, unknown in cases:
        verifier: dict[str, Any] = {
            "candidate_label": candidate,
            "candidate_verification_status": relation,
            "verdict": verdict,
            "explicit_contradiction": explicit,
            "candidate_verifier_disagreement": disagreement,
            "unknown": unknown,
        }

        assert _relation_flags_valid(verifier, relation) is True


def test_audit_conflict_does_not_broaden_relation_flags() -> None:
    verifier = {
        "candidate_label": "yes",
        "candidate_verification_status": "supported",
        "verdict": "yes",
        "candidate_verification_audit": {
            "audited_judgment": "supported",
            "classification": "unknown",
            "audited_verdict": "insufficient_evidence",
        },
        "explicit_contradiction": False,
        "candidate_verifier_disagreement": False,
        "unknown": False,
    }

    assert _relation_flags_valid(verifier, "supported") is True
    assert _audit_relation_consistent(verifier, "supported") is False


def test_audit_relation_is_exactly_candidate_bound() -> None:
    cases = (
        ("yes", "supported", "yes", "supported"),
        ("no", "supported", "no", "supported"),
        ("yes", "contradicted", "no", "explicit_contradiction"),
        ("no", "contradicted", "yes", "explicit_contradiction"),
        ("yes", "unknown", "insufficient_evidence", "unknown"),
        ("unanswerable", "unknown", "insufficient_evidence", "unknown"),
    )
    for candidate, relation, verdict, classification in cases:
        verifier: dict[str, Any] = {
            "candidate_label": candidate,
            "candidate_verification_audit": {
                "audited_judgment": relation,
                "audited_verdict": verdict,
                "classification": classification,
            },
        }
        assert _audit_relation_consistent(verifier, relation) is True

    verifier["candidate_verification_audit"]["classification"] = "invented"
    assert _audit_relation_consistent(verifier, relation) is False


def test_required_slot_gate_requires_one_exact_applicable_slot_evidence_set() -> None:
    evidence_refs = ["span:paper:s1#quote:0:30"]
    slot_spans = {
        "actor": (0, 9, "The paper"),
        "predicate": (9, 13, "uses"),
        "object": (13, 23, "the method"),
    }
    slot_evidence_refs = {
        slot: [f"{evidence_refs[0]}#slot:{slot}:{start}:{end}"]
        for slot, (start, end, _text) in slot_spans.items()
    }
    binding_payload = {
        "evidence_relation": "proposition_support",
        "proposition_slot_bindings": {
            "actor": "current_paper",
            "predicate": "use",
            "object": "the method",
        },
        "proposition_slot_evidence_refs": {
            slot: refs for slot, refs in slot_evidence_refs.items()
        },
        "proposition_binding_evidence_set_refs": evidence_refs,
        "not_applicable_proposition_slots": ["quantifier"],
    }
    authority: dict[str, Any] = {
        **binding_payload,
        "status": "verified",
        "required_slot_ids": ["support:boolean_proposition"],
        "verified_support_slot_ids": ["support:boolean_proposition"],
        "required_proposition_slots": ["actor", "predicate", "object"],
        "proposition_slot_evidence": {
            evidence_refs[0]: {
                slot: {
                    "evidence_ref": refs[0],
                    "text": text,
                    "span_start": start,
                    "span_end": end,
                    "clause_ref": "C1",
                    "clause_start": 0,
                    "clause_end": 30,
                }
                for slot, refs in slot_evidence_refs.items()
                for start, end, text in (slot_spans[slot],)
            }
        },
        "proposition_evidence_set_digest": hashlib.sha256(
            json.dumps(
                binding_payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    }
    verifier = {
        "candidate_label": "yes",
        "candidate_verification_status": "supported",
        "verdict": "yes",
        "question_proposition": {"quantifier": "none"},
    }
    audit = {"status": "passed"}
    metadata = {"semantic_proposition_authority": authority}

    assert _required_slot_state_unverified(verifier, audit, metadata) is False

    authority["proposition_slot_evidence_refs"] = {
        key: value
        for key, value in authority["proposition_slot_evidence_refs"].items()
        if key != "object"
    }
    assert _required_slot_state_unverified(verifier, audit, metadata) is True


def test_required_slot_gate_rejects_a_child_with_the_wrong_parent() -> None:
    verifier, audit, authority = _required_slot_fixture()
    parent = authority["proposition_binding_evidence_set_refs"][0]
    authority["proposition_slot_evidence_refs"]["actor"][
        0
    ] = "span:paper:s2#quote:0:30#slot:actor:0:9"
    authority["proposition_slot_evidence"][parent]["actor"]["evidence_ref"] = authority[
        "proposition_slot_evidence_refs"
    ]["actor"][0]
    _refresh_proposition_evidence_digest(authority)

    assert (
        _required_slot_state_unverified(
            verifier, audit, {"semantic_proposition_authority": authority}
        )
        is True
    )


def test_required_slot_gate_rejects_an_out_of_bounds_child_span() -> None:
    verifier, audit, authority = _required_slot_fixture()
    parent = authority["proposition_binding_evidence_set_refs"][0]
    child_ref = f"{parent}#slot:actor:0:31"
    authority["proposition_slot_evidence_refs"]["actor"][0] = child_ref
    authority["proposition_slot_evidence"][parent]["actor"].update(
        evidence_ref=child_ref,
        text="x" * 31,
        span_end=31,
    )
    _refresh_proposition_evidence_digest(authority)

    assert (
        _required_slot_state_unverified(
            verifier, audit, {"semantic_proposition_authority": authority}
        )
        is True
    )


def test_required_slot_gate_rejects_a_slot_name_mismatch() -> None:
    verifier, audit, authority = _required_slot_fixture()
    parent = authority["proposition_binding_evidence_set_refs"][0]
    authority["proposition_slot_evidence_refs"]["actor"][
        0
    ] = f"{parent}#slot:predicate:0:9"
    _refresh_proposition_evidence_digest(authority)

    assert (
        _required_slot_state_unverified(
            verifier, audit, {"semantic_proposition_authority": authority}
        )
        is True
    )


def test_required_slot_gate_rejects_slot_text_length_tampering() -> None:
    verifier, audit, authority = _required_slot_fixture()
    parent = authority["proposition_binding_evidence_set_refs"][0]
    authority["proposition_slot_evidence"][parent]["actor"]["text"] = "short"
    _refresh_proposition_evidence_digest(authority)

    assert (
        _required_slot_state_unverified(
            verifier, audit, {"semantic_proposition_authority": authority}
        )
        is True
    )


def test_required_slot_gate_rejects_child_offset_tampering() -> None:
    verifier, audit, authority = _required_slot_fixture()
    parent = authority["proposition_binding_evidence_set_refs"][0]
    authority["proposition_slot_evidence"][parent]["actor"]["span_start"] = 1

    assert (
        _required_slot_state_unverified(
            verifier, audit, {"semantic_proposition_authority": authority}
        )
        is True
    )


def test_required_slot_gate_rejects_a_tampered_evidence_set_digest() -> None:
    verifier, audit, authority = _required_slot_fixture()
    authority["proposition_evidence_set_digest"] = "tampered"

    assert (
        _required_slot_state_unverified(
            verifier, audit, {"semantic_proposition_authority": authority}
        )
        is True
    )
