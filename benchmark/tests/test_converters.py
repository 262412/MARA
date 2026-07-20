import json

import pyarrow as pa
import pyarrow.parquet as pq

from benchmark.converters.alce import normalize_alce_manifest
from benchmark.converters.mmdocrag import normalize_mmdocrag_manifest
from benchmark.converters.qasper import normalize_qasper_manifest
from benchmark.converters.ragtruth import normalize_ragtruth_manifest
from benchmark.converters.slidevqa import normalize_slidevqa_parquet_manifest
from benchmark.converters.vidore import normalize_vidore_manifest
from benchmark.manifest import load_manifest

_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\xff\xd9"
_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"


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
    assert bundle.examples[0].evidence_sources == ["The method uses retrieval."]
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


def test_normalize_mmdocrag_manifest_preserves_multimodal_gold_quotes(tmp_path):
    source_path = tmp_path / "dev.jsonl"
    source_path.write_text(
        json.dumps(
            {
                "q_id": 7,
                "doc_name": "report_2025",
                "question": "What does the chart show?",
                "answer_short": "Revenue rose",
                "evidence_modality_type": ["table", "text"],
                "gold_quotes": ["text1", "image1"],
                "text_quotes": [
                    {
                        "quote_id": "text1",
                        "text": "Revenue rose in 2025.",
                        "page_id": 3,
                        "layout_id": 31,
                    }
                ],
                "img_quotes": [
                    {
                        "quote_id": "image1",
                        "type": "table",
                        "img_path": "images/report_2025_table.jpg",
                        "img_description": "A revenue table.",
                        "page_id": 4,
                        "layout_id": 42,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_path = tmp_path / "mmdocrag_manifest.json"
    normalize_mmdocrag_manifest(source_path, manifest_path, documents_root=tmp_path)

    example = load_manifest(manifest_path).examples[0]
    assert example.modality == "multimodal"
    assert example.answers == ["Revenue rose"]
    assert example.evidence_pages == [3, 4]
    assert example.gold_evidence == [
        {
            "document_id": "report_2025",
            "page": 3,
            "element_id": "text1",
            "element_type": "text",
            "span": "Revenue rose in 2025.",
            "citation": "report_2025#page:3",
        },
        {
            "document_id": "report_2025",
            "page": 4,
            "element_id": "image1",
            "element_type": "table",
            "image_quote": "A revenue table.",
            "citation": "report_2025#page:4",
        },
    ]


def test_normalize_ragtruth_manifest_joins_sources_and_responses(tmp_path):
    source_info = tmp_path / "source_info.jsonl"
    responses = tmp_path / "response.jsonl"
    source_info.write_text(
        json.dumps(
            {
                "source_id": "s1",
                "task_type": "Summary",
                "source": "CNN/DM",
                "source_info": "The source says revenue rose.",
                "prompt": "Summarize the source.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    responses.write_text(
        json.dumps(
            {
                "id": "r1",
                "source_id": "s1",
                "response": "Revenue rose and profit doubled.",
                "labels": [{"label_type": "hallucination", "text": "profit doubled"}],
                "quality": "bad",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_path = tmp_path / "ragtruth_manifest.json"
    normalize_ragtruth_manifest(source_info, responses, manifest_path)

    manifest = load_manifest(manifest_path)
    document = manifest.documents["s1"]
    example = manifest.examples[0]

    assert document.path.read_text(encoding="utf-8").strip() == (
        "The source says revenue rose."
    )
    assert example.question == "Summarize the source."
    assert example.answers == ["Revenue rose and profit doubled."]
    assert example.gold_evidence == [
        {
            "document_id": "s1",
            "span": "The source says revenue rose.",
            "citation": "s1#source",
        }
    ]
    assert example.expected_guardrails == {
        "allow_abstention": True,
        "unsupported_claims_expected": True,
    }
    assert example.metadata["label_count"] == 1
    assert example.metadata["task_type"] == "Summary"
    assert example.metadata["source_info"] == "The source says revenue rose."
    assert example.metadata["response"] == "Revenue rose and profit doubled."
    assert example.metadata["source_label"] == "CNN/DM"


def test_normalize_alce_manifest_flattens_qa_pairs(tmp_path):
    source_path = tmp_path / "asqa_eval.json"
    source_path.write_text(
        json.dumps(
            [
                {
                    "qa_pairs": [
                        {
                            "question": "Who scored most?",
                            "short_answers": ["Ali"],
                            "context": "Ali scored most.",
                        }
                    ],
                    "annotations": [{"long_answer": "Ali scored most overall."}],
                }
            ]
        ),
        encoding="utf-8",
    )

    manifest_path = tmp_path / "alce_manifest.json"
    normalize_alce_manifest(source_path, manifest_path)

    bundle = load_manifest(manifest_path)
    assert bundle.dataset_name == "alce"
    assert bundle.examples[0].answers == ["Ali"]
    assert bundle.examples[0].evidence_sources == ["Ali scored most."]
    assert bundle.examples[0].metadata["dataset_family"] == "citation_quality"


def test_normalize_alce_manifest_preserves_qampari_answer_groups(tmp_path):
    source_path = tmp_path / "qampari_eval.json"
    source_path.write_text(
        json.dumps(
            [
                {
                    "id": "799__wikidata_simple__dev",
                    "question": "What manga was drawn by Ryoichi Ikegami?",
                    "answer": (
                        "Heat, Mai, the Psychic Girl, Wounded Man, Sanctuary, "
                        "Crying Freeman, Strain."
                    ),
                    "answers": [
                        ["Heat"],
                        ["Mai, the Psychic Girl"],
                        ["Wounded Man"],
                        ["Sanctuary"],
                        ["Crying Freeman"],
                        ["Strain"],
                    ],
                    "docs": [
                        {
                            "title": "Ryoichi Ikegami",
                            "text": "Ryoichi Ikegami drew Heat and Sanctuary.",
                            "id": "doc-1",
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    manifest_path = tmp_path / "alce_qampari_manifest.json"
    normalize_alce_manifest(source_path, manifest_path)

    bundle = load_manifest(manifest_path)
    assert bundle.dataset_name == "alce"
    example = bundle.examples[0]
    assert example.example_id == "799__wikidata_simple__dev"
    assert example.answer_type == "list_qa"
    assert example.answers == [
        "Heat, Mai, the Psychic Girl, Wounded Man, Sanctuary, "
        "Crying Freeman, Strain."
    ]
    assert example.evidence_sources == ["Ryoichi Ikegami drew Heat and Sanctuary."]
    assert example.metadata["alce_task"] == "qampari"
    assert example.metadata["alce_answers"] == [
        ["Heat"],
        ["Mai, the Psychic Girl"],
        ["Wounded Man"],
        ["Sanctuary"],
        ["Crying Freeman"],
        ["Strain"],
    ]


def test_normalize_vidore_manifest_accepts_jsonl_retrieval_rows(tmp_path):
    image_path = tmp_path / "page.png"
    image_path.write_text("image", encoding="utf-8")
    source_path = tmp_path / "vidore.jsonl"
    source_path.write_text(
        json.dumps(
            {
                "query": "Find the revenue table",
                "doc_id": "doc-1",
                "image_filename": "page.png",
                "page": 2,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_path = tmp_path / "vidore_manifest.json"
    normalize_vidore_manifest(source_path, manifest_path, documents_root=tmp_path)

    bundle = load_manifest(manifest_path)
    assert bundle.dataset_name == "vidore"
    assert bundle.documents["doc-1_page_2"].path == image_path.resolve()
    assert bundle.examples[0].answer_type == "retrieval"
    assert bundle.examples[0].gold_evidence == [
        {
            "document_id": "doc-1_page_2",
            "page": 2,
            "modality": "page_image",
            "citation": "doc-1_page_2#page:2",
        }
    ]


def test_normalize_vidore_manifest_materializes_embedded_image_bytes(tmp_path):
    source_path = tmp_path / "vidore.parquet"
    image_type = pa.struct([("bytes", pa.binary()), ("path", pa.string())])
    table = pa.table(
        {
            "query": ["Find the chart"],
            "doc_id": ["doc-1"],
            "page": ["7"],
            "image_filename": ["doc-1-page-7"],
            "image": pa.array(
                [{"bytes": _PNG_BYTES, "path": None}],
                type=image_type,
            ),
            "answer": ["chart"],
        }
    )
    pq.write_table(table, source_path)

    manifest_path = tmp_path / "vidore_manifest.json"
    normalize_vidore_manifest(source_path, manifest_path)

    bundle = load_manifest(manifest_path)
    document = bundle.documents["doc-1_page_7"]
    assert document.path == (tmp_path / "documents" / "doc-1_page_7.png").resolve()
    assert document.path.read_bytes() == _PNG_BYTES
    assert bundle.examples[0].evidence_pages == [7]


def test_normalize_slidevqa_parquet_manifest_materializes_page_images(tmp_path):
    source_path = tmp_path / "slidevqa.parquet"
    image_type = pa.struct([("bytes", pa.binary()), ("path", pa.string())])
    table = pa.table(
        {
            "deck_name": ["deck A"],
            "deck_url": ["https://example.test/deck-a"],
            "page_1": pa.array(
                [{"bytes": _JPEG_BYTES, "path": None}],
                type=image_type,
            ),
            "page_2": pa.array(
                [{"bytes": _PNG_BYTES, "path": None}],
                type=image_type,
            ),
            "qa_id": pa.array([123], type=pa.int64()),
            "question": ["Which page contains the chart?"],
            "answer": ["page two"],
            "evidence_pages": pa.array([[2]], type=pa.list_(pa.int64())),
        }
    )
    pq.write_table(table, source_path)

    manifest_path = tmp_path / "slidevqa_manifest.json"
    normalize_slidevqa_parquet_manifest(source_path, manifest_path)

    bundle = load_manifest(manifest_path)
    assert bundle.dataset_name == "slidevqa"
    assert sorted(bundle.documents) == ["deck_A_page_1", "deck_A_page_2"]
    assert (
        bundle.documents["deck_A_page_1"].path
        == (tmp_path / "documents" / "deck_A_page_1.jpg").resolve()
    )
    assert (
        bundle.documents["deck_A_page_2"].path
        == (tmp_path / "documents" / "deck_A_page_2.png").resolve()
    )
    assert bundle.documents["deck_A_page_1"].path.read_bytes() == _JPEG_BYTES
    assert bundle.documents["deck_A_page_2"].path.read_bytes() == _PNG_BYTES
    example = bundle.examples[0]
    assert example.example_id == "123"
    assert example.document_ids == ["deck_A_page_1", "deck_A_page_2"]
    assert example.evidence_pages == [2]
    assert example.gold_evidence == [
        {
            "document_id": "deck_A_page_2",
            "page": 2,
            "modality": "page_image",
            "citation": "deck_A_page_2#page:2",
        }
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
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    manifest_path = tmp_path / "qasper_boolean_manifest.json"
    normalize_qasper_manifest(source_path, manifest_path)
    bundle = load_manifest(manifest_path)

    assert [example.answers for example in bundle.examples] == [["yes"], ["no"]]
