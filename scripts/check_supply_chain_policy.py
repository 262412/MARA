from __future__ import annotations

import argparse
import importlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

supply_chain_contracts = importlib.import_module(
    "scripts.supply_chain_contracts" if __package__ else "supply_chain_contracts"
)
supply_chain_pins = importlib.import_module(
    "scripts.supply_chain_pins" if __package__ else "supply_chain_pins"
)

APPROVED_ACTIONS = supply_chain_pins.APPROVED_ACTIONS
APPROVED_EXTERNAL_IMAGES = supply_chain_pins.APPROVED_EXTERNAL_IMAGES
DOCKERFILE_FRONTEND = supply_chain_pins.DOCKERFILE_FRONTEND

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
    if path.name == "publish-packages.yaml":
        if "actions/attest-build-provenance@" not in source:
            violations.append(
                _violation(
                    path, source, "release-attestation", "Python release is unsigned"
                )
            )
    if path.name == "build-push-docker.yaml":
        for token in (
            "actions/attest-build-provenance@",
            "subject-digest: ${{ steps.build.outputs.digest }}",
            "push-to-registry: true",
        ):
            if token not in source:
                violations.append(
                    _violation(path, source, "release-attestation", f"missing {token}")
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
    if "WORKDIR /var/lib/mara" not in stages.get("runtime-base", ""):
        violations.append(
            _violation(path, source, "runtime-workdir", "runtime-base WORKDIR")
        )
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


def _check_dockerfile_source(path: Path, source: str) -> list[Violation]:
    violations: list[Violation] = []
    if source.splitlines()[0] != DOCKERFILE_FRONTEND:
        violations.append(
            _violation(
                path,
                source,
                "dockerfile-frontend-pin",
                "Dockerfile frontend digest does not match the allowlist",
            )
        )
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
    if (
        "uv sync --project /opt/mara/docker --frozen --no-dev --no-editable"
        not in source
    ):
        violations.append(
            _violation(
                path,
                source,
                "locked-sync",
                "Docker dependencies must come from uv.lock",
            )
        )
    if "COPY docker/pyproject.toml docker/uv.lock ./docker/" not in source:
        violations.append(
            _violation(
                path,
                source,
                "container-lock-copy",
                "Docker build must copy the isolated container project and lock",
            )
        )
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


def check_dockerfile(root: Path) -> list[Violation]:
    path = Path("Dockerfile")
    source = (root / path).read_text(encoding="utf-8")
    violations = _check_dockerfile_source(path, source)
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
    violations.extend(_check_docker_targets(path, source))
    return violations


def check_installers(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in INSTALLER_PATHS:
        source = (root / path).read_text(encoding="utf-8")
        if path in {Path("install.sh"), Path("install.ps1")}:
            for token in ("UV_PYTHON_DOWNLOADS", "uv python find", "--frozen"):
                if token not in source:
                    violations.append(
                        _violation(path, source, "installer-lock", f"missing {token}")
                    )
        if path == Path("install.ps1"):
            for token in (
                "$syncExit = $LASTEXITCODE",
                "$initExit = $LASTEXITCODE",
                "$doctorExit = $LASTEXITCODE",
            ):
                if token not in source:
                    violations.append(
                        _violation(path, source, "native-exit-code", f"missing {token}")
                    )
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
    configuration = [
        _violation(
            issue.path,
            (root / issue.path).read_text(encoding="utf-8"),
            issue.rule,
            issue.detail,
            needle=issue.needle,
        )
        for issue in supply_chain_contracts.check_configuration(root)
    ]
    return sorted(
        [
            *check_workflows(root),
            *check_dockerfile(root),
            *check_installers(root),
            *configuration,
        ]
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
