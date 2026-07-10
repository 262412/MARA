from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("workflow_path", "job_name"),
    [
        (".github/workflows/publish-packages.yaml", "publish"),
        (".github/workflows/build-push-docker.yaml", "build"),
    ],
)
def test_publish_jobs_are_hard_frozen(workflow_path, job_name):
    workflow = yaml.safe_load((REPO_ROOT / workflow_path).read_text(encoding="utf-8"))

    assert workflow["jobs"][job_name]["if"] == "${{ false }}"


def test_docker_context_excludes_secrets_runtime_state_and_generated_data():
    ignore_lines = {
        line.strip()
        for line in (REPO_ROOT / ".dockerignore")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    required_exclusions = {
        ".env",
        ".env.*",
        "admin-password",
        ".secrets/",
        "modelcli.yml",
        "modelcli.yaml",
        "modelcli.*.yml",
        "modelcli.*.yaml",
        "providers.yml",
        "providers.yaml",
        "providers.*.yml",
        "providers.*.yaml",
        "settings.yaml",
        "settings.*.yaml",
        ".codex/",
        "*.db",
        "*.db-*",
        "*.sqlite",
        "*.sqlite-*",
        "*.sqlite3",
        "*.sqlite3-*",
        ".cache/",
        ".mypy_cache/",
        ".pytest_cache/",
        ".ruff_cache/",
        "__pycache__/",
        ".venv/",
        "env/",
        "venv/",
        "ktem_app_data/",
        ".theflow/",
        "user_data/",
        "logs/",
        ".git",
        ".git/",
        "data/",
        "datasets/",
        "outputs/",
    }

    assert required_exclusions <= ignore_lines
    assert "!.env.example" in ignore_lines
    assert "*.sh" not in ignore_lines

    ordered_lines = (
        (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    )
    assert ordered_lines.index(".env.*") < ordered_lines.index("!.env.example")


def test_dockerfile_uses_only_explicit_application_inputs():
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY . /app" not in dockerfile
    assert "COPY .env.example /app/.env\n" not in dockerfile
    assert "COPY .env.example" not in dockerfile
    assert (
        "COPY scripts/download_pdfjs.sh /app/scripts/download_pdfjs.sh"
        not in dockerfile
    )
    assert "RUN bash scripts/download_pdfjs.sh" not in dockerfile
    assert "COPY pyproject.toml uv.lock README.md LICENSE.txt NOTICE ./" in dockerfile
    assert "COPY libs ./libs" in dockerfile
    assert "COPY docs" not in dockerfile
    assert "COPY app.py" not in dockerfile

    assert "python:3.10.20-slim-bookworm@sha256:" in dockerfile
    assert "FROM runtime-base AS lite" in dockerfile
    assert "FROM runtime-full AS full" in dockerfile
    assert "FROM runtime-full AS ollama" in dockerfile
    assert dockerfile.count("USER 10001:10001") == 3
    assert dockerfile.count("HEALTHCHECK") == 3


def test_secret_scanning_covers_full_history_and_built_image():
    workflow_path = REPO_ROOT / ".github/workflows/secret-scan.yaml"
    assert workflow_path.exists()

    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    assert workflow["permissions"] == {"contents": "read"}

    history_steps = workflow["jobs"]["repository-history"]["steps"]
    checkout_step = next(
        step for step in history_steps if "checkout" in step["name"].lower()
    )
    assert checkout_step["with"]["fetch-depth"] == 0
    history_command = "\n".join(
        step.get("run", "") for step in history_steps if "run" in step
    )
    assert "ghcr.io/gitleaks/gitleaks:v8.24.3@sha256:" in history_command
    assert " git --source /repo" in history_command
    assert " dir --source /repo" in history_command

    image_steps = workflow["jobs"]["image"]["steps"]
    build_step = next(step for step in image_steps if "Build" in step["name"])
    assert "docker build" in build_step["run"]
    assert "--target lite" in build_step["run"]
    assert "--push" not in build_step["run"]
    trivy_step = next(step for step in image_steps if "Trivy" in step["name"])
    assert trivy_step["uses"].startswith("aquasecurity/trivy-action@")
    assert trivy_step["with"]["scanners"] == "secret"
    assert trivy_step["with"]["exit-code"] == "1"
    assert trivy_step["with"]["image-ref"]
