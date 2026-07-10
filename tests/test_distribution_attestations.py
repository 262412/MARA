from __future__ import annotations

import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest


def _write_distribution_artifact(
    path: Path,
    distribution: str,
    *,
    requires: tuple[str, ...] = ("demo-dependency>=2",),
) -> None:
    metadata = "\n".join(
        [
            "Metadata-Version: 2.3",
            f"Name: {distribution}",
            "Version: 1.0.0",
            *[f"Requires-Dist: {requirement}" for requirement in requires],
            "",
        ]
    ).encode()
    normalized = distribution.replace("-", "_")
    if path.suffix == ".whl":
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{normalized}-1.0.0.dist-info/METADATA", metadata)
        return
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo(f"{normalized}-1.0.0/PKG-INFO")
        info.size = len(metadata)
        archive.addfile(info, io.BytesIO(metadata))


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
            _write_distribution_artifact(artifact, distribution)
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
        spdx = json.loads((output_dir / entry["spdx"]).read_text(encoding="utf-8"))
        provenance = json.loads(
            (output_dir / entry["provenance"]).read_text(encoding="utf-8")
        )

        assert sbom["bomFormat"] == "CycloneDX"
        assert sbom["specVersion"] == "1.6"
        assert sbom["metadata"]["component"]["hashes"] == [
            {"alg": "SHA-256", "content": digest}
        ]
        dependency = next(
            component
            for component in sbom["components"]
            if component["name"] == "demo-dependency"
        )
        assert dependency["bom-ref"] in sbom["dependencies"][0]["dependsOn"]
        assert spdx["spdxVersion"] == "SPDX-2.3"
        assert spdx["packages"][0]["checksums"] == [
            {"algorithm": "SHA256", "checksumValue": digest}
        ]
        assert any(package["name"] == "demo-dependency" for package in spdx["packages"])
        assert any(
            relationship["relationshipType"] == "DEPENDS_ON"
            for relationship in spdx["relationships"]
        )
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
    _write_distribution_artifact(package_dir / "ktem-1.0.0-py3-none-any.whl", "ktem")
    _write_distribution_artifact(package_dir / "ktem-1.0.0.tar.gz", "ktem")

    with pytest.raises(RuntimeError, match="missing required distributions"):
        generate_attestations(
            dist_root,
            tmp_path / "attestations",
            commit_sha="a" * 40,
            builder_id="https://github.com/example/mara/actions/runs/1",
        )


def test_distribution_attestations_require_one_wheel_and_one_sdist(tmp_path):
    from scripts.generate_distribution_attestations import generate_attestations

    dist_root = tmp_path / "dist"
    filenames = {
        "ktem": ("ktem-1.0.0-py3-none-any.whl", "ktem-1.0.0-py2-none-any.whl"),
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
    for distribution, package_filenames in filenames.items():
        package_dir = dist_root / distribution
        package_dir.mkdir(parents=True)
        for filename in package_filenames:
            _write_distribution_artifact(package_dir / filename, distribution)

    with pytest.raises(RuntimeError, match="one wheel and one sdist"):
        generate_attestations(
            dist_root,
            tmp_path / "attestations",
            commit_sha="a" * 40,
            builder_id="https://github.com/example/mara/actions/runs/1",
        )


def test_distribution_attestation_verification_rejects_tampered_artifact(tmp_path):
    from scripts.generate_distribution_attestations import (
        generate_attestations,
        verify_attestations,
    )

    dist_root = tmp_path / "dist"
    filenames = {
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
    for distribution, package_filenames in filenames.items():
        package_dir = dist_root / distribution
        package_dir.mkdir(parents=True)
        for filename in package_filenames:
            _write_distribution_artifact(package_dir / filename, distribution)

    evidence = tmp_path / "evidence"
    generate_attestations(
        dist_root,
        evidence,
        commit_sha="a" * 40,
        builder_id="https://github.com/example/mara/actions/runs/1",
    )
    verify_attestations(dist_root, evidence)

    (dist_root / "mara-app" / filenames["mara-app"][0]).write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="digest mismatch"):
        verify_attestations(dist_root, evidence)
