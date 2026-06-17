import json

from benchmark.dataset_profiles import (
    DatasetCapabilities,
    profile_for_dataset,
    profile_for_manifest,
)
from benchmark.manifest import load_manifest


def test_financebench_profile_is_page_grounded_not_special_controller_logic():
    profile = profile_for_manifest("financebench_plan5_text_main", examples=[])

    assert profile.dataset_family == "financebench"
    assert profile.capabilities == DatasetCapabilities(
        answer_correctness=True,
        page_evidence=True,
        span_evidence=True,
        citation_quality=True,
        hallucination_labels=False,
        multi_document=False,
        multimodal=False,
        source_level_citations=False,
        supports_abstention=False,
    )
    assert profile.allowed_text_routes == ("doc_text", "hybrid", "graph_global")


def test_qasper_profile_supports_span_and_multidoc_text_evidence():
    profile = profile_for_manifest("qasper_plan5_text_main", examples=[])

    assert profile.dataset_family == "qasper"
    assert profile.capabilities.span_evidence is True
    assert profile.capabilities.multi_document is True
    assert profile.capabilities.hallucination_labels is False
    assert profile.capabilities.source_level_citations is True


def test_ragtruth_profile_supports_hallucination_labels():
    profile = profile_for_manifest("ragtruth_plan5_guardrail", examples=[])

    assert profile.dataset_family == "ragtruth"
    assert profile.capabilities.hallucination_labels is True
    assert profile.capabilities.citation_quality is False
    assert profile.capabilities.supports_abstention is True


def test_alce_profile_supports_citation_quality():
    profile = profile_for_manifest("alce_plan5_citation", examples=[])

    assert profile.dataset_family == "alce"
    assert profile.capabilities.citation_quality is True
    assert profile.capabilities.page_evidence is False
    assert profile.capabilities.source_level_citations is True


def test_profiles_describe_capabilities_not_runtime_special_cases():
    finance = profile_for_dataset("financebench-main")
    qasper = profile_for_dataset("qasper-dev")
    ragtruth = profile_for_dataset("ragtruth")
    alce = profile_for_dataset("alce-asqa")

    assert finance.capabilities.page_evidence is True
    assert qasper.capabilities.span_evidence is True
    assert ragtruth.capabilities.hallucination_labels is True
    assert alce.capabilities.citation_quality is True
    assert finance.allowed_routes == (
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    )
    assert qasper.allowed_routes == finance.allowed_routes
    assert ragtruth.allowed_routes == finance.allowed_routes
    assert alce.allowed_routes == finance.allowed_routes


def test_load_manifest_attaches_derived_dataset_profile(tmp_path):
    (tmp_path / "paper.txt").write_text("paper text", encoding="utf-8")
    manifest_path = tmp_path / "qasper.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "qasper_plan5_text_main",
                "documents": [
                    {
                        "document_id": "paper",
                        "path": "paper.txt",
                        "format_type": "txt",
                    }
                ],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_ids": ["paper"],
                        "question": "What does the paper show?",
                        "answers": ["answer"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    bundle = load_manifest(manifest_path)

    assert bundle.metadata["dataset_profile"].dataset_family == "qasper"
    assert bundle.metadata["dataset_profile"].capabilities.span_evidence is True
    assert bundle.metadata["capabilities"]["span_evidence"] is True
    assert bundle.metadata["allowed_routes"] == [
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    ]
