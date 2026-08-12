from pathlib import Path

import yaml

WORKFLOW_PATH = Path(".github/workflows/desktop-gate2.yaml")


def _commands(job: dict) -> str:
    return "\n".join(
        str(step.get("run", "")) for step in job.get("steps", []) if "run" in step
    )


def test_native_packages_cover_query_journal_recovery_and_single_instance() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    for job_name in ("package-linux-22", "package-windows"):
        commands = _commands(jobs[job_name])
        assert "--smoke-test-query-persistence" in commands
        assert "query_state_permission_denied" in commands
        assert "partial,typed_error,blocked_retry,recovery,single_turn" in commands
        assert "--smoke-test-single-instance" in commands
        assert "secondary_blocked,primary_focused,one_sidecar" in commands
        assert (
            "renderer_markdown=heading,list,table,code,blockquote,katex,citations,safe-links"
            in commands
        )


def test_windows_uploads_query_journal_and_two_launch_diagnostics() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    upload = next(
        step
        for step in workflow["jobs"]["package-windows"]["steps"]
        if step.get("name") == "Upload Windows smoke diagnostics"
    )
    paths = upload["with"]["path"]

    assert "windows-query-persistence-stdout.txt" in paths
    assert "windows-query-persistence-stderr.txt" in paths
    assert "windows-single-primary-stdout.txt" in paths
    assert "windows-single-secondary-stderr.txt" in paths
