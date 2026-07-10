from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from collections import Counter
from pathlib import Path

from packaging.utils import parse_sdist_filename, parse_wheel_filename

REQUIRED_DISTRIBUTIONS = {
    "ktem",
    "kotaemon",
    "mara-research-cli",
    "mara-app",
}


def _artifact_identity(path: Path) -> tuple[str, str]:
    if path.suffix == ".whl":
        name, version, _build, _tags = parse_wheel_filename(path.name)
    elif path.name.endswith(".tar.gz"):
        name, version = parse_sdist_filename(path.name)
    else:
        raise ValueError(f"Unsupported distribution artifact: {path}")
    return str(name), str(version)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sbom(name: str, version: str, relative: str, digest: str) -> dict:
    serial = uuid.uuid5(uuid.NAMESPACE_URL, f"{relative}:{digest}")
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "bom-ref": f"pkg:pypi/{name}@{version}?download_url={relative}",
                "name": name,
                "version": version,
                "hashes": [{"alg": "SHA-256", "content": digest}],
                "properties": [
                    {"name": "mara:distribution-artifact", "value": relative}
                ],
            }
        },
        "components": [],
    }


def _provenance(relative: str, digest: str, commit_sha: str, builder_id: str) -> dict:
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": relative, "digest": {"sha256": digest}}],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://github.com/262412/MARA/python-distribution@v1",
                "externalParameters": {"artifact": relative},
                "internalParameters": {"commit": commit_sha},
                "resolvedDependencies": [
                    {
                        "uri": "git+https://github.com/262412/MARA",
                        "digest": {"gitCommit": commit_sha},
                    }
                ],
            },
            "runDetails": {
                "builder": {"id": builder_id},
                "metadata": {"invocationId": builder_id},
            },
        },
    }


def generate_attestations(
    dist_root: Path,
    output_dir: Path,
    *,
    commit_sha: str,
    builder_id: str,
) -> list[dict[str, str]]:
    artifacts = sorted(
        path
        for path in dist_root.glob("*/*")
        if path.is_file() and (path.suffix == ".whl" or path.name.endswith(".tar.gz"))
    )
    if not artifacts:
        raise RuntimeError(f"No Python distributions found in {dist_root}")

    identities = [_artifact_identity(artifact) for artifact in artifacts]
    names = {name for name, _version in identities}
    missing = REQUIRED_DISTRIBUTIONS - names
    unexpected = names - REQUIRED_DISTRIBUTIONS
    if missing:
        raise RuntimeError(
            "missing required distributions: " + ", ".join(sorted(missing))
        )
    if unexpected:
        raise RuntimeError(
            "unexpected distributions: " + ", ".join(sorted(unexpected))
        )
    counts = Counter(name for name, _version in identities)
    invalid_counts = {name: count for name, count in counts.items() if count != 2}
    if invalid_counts:
        raise RuntimeError(
            "each distribution must have exactly one wheel and one sdist: "
            + ", ".join(
                f"{name}={count}" for name, count in sorted(invalid_counts.items())
            )
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for artifact in artifacts:
        relative = artifact.relative_to(dist_root).as_posix()
        name, version = _artifact_identity(artifact)
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        slug = relative.replace("/", "__")
        sbom_name = f"{slug}.cdx.json"
        provenance_name = f"{slug}.intoto.json"
        _write_json(output_dir / sbom_name, _sbom(name, version, relative, digest))
        _write_json(
            output_dir / provenance_name,
            _provenance(relative, digest, commit_sha, builder_id),
        )
        entries.append(
            {
                "name": relative,
                "sha256": digest,
                "sbom": sbom_name,
                "provenance": provenance_name,
            }
        )
    _write_json(
        output_dir / "index.json",
        {"builder": builder_id, "commit": commit_sha, "artifacts": entries},
    )
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate CycloneDX and SLSA evidence for Python artifacts."
    )
    parser.add_argument("--dist-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--commit", default=os.environ.get("GITHUB_SHA", "local"))
    parser.add_argument(
        "--builder-id",
        default=(
            f"{os.environ.get('GITHUB_SERVER_URL', 'local')}"
            f"/{os.environ.get('GITHUB_REPOSITORY', 'MARA')}"
            f"/actions/runs/{os.environ.get('GITHUB_RUN_ID', 'local')}"
        ),
    )
    args = parser.parse_args()
    generate_attestations(
        args.dist_root.resolve(),
        args.output_dir.resolve(),
        commit_sha=args.commit,
        builder_id=args.builder_id,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
