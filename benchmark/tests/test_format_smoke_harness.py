import json

from benchmark.cli import main
from benchmark.format_smoke_harness import (
    REQUIRED_FORMATS,
    build_format_smoke_fixtures,
    run_format_smoke_harness,
)
from benchmark.manifest import load_manifest
from benchmark.normalizers import normalize_format_robustness_manifest


def test_build_format_smoke_fixtures_covers_required_formats(tmp_path):
    source_dir = tmp_path / "source"
    manifest_path = tmp_path / "format-smoke.json"

    output_path = build_format_smoke_fixtures(source_dir, manifest_path)
    bundle = load_manifest(output_path)

    assert output_path == manifest_path
    assert bundle.dataset_name == "format_robustness"
    assert {document.format_type for document in bundle.documents.values()} == set(
        REQUIRED_FORMATS
    )
    assert {document.path.suffix.lower() for document in bundle.documents.values()} == {
        ".pdf",
        ".docx",
        ".pptx",
        ".xlsx",
        ".csv",
        ".md",
        ".txt",
    }
    assert all(document.path.exists() for document in bundle.documents.values())


def test_run_format_smoke_harness_reports_index_and_query_success(tmp_path):
    manifest_path = build_format_smoke_fixtures(
        tmp_path / "source",
        tmp_path / "format-smoke.json",
    )

    report = run_format_smoke_harness(manifest_path)

    assert report["schema_version"] == 1
    assert report["dataset_name"] == "format_robustness"
    assert report["required_formats"] == list(REQUIRED_FORMATS)
    assert report["overall_status"] == "pass"
    assert set(report["format_summary"]) == set(REQUIRED_FORMATS)
    for format_type, summary in report["format_summary"].items():
        assert summary == {
            "format_type": format_type,
            "documents": 1,
            "examples": 1,
            "indexed": 1,
            "query_passed": 1,
            "failures": {},
            "status": "pass",
        }
    assert all(item["status"] == "pass" for item in report["indexing"])
    assert all(item["status"] == "pass" for item in report["queries"])


def test_run_format_smoke_harness_classifies_answer_not_indexed(tmp_path):
    source_dir = tmp_path / "source"
    text_dir = source_dir / "text"
    text_dir.mkdir(parents=True)
    (text_dir / "1_sample.txt").write_text(
        "The document omits the gold phrase.",
        encoding="utf-8",
    )
    (text_dir / "1_metadata.json").write_text(
        json.dumps(
            {
                "file_name": "sample.txt",
                "questions": [
                    {
                        "question": "What phrase should be present?",
                        "answer": "missing smoke answer",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "format-smoke.json"
    normalize_format_robustness_manifest(source_dir, manifest_path)

    report = run_format_smoke_harness(manifest_path)

    assert report["overall_status"] == "fail"
    assert report["queries"][0]["status"] == "fail"
    assert report["queries"][0]["failure_type"] == "answer_not_indexed"
    assert report["format_summary"]["text"]["failures"] == {"answer_not_indexed": 1}


def test_format_smoke_cli_builds_fixtures_and_writes_report(tmp_path):
    source_dir = tmp_path / "source"
    manifest_path = tmp_path / "format-smoke.json"
    report_path = tmp_path / "format-smoke-report.json"

    build_exit_code = main(
        [
            "build-format-smoke-fixtures",
            "--source-dir",
            str(source_dir),
            "--manifest",
            str(manifest_path),
        ]
    )
    run_exit_code = main(
        [
            "run-format-smoke",
            "--manifest",
            str(manifest_path),
            "--output",
            str(report_path),
            "--strict",
        ]
    )

    assert build_exit_code == 0
    assert run_exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_status"] == "pass"
    assert set(report["format_summary"]) == set(REQUIRED_FORMATS)
