import json
from pathlib import Path

from benchmark.manifest import load_manifest
from benchmark.manifest_templates import apply_route_template


def test_apply_route_template_materializes_dataset_manifest_routes(tmp_path):
    manifest_path = tmp_path / "qasper.base.json"
    template_path = tmp_path / "text-template.json"
    output_path = tmp_path / "qasper.routes.json"
    (tmp_path / "paper.txt").write_text("paper text", encoding="utf-8")
    _write_json(manifest_path, _base_qasper_manifest())
    _write_json(template_path, _route_template())

    result_path = apply_route_template(
        manifest_path,
        template_path,
        output_path,
        dataset_name="qasper_plan5_text_main",
    )

    assert result_path == output_path.resolve()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["dataset_name"] == "qasper_plan5_text_main"
    assert payload["documents"][0]["document_id"] == "paper"
    assert payload["examples"][0]["example_id"] == "ex"

    bundle = load_manifest(output_path)
    assert [route["route_id"] for route in bundle.routes] == [
        "text_rag",
        "controller_auto",
    ]
    assert bundle.routes[1]["allowed_routes"] == [
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    ]


def test_bundled_text_templates_use_benchmark_direct_answer_engine():
    template_dir = Path(__file__).parents[1] / "manifests" / "templates"

    for filename in ("mara_text_only.json", "mara_all_routes.local.json"):
        payload = json.loads((template_dir / filename).read_text(encoding="utf-8"))
        direct_route = next(
            route
            for route in payload["routes"]
            if route.get("route_id") == "direct_answer"
        )

        assert direct_route["engine"] == "benchmark_direct_answer"


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _base_qasper_manifest():
    return {
        "schema_version": 2,
        "dataset_name": "qasper",
        "documents": [
            {
                "document_id": "paper",
                "path": "paper.txt",
                "format_type": "txt",
                "metadata": {"title": "Paper"},
            }
        ],
        "examples": [
            {
                "example_id": "ex",
                "document_ids": ["paper"],
                "question": "What does it study?",
                "answers": ["text classification"],
                "answer_type": "abstractive",
            }
        ],
    }


def _route_template():
    return {
        "schema_version": 2,
        "dataset_name": "template",
        "documents": [],
        "examples": [],
        "routes": [
            {
                "route_id": "text_rag",
                "engine": "docqa_runtime",
                "scope": "multi_document",
                "allowed_routes": ["doc_text"],
            },
            {
                "route_id": "controller_auto",
                "engine": "docqa_runtime",
                "scope": "multi_document",
                "allowed_routes": [
                    "doc_text",
                    "hybrid",
                    "doc_page_image",
                    "doc_element",
                    "graph_global",
                ],
            },
        ],
    }
