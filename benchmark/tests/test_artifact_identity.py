import json

import pytest

from benchmark.artifact_identity import (
    AmbiguousArtifactError,
    canonical_suite_key,
    resolve_artifact_dir,
)

REQUIRED_ARTIFACTS = (
    "summary.json",
    "route_metrics.csv",
    "predictions.jsonl",
    "report.md",
)


def _artifact(tmp_path, name: str, suite_name: str):
    artifact_dir = tmp_path / name
    artifact_dir.mkdir()
    (artifact_dir / "summary.json").write_text(
        json.dumps({"suite_name": suite_name}),
        encoding="utf-8",
    )
    for filename in REQUIRED_ARTIFACTS[1:]:
        (artifact_dir / filename).write_text("", encoding="utf-8")
    return artifact_dir


def test_canonical_suite_key_normalizes_route_separators():
    assert canonical_suite_key("stat_alce_asqa_page_image_rag_vlm") == (
        "stat-alce-asqa-page-image-rag-vlm"
    )


def test_resolve_artifact_dir_matches_underscore_suite_to_hyphen_artifact(tmp_path):
    artifact_dir = _artifact(
        tmp_path,
        "20260723_165617_stat-alce-asqa-all-n50-shard00of4-9849607",
        "stat-alce-asqa-all-n50-shard00of4-9849607",
    )

    resolved = resolve_artifact_dir(
        tmp_path,
        suite_name="stat_alce_asqa_all_n50_shard00of4",
        job_id="9849607",
        required_artifacts=REQUIRED_ARTIFACTS,
    )

    assert resolved == artifact_dir


def test_resolve_artifact_dir_uses_job_id_to_select_superseding_artifact(tmp_path):
    _artifact(
        tmp_path,
        "20260720_120000_stat-ragtruth-all-n50-shard00of6-9849601",
        "stat-ragtruth-all-n50-shard00of6-9849601",
    )
    repaired = _artifact(
        tmp_path,
        "20260723_115032_stat-ragtruth-all-n50-shard00of6-9892047",
        "stat-ragtruth-all-n50-shard00of6-9892047",
    )

    resolved = resolve_artifact_dir(
        tmp_path,
        suite_name="stat_ragtruth_all_n50_shard00of6",
        job_id="9892047",
        required_artifacts=REQUIRED_ARTIFACTS,
    )

    assert resolved == repaired


def test_resolve_artifact_dir_rejects_ambiguous_matches_without_job_identity(tmp_path):
    first = _artifact(
        tmp_path,
        "20260720_120000_stat-ragtruth-all-n50-shard00of6-9849601",
        "stat-ragtruth-all-n50-shard00of6-9849601",
    )
    second = _artifact(
        tmp_path,
        "20260723_115032_stat-ragtruth-all-n50-shard00of6-9892047",
        "stat-ragtruth-all-n50-shard00of6-9892047",
    )

    with pytest.raises(AmbiguousArtifactError) as exc_info:
        resolve_artifact_dir(
            tmp_path,
            suite_name="stat_ragtruth_all_n50_shard00of6",
            required_artifacts=REQUIRED_ARTIFACTS,
        )

    message = str(exc_info.value)
    assert str(first) in message
    assert str(second) in message
