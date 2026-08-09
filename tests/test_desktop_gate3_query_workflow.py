from pathlib import Path

import yaml

WORKFLOW_PATH = Path(".github/workflows/desktop-gate2.yaml")


def _commands(job: dict) -> str:
    return "\n".join(
        str(step.get("run", "")) for step in job.get("steps", []) if "run" in step
    )


def test_linux_cross_version_smoke_reuses_the_persisted_model_endpoint() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    for job_name in ("package-linux-22", "smoke-linux-24"):
        commands = _commands(jobs[job_name])
        assert "smoke_model_port=43127" in commands
        assert '--port "$smoke_model_port"' in commands
