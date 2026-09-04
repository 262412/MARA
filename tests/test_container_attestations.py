from __future__ import annotations

import json

import pytest


def test_container_provenance_subject_matches_buildkit_digest(tmp_path):
    from scripts.generate_container_attestation import generate_container_evidence

    digest = "a" * 64
    metadata = {
        "containerimage.digest": f"sha256:{digest}",
        "buildx.build.provenance": {
            "buildType": "https://mobyproject.org/buildkit@v1",
            "materials": [],
        },
    }

    statement_path, metadata_path = generate_container_evidence(
        metadata,
        target="lite",
        output_dir=tmp_path,
    )

    statement = json.loads(statement_path.read_text(encoding="utf-8"))
    retained_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert statement["_type"] == "https://in-toto.io/Statement/v1"
    assert statement["subject"] == [
        {"name": "mara-quality:lite", "digest": {"sha256": digest}}
    ]
    assert statement["predicate"] == metadata["buildx.build.provenance"]
    assert retained_metadata == metadata


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"containerimage.digest": "sha256:short", "buildx.build.provenance": {}},
        {"containerimage.digest": "sha256:" + "a" * 64},
    ],
)
def test_container_provenance_fails_closed_on_incomplete_metadata(tmp_path, metadata):
    from scripts.generate_container_attestation import generate_container_evidence

    with pytest.raises(ValueError):
        generate_container_evidence(metadata, target="full", output_dir=tmp_path)
