from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tarfile
import uuid
import zipfile
from collections import Counter
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path

import tomli
from packaging.requirements import Requirement
from packaging.utils import (
    canonicalize_name,
    parse_sdist_filename,
    parse_wheel_filename,
)
from spdx_tools.spdx.parser.parse_anything import parse_file
from spdx_tools.spdx.validation.document_validator import validate_full_spdx_document

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DISTRIBUTIONS = {
    "ktem",
    "kotaemon",
    "mara-research-cli",
    "mara-app",
}
WORKSPACE_DISTRIBUTIONS = REQUIRED_DISTRIBUTIONS


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


def _validate_spdx_file(path: Path) -> None:
    messages = validate_full_spdx_document(parse_file(str(path)), "SPDX-2.3")
    if messages:
        detail = "; ".join(str(message) for message in messages)
        raise RuntimeError(f"Invalid SPDX 2.3 document {path}: {detail}")


def _resolve_child(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise RuntimeError(f"Attestation path escapes its root: {relative}") from error
    return candidate


def _artifact_requirements(path: Path) -> list[Requirement]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            names = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            ]
            if len(names) != 1:
                raise RuntimeError(f"Wheel must contain one METADATA file: {path}")
            metadata = archive.read(names[0])
    else:
        with tarfile.open(path, "r:gz") as archive:
            members = [
                member
                for member in archive.getmembers()
                if member.isfile()
                and len(Path(member.name).parts) == 2
                and Path(member.name).name == "PKG-INFO"
            ]
            if len(members) != 1:
                raise RuntimeError(f"Sdist must contain one PKG-INFO file: {path}")
            extracted = archive.extractfile(members[0])
            if extracted is None:
                raise RuntimeError(f"Cannot read sdist PKG-INFO: {path}")
            metadata = extracted.read()
    message = BytesParser(policy=policy.default).parsebytes(metadata)
    return [Requirement(value) for value in message.get_all("Requires-Dist", [])]


def _locked_versions(lock_path: Path) -> dict[str, set[str]]:
    lock = tomli.loads(lock_path.read_text(encoding="utf-8"))
    versions: dict[str, set[str]] = {}
    for package in lock["package"]:
        if "version" in package:
            versions.setdefault(canonicalize_name(package["name"]), set()).add(
                package["version"]
            )
    return versions


def _dependency_components(
    requirements: list[Requirement],
    locked: dict[str, set[str]],
    *,
    workspace_versions: dict[str, str] | None = None,
) -> list[dict]:
    workspace_versions = workspace_versions or {}
    components: dict[tuple[str, str], dict] = {}
    for requirement in requirements:
        name = canonicalize_name(requirement.name)
        locked_versions = locked.get(name, set())
        versions = sorted(
            version
            for version in locked_versions
            if requirement.specifier.contains(version, prereleases=True)
        )
        workspace = name in WORKSPACE_DISTRIBUTIONS
        if workspace:
            workspace_version = workspace_versions.get(name)
            if not workspace_version:
                raise RuntimeError(
                    f"Workspace dependency {requirement} has no artifact version"
                )
            if not requirement.specifier.contains(workspace_version, prereleases=True):
                raise RuntimeError(
                    f"Workspace artifact {name}=={workspace_version} does not satisfy "
                    f"{requirement}"
                )
            versions = [workspace_version]
        elif not locked_versions:
            raise RuntimeError(
                f"Declared dependency {requirement} is not present in uv.lock"
            )
        elif not versions:
            raise RuntimeError(
                f"Declared dependency {requirement}: no locked version satisfies "
                "the constraint"
            )
        for version in versions:
            requirement_text = str(requirement)
            key = (name, version)
            purl = f"pkg:pypi/{name}@{version}"
            component = components.setdefault(
                key,
                {
                    "name": name,
                    "version": version,
                    "requirements": set(),
                    "markers": set(),
                    "extras": set(),
                    "workspace": workspace,
                    "purl": purl,
                    "bom-ref": purl,
                },
            )
            component["requirements"].add(requirement_text)
            if requirement.marker:
                component["markers"].add(str(requirement.marker))
            if requirement.extras:
                component["extras"].add(",".join(sorted(requirement.extras)))
    for component in components.values():
        for field in ("requirements", "markers", "extras"):
            component[field] = sorted(component[field])
    return [components[key] for key in sorted(components)]


def _component_properties(item: dict) -> list[dict[str, str]]:
    properties = [
        *(
            {"name": "mara:requires-dist", "value": requirement}
            for requirement in item["requirements"]
        ),
        {"name": "mara:scope", "value": "declared-direct"},
    ]
    for key in ("markers", "extras"):
        property_name = key.removesuffix("s")
        properties.extend(
            {"name": f"mara:{property_name}", "value": value} for value in item[key]
        )
    if item["workspace"]:
        properties.append({"name": "mara:workspace", "value": "true"})
    return properties


def _cyclonedx_component(item: dict) -> dict:
    return {
        "type": "library",
        "bom-ref": item["bom-ref"],
        "name": item["name"],
        "version": item["version"],
        "purl": item["purl"],
        "properties": _component_properties(item),
    }


def _sbom(
    name: str,
    version: str,
    relative: str,
    digest: str,
    dependencies: list[dict],
) -> dict:
    serial = uuid.uuid5(uuid.NAMESPACE_URL, f"{relative}:{digest}")
    root_ref = f"pkg:pypi/{name}@{version}?download_url={relative}"
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "bom-ref": root_ref,
                "name": name,
                "version": version,
                "hashes": [{"alg": "SHA-256", "content": digest}],
                "properties": [
                    {"name": "mara:distribution-artifact", "value": relative},
                    {
                        "name": "mara:sbom-scope",
                        "value": "declared-direct-locked-versions",
                    },
                ],
            }
        },
        "components": [_cyclonedx_component(item) for item in dependencies],
        "dependencies": [
            {"ref": root_ref, "dependsOn": [item["bom-ref"] for item in dependencies]},
            *[{"ref": item["bom-ref"], "dependsOn": []} for item in dependencies],
        ],
    }


def _spdx(
    name: str,
    version: str,
    relative: str,
    digest: str,
    dependencies: list[dict],
) -> dict:
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
                "licenseConcluded": "Apache-2.0",
                "licenseDeclared": "Apache-2.0",
                "copyrightText": "NOASSERTION",
                "checksums": [{"algorithm": "SHA256", "checksumValue": digest}],
                "primaryPackagePurpose": "APPLICATION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:pypi/{name}@{version}",
                    }
                ],
            },
            *[
                {
                    "name": item["name"],
                    "SPDXID": "SPDXRef-Dependency-"
                    + hashlib.sha256(item["bom-ref"].encode()).hexdigest()[:16],
                    **({"versionInfo": item["version"]} if item["version"] else {}),
                    "downloadLocation": "NOASSERTION",
                    "filesAnalyzed": False,
                    "licenseConcluded": "NOASSERTION",
                    "licenseDeclared": "NOASSERTION",
                    "copyrightText": "NOASSERTION",
                    "comment": "Declared direct dependencies: "
                    + "; ".join(item["requirements"]),
                    "externalRefs": [
                        {
                            "referenceCategory": "PACKAGE-MANAGER",
                            "referenceType": "purl",
                            "referenceLocator": item["purl"],
                        }
                    ],
                }
                for item in dependencies
            ],
        ],
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": package_id,
            },
            *[
                {
                    "spdxElementId": package_id,
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": "SPDXRef-Dependency-"
                    + hashlib.sha256(item["bom-ref"].encode()).hexdigest()[:16],
                }
                for item in dependencies
            ],
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


def _validate_distribution_set(
    artifacts: list[Path], dist_root: Path
) -> dict[str, str]:
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
    invalid = {
        name: {
            "wheel": artifact_kinds[(name, "wheel")],
            "sdist": artifact_kinds[(name, "sdist")],
        }
        for name in REQUIRED_DISTRIBUTIONS
        if artifact_kinds[(name, "wheel")] != 1 or artifact_kinds[(name, "sdist")] != 1
    }
    if invalid:
        detail = ", ".join(
            f"{name}={counts}" for name, counts in sorted(invalid.items())
        )
        raise RuntimeError(
            f"each distribution must have one wheel and one sdist: {detail}"
        )
    versions = {
        name: {
            version for identity_name, version in identities if identity_name == name
        }
        for name in REQUIRED_DISTRIBUTIONS
    }
    mismatched = {name: values for name, values in versions.items() if len(values) != 1}
    if mismatched:
        raise RuntimeError(
            "distributions require matching wheel and sdist versions: "
            + ", ".join(
                f"{name}={sorted(values)}"
                for name, values in sorted(mismatched.items())
            )
        )
    return {name: next(iter(values)) for name, values in versions.items()}


def generate_attestations(
    dist_root: Path,
    output_dir: Path,
    *,
    commit_sha: str,
    builder_id: str,
    lock_path: Path = REPO_ROOT / "uv.lock",
) -> list[dict[str, str]]:
    artifacts = sorted(
        path
        for path in dist_root.glob("*/*")
        if path.is_file() and (path.suffix == ".whl" or path.name.endswith(".tar.gz"))
    )
    workspace_versions = _validate_distribution_set(artifacts, dist_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    locked = _locked_versions(lock_path)
    entries = []
    for artifact in artifacts:
        relative = artifact.relative_to(dist_root).as_posix()
        name, version = _artifact_identity(artifact)
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        dependencies = _dependency_components(
            _artifact_requirements(artifact),
            locked,
            workspace_versions=workspace_versions,
        )
        slug = relative.replace("/", "__")
        sbom_name = f"{slug}.cdx.json"
        spdx_name = f"{slug}.spdx.json"
        provenance_name = f"{slug}.provenance.json"
        _write_json(
            output_dir / sbom_name,
            _sbom(name, version, relative, digest, dependencies),
        )
        _write_json(
            output_dir / spdx_name,
            _spdx(name, version, relative, digest, dependencies),
        )
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


def verify_attestations(
    dist_root: Path,
    output_dir: Path,
    lock_path: Path = REPO_ROOT / "uv.lock",
) -> None:
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

    artifacts = [_resolve_child(dist_root, relative) for relative in sorted(actual)]
    workspace_versions = _validate_distribution_set(artifacts, dist_root)
    locked = _locked_versions(lock_path)
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
        expected_dependencies = _dependency_components(
            _artifact_requirements(artifact),
            locked,
            workspace_versions=workspace_versions,
        )
        expected_components = [
            _cyclonedx_component(item) for item in expected_dependencies
        ]
        if sbom.get("components") != expected_components:
            raise RuntimeError(f"SBOM dependencies mismatch: {relative}")

        spdx_path = _resolve_child(output_dir, entry.get("spdx", ""))
        spdx = _read_json(spdx_path)
        _validate_spdx_file(spdx_path)
        packages = spdx.get("packages", [])
        spdx_checksums = packages[0].get("checksums", []) if packages else []
        if {"algorithm": "SHA256", "checksumValue": digest} not in spdx_checksums:
            raise RuntimeError(f"SPDX digest mismatch: {relative}")
        expected_purls = {item["purl"] for item in expected_dependencies}
        spdx_refs = {
            reference.get("referenceLocator")
            for package in packages[1:]
            for reference in package.get("externalRefs", [])
            if reference.get("referenceType") == "purl"
        }
        if spdx_refs != expected_purls:
            raise RuntimeError(f"SPDX dependencies mismatch: {relative}")

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
    parser.add_argument("--lock", type=Path, default=REPO_ROOT / "uv.lock")
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
        verify_attestations(dist_root, output_dir, args.lock.resolve())
    else:
        generate_attestations(
            dist_root,
            output_dir,
            commit_sha=args.commit,
            builder_id=args.builder_id,
            lock_path=args.lock.resolve(),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
