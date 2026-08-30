from __future__ import annotations

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
