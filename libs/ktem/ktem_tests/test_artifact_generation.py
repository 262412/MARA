from ktem.docqa.artifact_generation import (
    artifact_generation_request,
    build_artifact_payload,
)
from ktem.docqa.artifact_models import SUPPORTED_ARTIFACT_TYPES


def _evidence():
    return [
        {
            "evidence_id": "evidence-1",
            "file_id": "file-1",
            "file_name": "report.pdf",
            "page_label": "3",
            "excerpt": "Revenue increased after MARA added source-grounded retrieval.",
        }
    ]


def test_artifact_generation_supports_every_studio_type_with_citations():
    for artifact_type in SUPPORTED_ARTIFACT_TYPES:
        payload = build_artifact_payload(artifact_type, _evidence())

        assert payload is not None
        assert payload["type"] == artifact_type
        assert payload["status"] == "ready"
        assert payload["source"] == "mara_reasoning"
        assert payload["cited_evidence"][0]["evidence_id"] == "evidence-1"


def test_artifact_generation_builds_data_table_with_row_citation_refs():
    payload = build_artifact_payload("data_table", _evidence())

    assert payload is not None
    assert payload["columns"] == ["Source", "Page", "Evidence"]
    assert payload["rows"] == [
        [
            "report.pdf",
            "3",
            "Revenue increased after MARA added source-grounded retrieval.",
        ]
    ]
    assert payload["row_citations"] == [
        {"row": 0, "citation_refs": ["evidence-1"], "source_ids": ["file-1"]}
    ]
    assert payload["cell_citations"] == [
        {"row": 0, "column": "Source", "citation_refs": ["evidence-1"]},
        {"row": 0, "column": "Page", "citation_refs": ["evidence-1"]},
        {"row": 0, "column": "Evidence", "citation_refs": ["evidence-1"]},
    ]


def test_artifact_generation_builds_schema_first_study_guide_payload():
    payload = build_artifact_payload("study_guide", _evidence())

    assert payload is not None
    assert payload["schema_version"] == "mara_artifact.v1"
    assert payload["learning_objectives"]
    assert payload["practice_questions"]
    assert payload["citations"] == [
        {
            "citation_id": "evidence-1",
            "source_id": "file-1",
            "source_name": "report.pdf",
            "page_label": "3",
        }
    ]


def test_artifact_generation_request_contains_schema_and_grounding_rules():
    request = artifact_generation_request("quiz", _evidence())

    assert request["artifact_type"] == "quiz"
    assert "multiple_choice" in request["json_schema"]["required"]
    assert "Use only the supplied evidence" in request["prompt"]
    assert "Markdown tables" in request["prompt"]
    assert "LaTeX" in request["prompt"]
    assert "citation_id" in request["prompt"]


def test_artifact_generation_uses_schema_adapter(monkeypatch):
    calls = []

    def adapter(request):
        calls.append(request["artifact_type"])
        return {
            "overview": "Adapter overview.",
            "learning_objectives": ["Understand cited evidence."],
            "key_concepts": ["Evidence"],
            "glossary": [],
            "practice_questions": [],
        }

    monkeypatch.setattr(
        "ktem.docqa.artifact_generation.configured_artifact_generation_adapter",
        lambda: adapter,
    )

    payload = build_artifact_payload("study_guide", _evidence())

    assert payload is not None
    assert payload["overview"] == "Adapter overview."
    assert payload["schema_version"] == "mara_artifact.v1"
    assert payload["source"] == "schema_adapter"
    assert calls == ["study_guide"]


def test_artifact_generation_rejects_adapter_payload_missing_required_key(
    monkeypatch,
):
    monkeypatch.setattr(
        "ktem.docqa.artifact_generation.configured_artifact_generation_adapter",
        lambda: lambda _request: {"overview": "Incomplete."},
    )

    try:
        build_artifact_payload("study_guide", _evidence())
    except ValueError as exc:
        assert "learning_objectives" in str(exc)
    else:
        raise AssertionError("Incomplete schema adapter payload should fail")


def test_artifact_generation_builds_media_overviews_as_script_only():
    audio = build_artifact_payload("audio_overview", _evidence())
    video = build_artifact_payload("video_overview", _evidence())

    assert audio is not None
    assert video is not None
    assert audio["media_status"] == "script_only"
    assert audio["script"][0]["text"].startswith("Revenue increased")
    assert video["media_status"] == "script_only"
    assert video["scenes"][0]["narration"].startswith("Revenue increased")
