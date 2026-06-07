from ktem.docqa._runtime_notebook import (
    NOTEBOOK_KEY,
    delete_artifact,
    list_artifacts,
    record_artifact_export,
    save_artifact,
)
from ktem.docqa.artifact_service import (
    append_artifact_record,
    build_artifact_note_fields,
    get_artifact_record,
    list_artifact_records,
    update_artifact_record,
)


def test_save_artifact_writes_full_studio_metadata():
    updated, artifact = save_artifact(
        {NOTEBOOK_KEY: {"selected_source_ids": ["file-1"], "notes": []}},
        artifact_type="briefing_doc",
        payload={"sections": []},
        artifact_id="artifact-1",
        title="Briefing",
        prompt="Create a briefing.",
        source_scope={"mode": "document", "source_ids": ["file-1"]},
        citations=[{"citation_id": "c1", "source_id": "file-1"}],
        generation={"adapter": "schema_builder", "parameters": {"language": "en"}},
        timestamp="2026-06-07T09:10:00+00:00",
    )

    assert artifact["status"] == "ready"
    assert artifact["title"] == "Briefing"
    assert artifact["prompt"] == "Create a briefing."
    assert artifact["source_scope"] == {"mode": "document", "source_ids": ["file-1"]}
    assert artifact["citations"] == [{"citation_id": "c1", "source_id": "file-1"}]
    assert artifact["exports"] == []
    assert artifact["generation"] == {
        "adapter": "schema_builder",
        "parameters": {"language": "en"},
    }
    assert updated[NOTEBOOK_KEY]["artifacts"] == [artifact]


def test_list_artifacts_normalizes_legacy_records_at_read_time():
    artifacts = list_artifacts(
        {
            NOTEBOOK_KEY: {
                "artifacts": [
                    {
                        "artifact_id": "legacy-1",
                        "type": "study_guide",
                        "payload": {"overview": "Legacy"},
                        "created_at": "2026-06-07T09:15:00+00:00",
                    }
                ]
            }
        }
    )

    assert artifacts[0]["artifact_id"] == "legacy-1"
    assert artifacts[0]["type"] == "study_guide"
    assert artifacts[0]["status"] == "ready"
    assert artifacts[0]["title"] == "Study Guide"
    assert artifacts[0]["updated_at"] == "2026-06-07T09:15:00+00:00"


def test_delete_artifact_removes_only_matching_record():
    data_source = {
        NOTEBOOK_KEY: {
            "artifacts": [
                {"artifact_id": "artifact-1", "type": "quiz", "payload": {}},
                {"artifact_id": "artifact-2", "type": "faq", "payload": {}},
            ]
        }
    }

    updated, deleted = delete_artifact(data_source, "artifact-1")

    assert deleted["artifact_id"] == "artifact-1"
    assert [item["artifact_id"] for item in list_artifacts(updated)] == ["artifact-2"]


def test_record_artifact_export_updates_metadata_without_payload_loss():
    data_source, artifact = save_artifact(
        {},
        artifact_type="data_table",
        payload={"columns": ["Metric"], "rows": [["Revenue"]]},
        artifact_id="artifact-1",
        timestamp="2026-06-07T09:20:00+00:00",
    )

    updated, exported = record_artifact_export(
        data_source,
        "artifact-1",
        export_format="csv",
        path="D:/tmp/artifact-1.csv",
        timestamp="2026-06-07T09:21:00+00:00",
    )

    assert exported["payload"] == artifact["payload"]
    assert exported["exports"] == [
        {
            "format": "csv",
            "path": "D:/tmp/artifact-1.csv",
            "created_at": "2026-06-07T09:21:00+00:00",
        }
    ]
    assert list_artifacts(updated)[0]["updated_at"] == "2026-06-07T09:21:00+00:00"


def test_artifact_service_lists_gets_appends_and_updates_records():
    artifacts, saved = append_artifact_record(
        [],
        {
            "artifact_id": "artifact-1",
            "type": "quiz",
            "payload": {"multiple_choice": []},
            "created_at": "2026-06-07T09:22:00+00:00",
        },
    )

    assert list_artifact_records(artifacts)[0]["status"] == "ready"
    assert get_artifact_record(artifacts, "artifact-1") == saved

    updated_artifacts, updated = update_artifact_record(
        artifacts,
        "artifact-1",
        {"status": "failed", "generation": {"error": "adapter unavailable"}},
    )

    assert updated["status"] == "failed"
    assert updated["generation"]["error"] == "adapter unavailable"
    assert get_artifact_record(updated_artifacts, "artifact-1") == updated


def test_build_artifact_note_fields_preserves_prompt_citations_and_exports():
    fields = build_artifact_note_fields(
        {
            "artifact_id": "artifact-1",
            "type": "briefing_doc",
            "title": "Launch briefing",
            "status": "ready",
            "prompt": "Create an executive briefing.",
            "source_scope": {"mode": "document", "source_ids": ["file-1"]},
            "payload": {"sections": [{"title": "Finding", "summary": "Grounded."}]},
            "citations": [
                {
                    "citation_id": "c1",
                    "source_name": "launch.pdf",
                    "page_label": "3",
                }
            ],
            "exports": [{"format": "md", "path": "launch.md"}],
        }
    )

    assert fields["title"] == "Launch briefing"
    assert fields["citation_refs"] == ["c1"]
    assert "Artifact ID: artifact-1" in fields["text"]
    assert "Create an executive briefing." in fields["text"]
    assert "launch.pdf p.3" in fields["text"]
    assert "launch.md" in fields["text"]
