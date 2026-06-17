import json

from benchmark.manifest import load_manifest


def test_load_v1_manifest_sets_v2_defaults(tmp_path):
    (tmp_path / "doc.pdf").write_text("pdf", encoding="utf-8")
    manifest_path = tmp_path / "v1.json"
    manifest_path.write_text(
        json.dumps(
            {
                "dataset_name": "v1_suite",
                "examples": [
                    {
                        "document_id": "doc",
                        "document_path": "doc.pdf",
                        "question": "What is it?",
                        "answer": "pdf",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    bundle = load_manifest(manifest_path)
    example = bundle.examples[0]

    assert bundle.schema_version == 1
    assert example.scope == "document"
    assert example.modality == "text"
    assert example.answer_type == "extractive"
    assert example.document_ids == ["doc"]


def test_load_manifest_accepts_utf8_bom(tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "bom.json"
    manifest_path.write_text(
        '\ufeff{"dataset_name": "bom", "examples": ['
        '{"document_id": "doc", "document_path": "doc.txt", '
        '"question": "What?", "answer": "alpha"}]}',
        encoding="utf-8",
    )

    bundle = load_manifest(manifest_path)

    assert bundle.dataset_name == "bom"
    assert bundle.examples[0].answers == ["alpha"]
