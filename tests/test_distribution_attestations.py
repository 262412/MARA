from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


def test_distribution_attestations_cover_every_artifact(tmp_path):
    from scripts.generate_distribution_attestations import generate_attestations

    dist_root = tmp_path / "dist"
    artifacts = []
    names = {
        "ktem": ("ktem-1.0.0-py3-none-any.whl", "ktem-1.0.0.tar.gz"),
        "kotaemon": (
            "kotaemon-1.0.0-py3-none-any.whl",
            "kotaemon-1.0.0.tar.gz",
        ),
        "mara-research-cli": (
            "mara_research_cli-1.0.0-py3-none-any.whl",
            "mara_research_cli-1.0.0.tar.gz",
        ),
        "mara-app": ("mara_app-1.0.0-py3-none-any.whl", "mara_app-1.0.0.tar.gz"),
    }
    for distribution, filenames in names.items():
        package_dir = dist_root / distribution
        package_dir.mkdir(parents=True)
        for filename in filenames:
            artifact = package_dir / filename
            artifact.write_bytes(f"artifact:{distribution}:{filename}".encode())
            artifacts.append(artifact)

    output_dir = tmp_path / "attestations"
    result = generate_attestations(
        dist_root,
        output_dir,
        commit_sha="a" * 40,
        builder_id="https://github.com/example/mara/actions/runs/1",
    )

    assert len(result) == 8
    index = json.loads((output_dir / "index.json").read_text(encoding="utf-8"))
    assert len(index["artifacts"]) == 8
    for artifact in artifacts:
        relative = artifact.relative_to(dist_root).as_posix()
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        entry = next(item for item in index["artifacts"] if item["name"] == relative)
        sbom = json.loads((output_dir / entry["sbom"]).read_text(encoding="utf-8"))
        provenance = json.loads(
            (output_dir / entry["provenance"]).read_text(encoding="utf-8")
        )

        assert sbom["bomFormat"] == "CycloneDX"
        assert sbom["specVersion"] == "1.6"
        assert sbom["metadata"]["component"]["hashes"] == [
            {"alg": "SHA-256", "content": digest}
        ]
        assert provenance["_type"] == "https://in-toto.io/Statement/v1"
        assert provenance["subject"] == [
            {"name": relative, "digest": {"sha256": digest}}
        ]
        assert provenance["predicateType"] == "https://slsa.dev/provenance/v1"


def test_distribution_attestations_fail_closed_when_a_distribution_is_missing(
    tmp_path,
):
    from scripts.generate_distribution_attestations import generate_attestations

    dist_root = tmp_path / "dist"
    package_dir = dist_root / "ktem"
    package_dir.mkdir(parents=True)
    (package_dir / "ktem-1.0.0-py3-none-any.whl").write_bytes(b"wheel")
    (package_dir / "ktem-1.0.0.tar.gz").write_bytes(b"sdist")

    with pytest.raises(RuntimeError, match="missing required distributions"):
        generate_attestations(
            dist_root,
            tmp_path / "attestations",
            commit_sha="a" * 40,
            builder_id="https://github.com/example/mara/actions/runs/1",
        )
