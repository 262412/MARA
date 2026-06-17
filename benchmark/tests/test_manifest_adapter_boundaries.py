import json
from pathlib import Path

from benchmark.dataset_profiles import profile_for_manifest
from benchmark.manifest import load_manifest


def test_load_manifest_does_not_parse_financebench_evidence_for_generic_dataset(
    tmp_path,
):
    (tmp_path / "generic.pdf").write_text("pdf", encoding="utf-8")
    manifest_path = tmp_path / "generic.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "qasper_style",
                "documents": [
                    {
                        "document_id": "generic",
                        "path": "generic.pdf",
                        "format_type": "pdf",
                    }
                ],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_ids": ["generic"],
                        "question": "What evidence string was quoted?",
                        "answers": ["Capex was 42."],
                        "evidence_sources": [
                            "{'evidence_text': 'Capex was 42.', "
                            "'evidence_page_num': 7}"
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    example = load_manifest(manifest_path).examples[0]

    assert example.evidence_pages == []
    assert example.evidence_sources == [
        "{'evidence_text': 'Capex was 42.', 'evidence_page_num': 7}"
    ]
    assert example.gold_evidence == []


def test_financebench_route_template_opts_into_finance_verification_domain():
    template_dir = Path("benchmark/manifests/templates")

    finance_routes = load_manifest(template_dir / "mara_financebench_text.json").routes
    text_routes = load_manifest(template_dir / "mara_text_only.json").routes

    assert {route["route_id"] for route in finance_routes} == {
        "text_rag",
        "hybrid_rag",
        "controller_auto",
        "crag_guarded",
    }
    assert all(route["verification_domain"] == "finance" for route in finance_routes)
    assert not any("verification_domain" in route for route in text_routes)
    assert finance_routes[2]["allowed_routes"] == [
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    ]


def test_text_templates_do_not_enable_visual_backends():
    template_dir = Path("benchmark/manifests/templates")

    for template_name in ("mara_text_only.json", "mara_financebench_text.json"):
        routes = load_manifest(template_dir / template_name).routes
        assert routes
        for route in routes:
            assert "visual_retriever_backend" not in route
            assert "visual_generator_backend" not in route
            assert "visual_backend_type" not in route


def test_text_template_controller_routes_match_text_dataset_profiles():
    template_dir = Path("benchmark/manifests/templates")
    routes = load_manifest(template_dir / "mara_text_only.json").routes
    route_by_id = {route["route_id"]: route for route in routes}

    for dataset_name in ("financebench", "qasper", "ragtruth", "alce"):
        profile = profile_for_manifest(dataset_name, examples=[])
        assert route_by_id["controller_auto"]["allowed_routes"] == list(
            profile.allowed_routes
        )
        assert route_by_id["crag_guarded"]["allowed_routes"] == list(
            profile.allowed_routes
        )


def test_local_qwen3_route_templates_cap_context_for_4k_server():
    template_dir = Path("benchmark/manifests/templates")
    template_names = (
        "mara_text_only.json",
        "mara_financebench_text.json",
        "mara_all_routes.local.json",
        "mara_multimodal.json",
    )

    for template_name in template_names:
        routes = load_manifest(template_dir / template_name).routes
        for route in routes:
            model_fields = (
                str(route.get("generator_backend") or ""),
                str(route.get("planner_model") or ""),
            )
            if "Qwen/Qwen3-8B" not in model_fields:
                continue
            assert route["max_context_length"] == 2000


def test_local_controller_templates_use_heuristic_planner_backend():
    template_dir = Path("benchmark/manifests/templates")
    template_names = (
        "mara_text_only.json",
        "mara_financebench_text.json",
        "mara_all_routes.local.json",
        "mara_multimodal.json",
    )

    for template_name in template_names:
        routes = load_manifest(template_dir / template_name).routes
        route_by_id = {route["route_id"]: route for route in routes}
        for route_id in ("controller_auto", "crag_guarded"):
            if route_id not in route_by_id:
                continue
            assert route_by_id[route_id]["planner_backend"] == "heuristic_local"


def test_multimodal_template_keeps_visual_routes_explicit():
    template_dir = Path("benchmark/manifests/templates")

    routes = load_manifest(template_dir / "mara_multimodal.json").routes
    route_by_id = {route["route_id"]: route for route in routes}

    assert route_by_id["page_image_rag_vlm"]["route_policy"] == "visual"
    assert route_by_id["controller_auto"]["allowed_routes"] == [
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    ]


def test_multimodal_template_limits_visual_backend_fields_to_visual_capable_routes():
    template_dir = Path("benchmark/manifests/templates")
    routes = load_manifest(template_dir / "mara_multimodal.json").routes
    visual_keys = {
        "visual_retriever_backend",
        "visual_generator_backend",
        "visual_backend_type",
    }
    visual_capable_policies = {"visual", "hybrid", "auto"}

    for route in routes:
        present_keys = visual_keys & set(route)
        route_policy = str(route.get("route_policy") or "")
        if route_policy in visual_capable_policies:
            continue
        assert present_keys == set()
