from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = Path(".github/workflows")
RELEASE_JOBS = {
    "auto-bump-and-release.yaml": "auto-bump-and-release",
    "build-push-docker.yaml": "build",
    "publish-packages.yaml": "publish",
}
INSTALLER_PATHS = (
    Path("install.sh"),
    Path("install.ps1"),
    Path("scripts/run_linux.sh"),
    Path("scripts/run_macos.sh"),
    Path("scripts/run_windows.bat"),
    Path("scripts/setup.sh"),
    Path("scripts/setup.ps1"),
    Path("scripts/update_linux.sh"),
    Path("scripts/update_macos.sh"),
    Path("scripts/update_windows.bat"),
)
FULL_SHA = re.compile(r"[0-9a-f]{40}")
ACTION_LINE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)(?:\s+#\s*([^\s]+))?\s*$")
FROM_LINE = re.compile(
    r"^FROM\s+(?P<image>[^\s]+)(?:\s+AS\s+(?P<stage>[A-Za-z0-9_.-]+))?\s*$",
    re.IGNORECASE,
)
EXTERNAL_IMAGE = re.compile(r"^[^:@\s]+(?:/[^:@\s]+)*:[^@\s]+@sha256:[0-9a-f]{64}$")
APPROVED_EXTERNAL_IMAGES = {
    "ghcr.io/astral-sh/uv:0.11.19@sha256:b46b03ddfcfbf8f547af7e9eaefdf8a39c8cebcba7c98858d3162bd28cf536f6",
    "ollama/ollama:0.31.2@sha256:509fdf54e23bd50d87af646cb51c0a7a203d6a83cc4d6695b3b08c5be1c62c0a",
    "python:3.10.20-slim-bookworm@sha256:ff7161e2b8e2a56fc6a62a6099ff8feb72f1a6dbae9860cdcb9a6c65cf4c6be9",
}
APPROVED_ACTIONS = {
    "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683": "v4.2.2",
    "actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10": "v6.0.3",
    "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093": "v4.3.0",
    "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065": "v5.6.0",
    "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02": "v4.6.2",
    "amannn/action-semantic-pull-request@0723387faaf9b38adef4775cd42cfd5155ed6017": "v5.5.3",
    "anothrNick/github-tag-action@4ed44965e0db8dab2b466a16da04aec3cc312fd8": "1.75.0",
    "aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25": "v0.36.0",
    "astral-sh/setup-uv@b75a909f75acd358c2196fb9a5f1299a9a8868a4": "v6.7.0",
    "buildingcash/json-to-markdown-table-action@b442169239ef35f1dc4e5c8c3d47686c081a7e65": "v1.1.0",
    "docker/build-push-action@10e90e3645eae34f1e60eeb005ba3a3d33f178e8": "v6.19.2",
    "docker/login-action@c94ce9fb468520275223c153574b00df6fe4bcc9": "v3.7.0",
    "docker/metadata-action@c299e40c65443455700f0fdfc63efafe5b349051": "v5.10.0",
    "docker/setup-buildx-action@8d2750c68a42422c14e847fe6c8ac0403b4cbd6f": "v3.12.0",
    "docker/setup-qemu-action@c7c53464625b32c7a7e944ae62b3e17d2b600130": "v3.7.0",
    "gitleaks/gitleaks-action@e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e": "v3.0.0",
    "jlumbroso/free-disk-space@54081f138730dfa15788a46383842cd2f914a1be": "v1.3.1",
    "marocchino/sticky-pull-request-comment@773744901bac0e8cbb5a0dc842800d45e9b2b405": "v2.9.4",
    "softprops/action-gh-release@3bb12739c298aeb8a4eeaf626c5b8d85266b0e65": "v2.6.2",
    "wagoid/commitlint-github-action@b948419dd99f3fd78a6548d48f94e3df7f6bf3ed": "v6.2.1",
}
FORBIDDEN_DOWNLOADS = (
    (re.compile(r"curl\s+[^\n|]*-k(?:\s|$)", re.IGNORECASE), "insecure-curl"),
    (re.compile(r"curl[^\n|]*\|\s*(?:ba)?sh\b", re.IGNORECASE), "curl-pipe-shell"),
    (re.compile(r"Miniconda3-latest", re.IGNORECASE), "mutable-download"),
    (
        re.compile(r"git\+https?://[^\s\"']+@(?:main|latest)\b", re.IGNORECASE),
        "moving-git-ref",
    ),
    (
        re.compile(
            r"git\s+(?:clone|checkout)[^\n]*(?:\bmain\b|\blatest\b)", re.IGNORECASE
        ),
        "moving-git-ref",
    ),
)


@dataclass(frozen=True, order=True)
class Violation:
    path: str
    line: int
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.detail}"


def _line_number(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _violation(
    path: Path,
    source: str,
    rule: str,
    detail: str,
    *,
    needle: str | None = None,
) -> Violation:
    offset = source.find(needle) if needle else 0
    return Violation(
        path.as_posix(), _line_number(source, max(offset, 0)), rule, detail
    )


def _load_yaml(root: Path, path: Path) -> dict:
    payload = yaml.safe_load((root / path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload


def _check_action_pins(path: Path, source: str) -> list[Violation]:
    violations: list[Violation] = []
    for number, line in enumerate(source.splitlines(), start=1):
        if "uses:" not in line:
            continue
        match = ACTION_LINE.match(line)
        if not match:
            violations.append(
                Violation(
                    path.as_posix(),
                    number,
                    "action-line",
                    "uses line must contain one action and an exact version comment",
                )
            )
            continue
        action, version_comment = match.groups()
        if action.startswith("./"):
            continue
        reference = action.rsplit("@", 1)[-1] if "@" in action else ""
        if not FULL_SHA.fullmatch(reference):
            violations.append(
                Violation(
                    path.as_posix(),
                    number,
                    "action-pin",
                    f"{action} is not pinned to 40 hex",
                )
            )
        expected_version = APPROVED_ACTIONS.get(action)
        if expected_version is None:
            violations.append(
                Violation(
                    path.as_posix(),
                    number,
                    "action-allowlist",
                    f"{action} was not independently verified",
                )
            )
        if version_comment != expected_version:
            violations.append(
                Violation(
                    path.as_posix(),
                    number,
                    "action-version-comment",
                    f"{action} must be commented as {expected_version!r}",
                )
            )
    return violations


def _check_runners(path: Path, source: str) -> list[Violation]:
    violations: list[Violation] = []
    for number, line in enumerate(source.splitlines(), start=1):
        if not re.match(r"^\s*runs-on\s*:", line):
            continue
        runner = line.split(":", 1)[1].split("#", 1)[0].strip().strip("\"'")
        if runner != "ubuntu-24.04":
            violations.append(
                Violation(
                    path.as_posix(), number, "runner-pin", f"runner is {runner!r}"
                )
            )
    return violations


def _check_workflow_commands(path: Path, source: str) -> list[Violation]:
    violations: list[Violation] = []
    patterns = (
        (
            r"\bnpx(?:\s+--yes)?\b",
            "unlocked-playwright",
            "use the package-lock executable",
        ),
        (
            r"\bpython\s+-m\s+pip\s+install\b|(?<!uv )\bpip\s+install\b",
            "unlocked-python-install",
            "workflow install is outside uv.lock",
        ),
        (
            r"\bmake_latest\s*:",
            "mutable-release-alias",
            "latest release aliases are forbidden",
        ),
        (
            r"type=raw,value=latest",
            "mutable-image-tag",
            "latest image tags are forbidden",
        ),
        (
            r"tonistiigi/binfmt:latest",
            "mutable-image",
            "binfmt image must use version and digest",
        ),
    )
    for pattern, rule, detail in patterns:
        for match in re.finditer(pattern, source, re.IGNORECASE):
            violations.append(
                Violation(
                    path.as_posix(), _line_number(source, match.start()), rule, detail
                )
            )
    return violations


def _check_release_freeze(
    root: Path, path: Path, workflow: dict, source: str
) -> list[Violation]:
    violations: list[Violation] = []
    publish_job = RELEASE_JOBS.get(path.name)
    if not publish_job:
        return violations
    jobs = workflow.get("jobs", {})
    quality = jobs.get("quality", {})
    publish = jobs.get(publish_job, {})
    if quality.get("uses") != "./.github/workflows/quality-gates.yaml":
        violations.append(
            _violation(path, source, "release-gate", "missing reusable quality gate")
        )
    if publish.get("needs") != "quality":
        violations.append(
            _violation(
                path, source, "release-needs", f"{publish_job} must need quality"
            )
        )
    if publish.get("if") != "${{ false }}":
        violations.append(
            _violation(
                path, source, "release-freeze", f"{publish_job} is not hard-frozen"
            )
        )
    return violations


def _check_quality_supply_chain(root: Path) -> list[Violation]:
    path = WORKFLOW_DIR / "quality-gates.yaml"
    source = (root / path).read_text(encoding="utf-8")
    workflow = _load_yaml(root, path)
    jobs = workflow.get("jobs", {})
    violations: list[Violation] = []
    container = jobs.get("container-supply-chain", {})
    matrix = container.get("strategy", {}).get("matrix", {}).get("target")
    if matrix != ["lite", "full", "ollama"]:
        violations.append(
            _violation(
                path,
                source,
                "container-matrix",
                "quality gate must build lite/full/ollama",
            )
        )
    commands = "\n".join(
        str(step.get("run", "")) for step in container.get("steps", [])
    )
    uses = "\n".join(str(step.get("uses", "")) for step in container.get("steps", []))
    contract_tokens = (
        ("docker/build-push-action@", uses, "container-build"),
        ("aquasecurity/trivy-action@", uses, "container-scan"),
        ("vuln,secret,misconfig", source, "container-scanners"),
        ("HIGH,CRITICAL", source, "container-severity"),
        ("ignore-unfixed: true", source, "container-fixable-only"),
        ('exit-code: "1"', source, "container-scan-fail"),
        ("sbom", source.lower(), "container-sbom"),
        ("provenance", source.lower(), "container-provenance"),
    )
    for token, haystack, rule in contract_tokens:
        if token not in haystack:
            violations.append(_violation(path, source, rule, f"missing {token}"))
    if commands and "--target" not in commands and "target:" not in source:
        violations.append(
            _violation(
                path, source, "container-target", "matrix target is not passed to build"
            )
        )
    python_job = jobs.get("python-supply-chain", {})
    python_source = str(python_job)
    for token in (
        "mara-app",
        "mara-research-cli",
        "kotaemon",
        "ktem",
        "sbom",
        "provenance",
    ):
        if token not in python_source.lower():
            violations.append(
                _violation(path, source, "python-attestation", f"missing {token}")
            )
    required_needs = set(jobs.get("required", {}).get("needs", []))
    for required_job in ("container-supply-chain", "python-supply-chain"):
        if required_job not in required_needs:
            violations.append(
                _violation(
                    path,
                    source,
                    "required-needs",
                    f"required does not need {required_job}",
                )
            )
    return violations


def check_workflows(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for absolute_path in sorted((root / WORKFLOW_DIR).glob("*.y*ml")):
        path = absolute_path.relative_to(root)
        source = absolute_path.read_text(encoding="utf-8")
        workflow = _load_yaml(root, path)
        violations.extend(_check_action_pins(path, source))
        violations.extend(_check_runners(path, source))
        violations.extend(_check_workflow_commands(path, source))
        violations.extend(_check_release_freeze(root, path, workflow, source))
    violations.extend(_check_quality_supply_chain(root))
    return violations


def _docker_stages(source: str) -> dict[str, str]:
    matches = list(
        re.finditer(
            r"^FROM\s+[^\n]+\s+AS\s+([A-Za-z0-9_.-]+)\s*$",
            source,
            re.MULTILINE | re.IGNORECASE,
        )
    )
    stages: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        stages[match.group(1).lower()] = source[match.start() : end]
    return stages


def _check_docker_targets(path: Path, source: str) -> list[Violation]:
    violations: list[Violation] = []
    stages = _docker_stages(source)
    for target in ("lite", "full", "ollama"):
        stage = stages.get(target, "")
        for token, rule in (
            ("USER 10001:10001", "non-root-user"),
            ("HEALTHCHECK", "healthcheck"),
            ('ENTRYPOINT ["/usr/bin/tini"', "pid1"),
            ("HOME=/home/mara", "runtime-home"),
            ("KH_APP_DATA_DIR=/var/lib/mara", "runtime-data"),
            ("MARA_AUTH_MODE=password", "network-auth"),
            (
                "MARA_ADMIN_PASSWORD_FILE=/run/secrets/mara_admin_password",
                "password-secret-file",
            ),
        ):
            if token not in stage:
                violations.append(
                    _violation(path, source, rule, f"{target} missing {token}")
                )
    return violations


def check_dockerfile(root: Path) -> list[Violation]:
    path = Path("Dockerfile")
    source = (root / path).read_text(encoding="utf-8")
    violations: list[Violation] = []
    internal_stages: set[str] = set()
    for number, line in enumerate(source.splitlines(), start=1):
        match = FROM_LINE.match(line.strip())
        if not match:
            continue
        image = match.group("image")
        if image.lower() not in internal_stages and not EXTERNAL_IMAGE.fullmatch(image):
            violations.append(
                Violation(
                    path.as_posix(),
                    number,
                    "base-image-pin",
                    f"{image} lacks fixed version/digest",
                )
            )
        elif (
            image.lower() not in internal_stages
            and image not in APPROVED_EXTERNAL_IMAGES
        ):
            violations.append(
                Violation(
                    path.as_posix(),
                    number,
                    "base-image-allowlist",
                    f"{image} was not independently verified",
                )
            )
        if match.group("stage"):
            internal_stages.add(match.group("stage").lower())
    forbidden = (
        (r"\bcurl\b[^\n|]*\|\s*(?:ba)?sh\b", "curl-pipe-shell"),
        (r"\b(?:uv\s+)?pip\s+install\b", "unlocked-python-install"),
        (r"git\+https?://", "git-dependency"),
        (r"\bollama\s+pull\b", "implicit-model-pull"),
    )
    for pattern, rule in forbidden:
        for match in re.finditer(pattern, source, re.IGNORECASE):
            violations.append(
                Violation(
                    path.as_posix(),
                    _line_number(source, match.start()),
                    rule,
                    match.group(0),
                )
            )
    if "uv sync --frozen --no-dev" not in source:
        violations.append(
            _violation(
                path,
                source,
                "locked-sync",
                "Docker dependencies must come from uv.lock",
            )
        )
    violations.extend(_check_docker_targets(path, source))
    for token, rule in (
        ("/usr/lib/ollama", "ollama-libraries"),
        ("OLLAMA_MODELS=/var/lib/mara/ollama", "ollama-model-dir"),
        ("prepare_container_nltk.py", "offline-nltk"),
        ("network download forbidden", "offline-nltk-smoke"),
        ("NLTK_DATA=/opt/mara/.venv", "offline-nltk-runtime"),
        ("chmod -R a-w /opt/mara", "readonly-source"),
    ):
        if token not in source:
            violations.append(_violation(path, source, rule, f"missing {token}"))
    if re.search(r"MARA_ADMIN_PASSWORD\s*=\s*[^\s$]", source):
        violations.append(
            _violation(path, source, "baked-password", "image embeds an admin password")
        )
    return violations


def check_installers(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in INSTALLER_PATHS:
        source = (root / path).read_text(encoding="utf-8")
        for pattern, rule in FORBIDDEN_DOWNLOADS:
            for match in pattern.finditer(source):
                violations.append(
                    Violation(
                        path.as_posix(),
                        _line_number(source, match.start()),
                        rule,
                        match.group(0),
                    )
                )
        for match in re.finditer(
            r"(?:python\s+-m\s+)?pip\s+install\b", source, re.IGNORECASE
        ):
            violations.append(
                Violation(
                    path.as_posix(),
                    _line_number(source, match.start()),
                    "unlocked-python-install",
                    match.group(0),
                )
            )
        for match in re.finditer(
            r"(?:curl|wget|Invoke-WebRequest)\b", source, re.IGNORECASE
        ):
            violations.append(
                Violation(
                    path.as_posix(),
                    _line_number(source, match.start()),
                    "unchecked-download",
                    match.group(0),
                )
            )
    return violations


def scan_repository(root: Path = REPO_ROOT) -> list[Violation]:
    return sorted(
        [*check_workflows(root), *check_dockerfile(root), *check_installers(root)]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enforce MARA supply-chain policy.")
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    violations = scan_repository(args.root.resolve())
    if violations:
        print("Supply-chain policy violations:")
        for violation in violations:
            print(f"- {violation.render()}")
        return 1
    print("Supply-chain policy passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
