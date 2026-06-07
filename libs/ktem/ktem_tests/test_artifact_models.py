from ktem.docqa.artifact_models import (
    ARTIFACT_STATUS_READY,
    SUPPORTED_ARTIFACT_TYPES,
    build_artifact_record,
    normalize_artifact,
)


def test_supported_artifact_types_cover_studio_target_catalog():
    assert SUPPORTED_ARTIFACT_TYPES == (
        "study_guide",
        "quiz",
        "flashcards",
        "mindmap",
        "slide_outline",
        "briefing_doc",
        "faq",
        "timeline",
        "custom_report",
        "data_table",
        "infographic",
        "slide_deck",
        "audio_overview",
        "video_overview",
    )


def test_normalize_artifact_preserves_legacy_shape_with_full_metadata():
    artifact = normalize_artifact(
        {
            "artifact_id": "artifact-1",
            "type": "quiz",
            "payload": {"multiple_choice": []},
            "created_at": "2026-06-07T09:00:00+00:00",
        }
    )

    assert artifact == {
        "artifact_id": "artifact-1",
        "type": "quiz",
        "title": "Quiz",
        "status": ARTIFACT_STATUS_READY,
        "prompt": "",
        "source_scope": {"mode": "document", "source_ids": []},
        "payload": {"multiple_choice": []},
        "citations": [],
        "exports": [],
        "generation": {"adapter": "legacy", "parameters": {}},
        "created_at": "2026-06-07T09:00:00+00:00",
        "updated_at": "2026-06-07T09:00:00+00:00",
    }


def test_build_artifact_record_creates_source_grounded_metadata():
    artifact = build_artifact_record(
        artifact_type="data_table",
        payload={"columns": ["Metric"], "rows": [["Revenue"]]},
        artifact_id="artifact-2",
        title="Revenue table",
        status=ARTIFACT_STATUS_READY,
        prompt="Build a revenue table.",
        source_scope={"mode": "multi_document", "source_ids": ["file-1", "file-2"]},
        citations=[{"citation_id": "c1", "source_id": "file-1", "page_label": "3"}],
        generation={"adapter": "schema_builder", "parameters": {"count": 3}},
        timestamp="2026-06-07T09:05:00+00:00",
    )

    assert artifact["type"] == "data_table"
    assert artifact["title"] == "Revenue table"
    assert artifact["source_scope"] == {
        "mode": "multi_document",
        "source_ids": ["file-1", "file-2"],
    }
    assert artifact["citations"] == [
        {"citation_id": "c1", "source_id": "file-1", "page_label": "3"}
    ]
    assert artifact["generation"] == {
        "adapter": "schema_builder",
        "parameters": {"count": 3},
    }
    assert artifact["created_at"] == "2026-06-07T09:05:00+00:00"
    assert artifact["updated_at"] == "2026-06-07T09:05:00+00:00"
