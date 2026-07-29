import json

import pytest

from benchmark.manifest import load_manifest


def test_qasper_gold_text_is_not_interpreted_as_a_source_id(tmp_path):
    (tmp_path / "paper.txt").write_text("paper", encoding="utf-8")
    evidence_text = (
        "This natural-language evidence sentence is deliberately much longer "
        "than a source identifier."
    )
    manifest_path = tmp_path / "qasper-v2.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "qasper",
                "documents": [
                    {
                        "document_id": "paper",
                        "path": "paper.txt",
                        "format_type": "txt",
                    }
                ],
                "examples": [
                    {
                        "example_id": "q1",
                        "document_ids": ["paper"],
                        "question": "What evidence is reported?",
                        "answers": ["the evidence"],
                        "evidence_sources": [evidence_text],
                        "gold_evidence": [
                            {
                                "document_id": "paper",
                                "span": evidence_text,
                                "citation": "paper#evidence:1",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    example = load_manifest(manifest_path).examples[0]

    assert example.gold_source_ids == ["paper"]
    assert example.gold_evidence_texts == [evidence_text]
    assert example.evidence_sources == ["paper#evidence:1"]


def test_manifest_rejects_invalid_gold_source_schema(tmp_path):
    (tmp_path / "paper.txt").write_text("paper", encoding="utf-8")
    manifest_path = tmp_path / "invalid-v2.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "qasper",
                "documents": [
                    {
                        "document_id": "paper",
                        "path": "paper.txt",
                        "format_type": "txt",
                    }
                ],
                "examples": [
                    {
                        "example_id": "q1",
                        "document_ids": ["paper"],
                        "question": "What evidence is reported?",
                        "answers": ["the evidence"],
                        "gold_source_ids": [
                            "This is evidence prose, not a document identifier."
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="gold_source_schema_invalid"):
        load_manifest(manifest_path)
