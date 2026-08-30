from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from scripts.slurm import qasper_natural_semantic_pack_probe as probe
from scripts.slurm.qasper_natural_semantic_pack_probe import probe_prediction


def _row() -> dict[str, object]:
    question = "Did the authors compare the two systems?"
    text = "The authors compared the two systems."
    return {
        "example_id": "natural-probe-example",
        "route": "text_rag",
        "question": question,
        "evidence_bundle": {
            "items": [
                {
                    "evidence_id": "natural-probe-evidence",
                    "source_id": "paper",
                    "text": text,
                }
            ]
        },
        "evidence_metadata": {
            "query_plan": {
                "evidence_slots": [
                    {
                        "slot_id": "support:boolean_proposition",
                        "description": "complete proposition support",
                        "required_for_verification": True,
                        "evidence_ids": [],
                        "evidence_refs": [],
                    }
                ]
            }
        },
        "qasper_annotation_diagnostics": {
            "ambiguity_reasons": [],
            "boolean_no_evidence_semantics": {},
        },
    }


def test_natural_probe_reuses_one_plan_across_pack_schema_parser_and_constraint() -> None:
    result = probe_prediction(_row(), code_sha="test-sha")

    assert result["status"] == "passed"
    assert result["binding_state"] == "relation_bound_support"
    assert result["schema_parser"]["schema_accepted"] is True
    assert result["schema_parser"]["parser_accepted"] is True
    assert result["schema_parser"]["downstream_status"] == "passed"
    assert all(result["checks"].values())


def test_natural_probe_rejects_unambiguous_unresolved_zero_plan() -> None:
    row = _row()
    row["evidence_bundle"] = {
        "items": [
            {
                "evidence_id": "natural-probe-evidence",
                "source_id": "paper",
                "text": "The paper discusses comparisons between systems.",
            }
        ]
    }

    result = probe_prediction(row, code_sha="test-sha")

    assert result["binding_state"] == "unresolved"
    assert result["canonical_plan_count"] == 0
    assert result["ambiguity"]["ambiguous"] is False
    assert result["checks"]["unambiguous_zero_plan_rejected"] is False
    assert result["status"] == "failed"


def test_natural_probe_rejects_a_plan_that_fails_the_audit_constraint(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        probe,
        "semantic_relation_evidence_set_constraint",
        lambda *_args, **_kwargs: {
            "status": "rejected",
            "reason": "audit_invalid_plan",
        },
    )

    result = probe_prediction(deepcopy(_row()), code_sha="test-sha")

    assert result["schema_parser"]["downstream_status"] == "rejected"
    assert result["checks"]["canonical_plan_audit_valid"] is False
    assert result["status"] == "failed"


def test_natural_probe_keeps_ambiguous_and_unambiguous_denominators_separate() -> None:
    ambiguous = _row()
    base_bundle = cast(dict[str, Any], _row()["evidence_bundle"])
    base_items = cast(list[dict[str, Any]], base_bundle["items"])
    ambiguous["evidence_bundle"] = {
        "items": [
            *base_items,
            {
                "evidence_id": "natural-probe-contradiction",
                "source_id": "paper",
                "text": "The authors did not compare the two systems.",
            },
        ]
    }
    ambiguous["qasper_annotation_diagnostics"] = {
        "ambiguous": True,
        "ambiguity_reasons": ["annotation_answer_disagreement"],
        "boolean_no_evidence_semantics": {},
    }

    audit = probe.build_audit(
        [
            probe_prediction(_row(), code_sha="test-sha"),
            probe_prediction(ambiguous, code_sha="test-sha"),
        ],
        code_sha="test-sha",
        input_path=__import__("pathlib").Path(__file__),
        expected_count=2,
    )

    assert audit["ambiguity_denominator"] == {
        "ambiguous": 1,
        "unambiguous": 1,
    }
