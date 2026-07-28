from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from pathlib import Path

import tomli
import yaml
from packaging.requirements import Requirement

supply_chain_pins = importlib.import_module(
    "scripts.supply_chain_pins" if __package__ else "supply_chain_pins"
)


@dataclass(frozen=True)
class ContractIssue:
    path: Path
    rule: str
    detail: str
    needle: str | None = None


def _load_yaml(root: Path, path: Path) -> dict:
    payload = yaml.safe_load((root / path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload


def _steps(workflow: dict):
    for job in workflow.get("jobs", {}).values():
        yield from job.get("steps", [])


def check_precommit(root: Path) -> list[ContractIssue]:
    path = Path(".pre-commit-config.yaml")
    config = _load_yaml(root, path)
    issues: list[ContractIssue] = []
    seen = set()
    for repository in config.get("repos", []):
        url = repository.get("repo")
        if url != "local":
            seen.add(url)
            expected = supply_chain_pins.APPROVED_PRECOMMIT_REVISIONS.get(url)
            if repository.get("rev") != expected:
                issues.append(
                    ContractIssue(
                        path,
                        "precommit-pin",
                        f"{url} must use independently verified revision {expected}",
                        str(url),
                    )
                )
        for hook in repository.get("hooks", []):
            for dependency in hook.get("additional_dependencies", []):
                requirement = Requirement(dependency)
                specifiers = list(requirement.specifier)
                if (
                    requirement.url
                    or len(specifiers) != 1
                    or specifiers[0].operator != "=="
                ):
                    issues.append(
                        ContractIssue(
                            path,
                            "precommit-dependency-pin",
                            f"{dependency} must use one exact == version",
                            str(dependency),
                        )
                    )
    missing = set(supply_chain_pins.APPROVED_PRECOMMIT_REVISIONS) - seen
    for url in sorted(missing):
        issues.append(ContractIssue(path, "precommit-repository", f"missing {url}"))
    return issues


def check_build_requirements(root: Path) -> list[ContractIssue]:
    projects = (
        Path("pyproject.toml"),
        Path("libs/kotaemon/pyproject.toml"),
        Path("libs/ktem/pyproject.toml"),
        Path("libs/slide_cli/pyproject.toml"),
    )
    expected = [
        "setuptools==80.9.0",
        "wheel==0.45.1",
        "setuptools-git-versioning==2.1.0",
    ]
    issues: list[ContractIssue] = []
    for path in projects:
        project = tomli.loads((root / path).read_text(encoding="utf-8"))
        if project.get("build-system", {}).get("requires") != expected:
            issues.append(
                ContractIssue(
                    path,
                    "pep517-build-pin",
                    "PEP 517 build requirements must match the verified versions",
                )
            )
    expected_constraints = set(expected)
    for path in (Path("pyproject.toml"), Path("docker/pyproject.toml")):
        project = tomli.loads((root / path).read_text(encoding="utf-8"))
        actual = set(
            project.get("tool", {})
            .get("uv", {})
            .get("build-constraint-dependencies", [])
        )
        if actual != expected_constraints:
            issues.append(
                ContractIssue(
                    path, "build-constraint-pin", "build constraints mismatch"
                )
            )
    return issues


def check_workflow_tool_inputs(root: Path) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    for absolute in sorted((root / ".github/workflows").glob("*.y*ml")):
        path = absolute.relative_to(root)
        workflow = _load_yaml(root, path)
        for step in _steps(workflow):
            action = str(step.get("uses", ""))
            inputs = step.get("with", {})
            if action == supply_chain_pins.SETUP_UV_ACTION and (
                inputs.get("version") != supply_chain_pins.SETUP_UV_VERSION
                or inputs.get("checksum") != supply_chain_pins.SETUP_UV_CHECKSUM
            ):
                issues.append(
                    ContractIssue(path, "setup-uv-pin", "uv version/checksum mismatch")
                )
            if action.startswith("docker/setup-buildx-action@") and inputs != {
                "version": supply_chain_pins.BUILDX_VERSION,
                "driver-opts": f"image={supply_chain_pins.BUILDKIT_IMAGE}",
            }:
                issues.append(
                    ContractIssue(
                        path,
                        "buildx-pin",
                        "Buildx version and BuildKit image digest must match the allowlist",
                    )
                )
    return issues


def check_secret_scan(root: Path) -> list[ContractIssue]:
    path = Path(".github/workflows/secret-scan.yaml")
    source = (root / path).read_text(encoding="utf-8")
    issues: list[ContractIssue] = []
    required = (
        (supply_chain_pins.GITLEAKS_IMAGE, 2),
        ("git /repo", 1),
        ("dir /repo", 1),
        ("--config /repo/.gitleaks.toml", 2),
        ("--verbose", 2),
        ("--redact", 2),
        ("persist-credentials: false", 2),
        ("if: ${{ always() }}", 1),
    )
    for token, minimum in required:
        if source.count(token) < minimum:
            issues.append(
                ContractIssue(path, "secret-scan-contract", f"missing {token}")
            )
    if "gitleaks/gitleaks-action@" in source:
        issues.append(
            ContractIssue(
                path, "gitleaks-action", "use the digest-pinned scanner image"
            )
        )
    ignore_path = root / ".gitleaksignore"
    fingerprints = tuple(
        line.strip()
        for line in ignore_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if fingerprints != supply_chain_pins.GITLEAKS_IGNORE_FINGERPRINTS:
        issues.append(
            ContractIssue(
                Path(".gitleaksignore"),
                "gitleaks-fingerprint-baseline",
                "only the nine triaged historical fingerprints are allowed",
            )
        )
    config_path = root / ".gitleaks.toml"
    config = config_path.read_text(encoding="utf-8")
    for token in (
        "useDefault = true",
        'id = "mara-promptui-frp-token"',
        "promptui/tunnel",
        "secretGroup = 1",
    ):
        if token not in config:
            issues.append(
                ContractIssue(
                    Path(".gitleaks.toml"),
                    "gitleaks-frp-rule",
                    f"missing {token}",
                )
            )
    if "allowlist" in config.lower():
        issues.append(
            ContractIssue(
                Path(".gitleaks.toml"),
                "gitleaks-frp-allowlist",
                "the known historical FRP token must remain a blocking finding",
            )
        )
    return issues


def check_trusted_review(root: Path) -> list[ContractIssue]:
    path = Path(".github/workflows/supply-chain-review.yaml")
    source = (root / path).read_text(encoding="utf-8")
    workflow = _load_yaml(root, path)
    triggers = workflow.get("on", {})
    issues: list[ContractIssue] = []
    if "pull_request_target" not in triggers or "pull_request" in triggers:
        issues.append(
            ContractIssue(
                path, "trusted-review-trigger", "must use trusted base context"
            )
        )
    if triggers.get("pull_request_review", {}).get("types") != [
        "submitted",
        "dismissed",
    ]:
        issues.append(
            ContractIssue(path, "trusted-review-rerun", "review changes must rerun")
        )
    for token in (
        "pull_request.head.sha",
        "pull_request.changed_files",
        "len(files) != expected_file_count",
        "author_association",
        'review.get("state") == "APPROVED"',
        '"COLLABORATOR"',
        "two-person control",
        'startswith((".gitleaks", ".trivy"))',
        '"gitleaks.toml"',
        '"trivy.yaml"',
        '"trivy.yml"',
    ):
        if token not in source:
            issues.append(
                ContractIssue(path, "trusted-review-contract", f"missing {token}")
            )
    if "actions/checkout@" in source:
        issues.append(
            ContractIssue(path, "trusted-review-checkout", "checkout is forbidden")
        )
    return issues


def check_signed_provenance(root: Path) -> list[ContractIssue]:
    path = Path(".github/workflows/signed-provenance.yaml")
    source = (root / path).read_text(encoding="utf-8")
    quality = (root / ".github/workflows/quality-gates.yaml").read_text(
        encoding="utf-8"
    )
    issues: list[ContractIssue] = []
    for token in (
        "workflow_run.conclusion == 'success'",
        "workflow_run.event == 'push'",
        "github.event.workflow_run.id",
        "actions/attest-build-provenance@",
        "subject-digest: ${{ steps.subject.outputs.digest }}",
    ):
        if token not in source:
            issues.append(ContractIssue(path, "signed-provenance", f"missing {token}"))
    if re.search(r"(?:id-token|attestations): write", quality):
        issues.append(
            ContractIssue(
                Path(".github/workflows/quality-gates.yaml"),
                "pr-signing-permission",
                "PR quality jobs must not hold signing permissions",
            )
        )
    return issues


def check_dependency_audit(root: Path) -> list[ContractIssue]:
    path = Path(".github/workflows/quality-gates.yaml")
    workflow = _load_yaml(root, path)
    audit = workflow.get("jobs", {}).get("dependency-audit", {})
    matrix = audit.get("strategy", {}).get("matrix", {}).get("include")
    expected = [
        {"label": "root-py310", "project": ".", "python-version": "3.10"},
        {"label": "root-py311", "project": ".", "python-version": "3.11"},
        {
            "label": "container-py310",
            "project": "docker",
            "python-version": "3.10",
        },
    ]
    issues: list[ContractIssue] = []
    if matrix != expected:
        issues.append(
            ContractIssue(
                path,
                "dependency-audit-matrix",
                "root 3.10/3.11 and container 3.10 must be audited",
            )
        )
    commands = "\n".join(str(step.get("run", "")) for step in audit.get("steps", []))
    for token in (
        "check_dependency_audit.py",
        "--profile",
        "--project",
        "--python-version",
    ):
        if token not in commands:
            issues.append(ContractIssue(path, "dependency-audit", f"missing {token}"))
    setup_python = any(
        str(step.get("uses", "")).startswith("actions/setup-python@")
        and step.get("with", {}).get("python-version") == "3.10"
        for step in audit.get("steps", [])
    )
    if not setup_python:
        issues.append(
            ContractIssue(
                path,
                "dependency-audit-python",
                "dependency audit must provision the repository Python",
            )
        )
    return issues


def _check_container_quality_contract(
    path: Path, source: str, container: dict
) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    matrix = container.get("strategy", {}).get("matrix", {}).get("target")
    if matrix != ["lite", "full", "ollama"]:
        issues.append(
            ContractIssue(
                path,
                "container-matrix",
                "quality gate must build lite/full/ollama",
            )
        )
    commands = "\n".join(
        str(step.get("run", "")) for step in container.get("steps", [])
    )
    uses = "\n".join(str(step.get("uses", "")) for step in container.get("steps", []))
    required_tokens = (
        ("docker/build-push-action@", uses, "container-build"),
        ("aquasecurity/trivy-action@", uses, "container-scan"),
        ("vuln,secret,misconfig", source, "container-scanners"),
        ("HIGH,CRITICAL", source, "container-severity"),
        ("ignore-unfixed: true", source, "container-fixable-only"),
        ('exit-code: "0"', source, "container-scan-report"),
        (
            "check_container_vulnerability_baseline.py",
            commands,
            "container-scan-ratchet",
        ),
        (
            "container_vulnerability_baseline.json",
            commands,
            "container-scan-baseline",
        ),
        ("sbom", source.lower(), "container-sbom"),
        ("provenance", source.lower(), "container-provenance"),
        ("type=oci", source, "container-runtime-image"),
        ("no-cache: true", source, "container-clean-build"),
        ("skopeo copy", commands, "container-load"),
        ("docker-daemon:", commands, "container-load-target"),
        ("smoke_container_runtime.py", commands, "container-runtime-smoke"),
    )
    for token, haystack, rule in required_tokens:
        if token not in haystack:
            issues.append(ContractIssue(path, rule, f"missing {token}", token))
    expected_image_ref = "mara-quality:${{ matrix.target }}-${{ github.sha }}"
    trivy_steps = [
        step
        for step in container.get("steps", [])
        if "aquasecurity/trivy-action@" in str(step.get("uses", ""))
    ]
    if len(trivy_steps) != 3:
        issues.append(
            ContractIssue(path, "container-scan-count", "three Trivy stages required")
        )
    for step in trivy_steps:
        inputs = step.get("with", {})
        if inputs.get("image-ref") != expected_image_ref or "input" in inputs:
            issues.append(
                ContractIssue(
                    path,
                    "container-scan-artifact",
                    "Trivy must scan the OCI artifact imported into the local image tag",
                )
            )
    if commands and "--target" not in commands and "target:" not in source:
        issues.append(
            ContractIssue(
                path,
                "container-target",
                "matrix target is not passed to build",
            )
        )
    return issues


def _check_quality_job_contracts(path: Path, jobs: dict) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    python_source = str(jobs.get("python-supply-chain", {})).lower()
    for token in (
        "mara-app",
        "mara-research-cli",
        "kotaemon",
        "ktem",
        "sbom",
        "provenance",
    ):
        if token not in python_source:
            issues.append(
                ContractIssue(path, "python-attestation", f"missing {token}", token)
            )
    static_commands = "\n".join(
        str(step.get("run", "")) for step in jobs.get("static", {}).get("steps", [])
    )
    for token in (
        "uv lock --project docker --check",
        "check_container_lock_parity.py",
        "check_supply_chain_policy.py",
    ):
        if token not in static_commands:
            issues.append(
                ContractIssue(path, "static-supply-chain", f"missing {token}", token)
            )
    required_needs = set(jobs.get("required", {}).get("needs", []))
    for required_job in (
        "container-supply-chain",
        "python-supply-chain",
        "dependency-audit",
    ):
        if required_job not in required_needs:
            issues.append(
                ContractIssue(
                    path,
                    "required-needs",
                    f"required does not need {required_job}",
                    required_job,
                )
            )
    return issues


def check_quality_supply_chain(root: Path) -> list[ContractIssue]:
    path = Path(".github/workflows/quality-gates.yaml")
    source = (root / path).read_text(encoding="utf-8")
    jobs = _load_yaml(root, path).get("jobs", {})
    return [
        *_check_container_quality_contract(
            path, source, jobs.get("container-supply-chain", {})
        ),
        *_check_quality_job_contracts(path, jobs),
    ]


def check_configuration(root: Path) -> list[ContractIssue]:
    return [
        *check_precommit(root),
        *check_build_requirements(root),
        *check_workflow_tool_inputs(root),
        *check_secret_scan(root),
        *check_trusted_review(root),
        *check_signed_provenance(root),
        *check_dependency_audit(root),
        *check_quality_supply_chain(root),
    ]
