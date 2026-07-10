from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
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


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Invalid attestation JSON {path}: {error}") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"Attestation JSON must be an object: {path}")
    return payload


def _resolve_child(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise RuntimeError(f"Attestation path escapes its root: {relative}") from error
    return candidate


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


def _spdx(name: str, version: str, relative: str, digest: str) -> dict:
    package_id = "SPDXRef-Package-" + re.sub(r"[^A-Za-z0-9.-]", "-", name)
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"MARA distribution {relative}",
        "documentNamespace": f"https://github.com/262412/MARA/sbom/{digest}",
        "creationInfo": {
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "creators": ["Tool: MARA-generate-distribution-attestations"],
        },
        "packages": [
            {
                "name": name,
                "SPDXID": package_id,
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "checksums": [{"algorithm": "SHA256", "checksumValue": digest}],
                "primaryPackagePurpose": "APPLICATION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:pypi/{name}@{version}",
                    }
                ],
            }
        ],
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": package_id,
            }
        ],
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
        raise RuntimeError("unexpected distributions: " + ", ".join(sorted(unexpected)))
    artifact_kinds = Counter(
        (name, "wheel" if artifact.suffix == ".whl" else "sdist")
        for artifact, (name, _version) in zip(artifacts, identities, strict=True)
    )
    invalid_kinds = {
        name: {
            "wheel": artifact_kinds[(name, "wheel")],
            "sdist": artifact_kinds[(name, "sdist")],
        }
        for name in REQUIRED_DISTRIBUTIONS
        if artifact_kinds[(name, "wheel")] != 1 or artifact_kinds[(name, "sdist")] != 1
    }
    if invalid_kinds:
        raise RuntimeError(
            "each distribution must have one wheel and one sdist: "
            + ", ".join(
                f"{name}={counts}" for name, counts in sorted(invalid_kinds.items())
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
        spdx_name = f"{slug}.spdx.json"
        provenance_name = f"{slug}.provenance.json"
        _write_json(output_dir / sbom_name, _sbom(name, version, relative, digest))
        _write_json(output_dir / spdx_name, _spdx(name, version, relative, digest))
        _write_json(
            output_dir / provenance_name,
            _provenance(relative, digest, commit_sha, builder_id),
        )
        entries.append(
            {
                "name": relative,
                "sha256": digest,
                "sbom": sbom_name,
                "spdx": spdx_name,
                "provenance": provenance_name,
            }
        )
    _write_json(
        output_dir / "index.json",
        {"builder": builder_id, "commit": commit_sha, "artifacts": entries},
    )
    return entries


def verify_attestations(dist_root: Path, output_dir: Path) -> None:
    index = _read_json(output_dir / "index.json")
    entries = index.get("artifacts")
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("Attestation index has no artifacts")

    actual = {
        path.relative_to(dist_root).as_posix()
        for path in dist_root.glob("*/*")
        if path.is_file() and (path.suffix == ".whl" or path.name.endswith(".tar.gz"))
    }
    recorded = {entry.get("name") for entry in entries if isinstance(entry, dict)}
    if len(recorded) != len(entries) or recorded != actual:
        raise RuntimeError(
            f"Attestation artifact set mismatch: recorded={recorded}, actual={actual}"
        )

    for entry in entries:
        relative = entry["name"]
        artifact = _resolve_child(dist_root, relative)
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if entry.get("sha256") != digest:
            raise RuntimeError(f"Artifact digest mismatch: {relative}")

        sbom = _read_json(_resolve_child(output_dir, entry.get("sbom", "")))
        hashes = sbom.get("metadata", {}).get("component", {}).get("hashes", [])
        if {"alg": "SHA-256", "content": digest} not in hashes:
            raise RuntimeError(f"SBOM digest mismatch: {relative}")

        spdx = _read_json(_resolve_child(output_dir, entry.get("spdx", "")))
        packages = spdx.get("packages", [])
        spdx_checksums = packages[0].get("checksums", []) if packages else []
        if {"algorithm": "SHA256", "checksumValue": digest} not in spdx_checksums:
            raise RuntimeError(f"SPDX digest mismatch: {relative}")

        provenance = _read_json(_resolve_child(output_dir, entry.get("provenance", "")))
        expected_subject = [{"name": relative, "digest": {"sha256": digest}}]
        if provenance.get("subject") != expected_subject:
            raise RuntimeError(f"Provenance digest mismatch: {relative}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate CycloneDX and SLSA evidence for Python artifacts."
    )
    parser.add_argument("--dist-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify existing evidence instead of generating new evidence.",
    )
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
    dist_root = args.dist_root.resolve()
    output_dir = args.output_dir.resolve()
    if args.verify:
        verify_attestations(dist_root, output_dir)
    else:
        generate_attestations(
            dist_root,
            output_dir,
            commit_sha=args.commit,
            builder_id=args.builder_id,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
