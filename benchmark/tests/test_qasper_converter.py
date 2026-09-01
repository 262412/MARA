import json

from benchmark.converters.qasper import normalize_qasper_manifest
from benchmark.manifest import load_manifest


def test_normalize_qasper_manifest_materializes_paper_text(tmp_path):
    source_path = tmp_path / "qasper.json"
    source_path.write_text(
        json.dumps(
            {
                "paper-1": {
                    "title": "Paper title",
                    "abstract": "Paper abstract.",
                    "full_text": [
                        {
                            "section_name": "Method",
                            "paragraphs": ["The method uses retrieval."],
                        }
                    ],
                    "qas": [
                        {
                            "question_id": "q1",
                            "question": "What does the method use?",
                            "answers": [
                                {
                                    "answer": {
                                        "extractive_spans": ["retrieval"],
                                        "free_form_answer": "",
                                        "yes_no": None,
                                        "evidence": ["The method uses retrieval."],
                                    }
                                },
                                {
                                    "answer": {
                                        "extractive_spans": [],
                                        "free_form_answer": "document retrieval",
                                        "yes_no": None,
                                        "evidence": ["The method uses retrieval."],
                                    }
                                },
                            ],
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    manifest_path = tmp_path / "qasper_manifest.json"
    normalize_qasper_manifest(source_path, manifest_path)

    bundle = load_manifest(manifest_path)
    assert bundle.dataset_name == "qasper"
    assert (
        bundle.documents["paper-1"]
        .path.read_text(encoding="utf-8")
        .startswith("# Paper title")
    )
    assert bundle.examples[0].answers == ["retrieval", "document retrieval"]
    assert bundle.examples[0].answer_type == "free_text"
    assert bundle.examples[0].evidence_sources == ["paper-1#evidence:1"]
    assert bundle.examples[0].gold_source_ids == ["paper-1"]
    assert bundle.examples[0].gold_evidence_texts == ["The method uses retrieval."]
    assert bundle.examples[0].metadata["dataset_family"] == "scientific_qa"
    assert bundle.examples[0].metadata["qasper_answer_annotations"] == [
        {
            "extractive_spans": ["retrieval"],
            "free_form_answer": "",
            "yes_no": None,
            "unanswerable": None,
            "evidence": ["The method uses retrieval."],
        },
        {
            "extractive_spans": [],
            "free_form_answer": "document retrieval",
            "yes_no": None,
            "unanswerable": None,
            "evidence": ["The method uses retrieval."],
        },
    ]


def test_normalize_qasper_manifest_uses_yes_no_not_python_booleans(tmp_path):
    source_path = tmp_path / "qasper_boolean.json"
    source_path.write_text(
        json.dumps(
            {
                "paper-1": {
                    "title": "Paper title",
                    "abstract": "Paper abstract.",
                    "full_text": [],
                    "qas": [
                        {
                            "question_id": "yes",
                            "question": "Was retrieval used?",
                            "answers": [
                                {
                                    "answer": {
                                        "extractive_spans": [],
                                        "free_form_answer": "",
                                        "yes_no": True,
                                        "evidence": ["Retrieval was used."],
                                    }
                                }
                            ],
                        },
                        {
                            "question_id": "no",
                            "question": "Was retrieval omitted?",
                            "answers": [
                                {
                                    "answer": {
                                        "extractive_spans": [],
                                        "free_form_answer": "",
                                        "yes_no": False,
                                        "evidence": ["Retrieval was used."],
                                    }
                                }
                            ],
                        },
                        {
                            "question_id": "unanswerable",
                            "question": "Was a graph retriever evaluated?",
                            "answers": [
                                {
                                    "answer": {
                                        "extractive_spans": [],
                                        "free_form_answer": "",
                                        "yes_no": None,
                                        "unanswerable": True,
                                        "evidence": [],
                                    }
                                }
                            ],
                        },
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    manifest_path = tmp_path / "qasper_boolean_manifest.json"
    normalize_qasper_manifest(source_path, manifest_path)
    bundle = load_manifest(manifest_path)

    assert [example.answers for example in bundle.examples] == [
        ["yes"],
        ["no"],
        ["unanswerable"],
    ]
    assert [example.answer_type for example in bundle.examples] == [
        "boolean",
        "boolean",
        "unanswerable",
    ]
    assert [example.metadata["qasper_answer_type"] for example in bundle.examples] == [
        "boolean",
        "boolean",
        "unanswerable",
    ]


def _qasper_reference_sets_bundle(tmp_path):
    source_path = tmp_path / "qasper_reference_sets.json"
    source_path.write_text(
        json.dumps(
            {
                "paper-1": {
                    "title": "Paper title",
                    "abstract": "Paper abstract.",
                    "full_text": [],
                    "figures_and_tables": [
                        {
                            "file": "3-Table1-1.png",
                            "caption": (
                                "Table 1: The compared systems use recurrent "
                                "architectures."
                            ),
                        }
                    ],
                    "qas": [
                        {
                            "question_id": "no-transformer",
                            "question": "Were transformer systems compared?",
                            "answers": [
                                {
                                    "annotation_id": "annotation-1",
                                    "worker_id": "worker-1",
                                    "answer": {
                                        "extractive_spans": [],
                                        "free_form_answer": "",
                                        "yes_no": False,
                                        "unanswerable": False,
                                        "evidence": [
                                            "FLOAT SELECTED: Table 1: The compared "
                                            "systems use recurrent architectures."
                                        ],
                                        "highlighted_evidence": [
                                            "FLOAT SELECTED: Table 1: The compared "
                                            "systems use recurrent architectures."
                                        ],
                                    },
                                },
                                {
                                    "annotation_id": "annotation-2",
                                    "worker_id": "worker-2",
                                    "answer": {
                                        "extractive_spans": [],
                                        "free_form_answer": "",
                                        "yes_no": False,
                                        "unanswerable": False,
                                        "evidence": [],
                                        "highlighted_evidence": [],
                                    },
                                },
                            ],
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    manifest_path = tmp_path / "qasper_reference_sets_manifest.json"
    normalize_qasper_manifest(source_path, manifest_path)
    return load_manifest(manifest_path)


def test_normalize_qasper_preserves_reference_sets_and_float_evidence(tmp_path):
    bundle = _qasper_reference_sets_bundle(tmp_path)
    document_text = bundle.documents["paper-1"].path.read_text(encoding="utf-8")
    example = bundle.examples[0]

    assert "## Figures and Tables" in document_text
    assert "### 3-Table1-1.png" in document_text
    assert (
        "FLOAT SELECTED: Table 1: The compared systems use recurrent architectures."
        in document_text
    )
    assert example.metadata["qasper_reference_set_contract"] == (
        "qasper_reference_sets.v1"
    )
    assert example.metadata["qasper_reference_sets"] == [
        {
            "reference_id": "annotation-1",
            "annotation_id": "annotation-1",
            "worker_id": "worker-1",
            "answer_type": "boolean",
            "answers": ["no"],
            "gold_support_mode": "multimodal",
            "evidence_texts": [
                "FLOAT SELECTED: Table 1: The compared systems use recurrent "
                "architectures."
            ],
            "highlighted_evidence_texts": [
                "FLOAT SELECTED: Table 1: The compared systems use recurrent "
                "architectures."
            ],
            "evidence_source_ids": ["paper-1#evidence:1"],
        },
        {
            "reference_id": "annotation-2",
            "annotation_id": "annotation-2",
            "worker_id": "worker-2",
            "answer_type": "boolean",
            "answers": ["no"],
            "gold_support_mode": "absence_bounded",
            "evidence_texts": [],
            "highlighted_evidence_texts": [],
            "evidence_source_ids": [],
        },
    ]
    assert example.metadata["qasper_answer_annotations"][0]["annotation_id"] == (
        "annotation-1"
    )
    assert example.metadata["qasper_answer_annotations"][0]["highlighted_evidence"] == [
        "FLOAT SELECTED: Table 1: The compared systems use recurrent architectures."
    ]
