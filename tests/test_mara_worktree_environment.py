from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD = REPO_ROOT / "scripts" / "check_mara_worktree_env.py"
HOOK = REPO_ROOT / ".githooks" / "post-checkout"
SENTINEL_HEADER = "MARA_LINKED_WORKTREE_NO_VENV=1"
CONFIG_ERROR = getattr(os, "EX_CONFIG", 78)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )


def _init_repository(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "MARA Tests")
    _git(repo, "config", "user.email", "mara-tests@example.invalid")

    scripts = repo / "scripts"
    hooks = repo / ".githooks"
    scripts.mkdir()
    hooks.mkdir()
    shutil.copy2(GUARD, scripts / GUARD.name)
    shutil.copy2(HOOK, hooks / HOOK.name)
    (scripts / GUARD.name).chmod(0o755)
    (hooks / HOOK.name).chmod(0o755)
    (repo / "README.md").write_text("test repository\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "mara-guard-fixture"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "test fixture")

    canonical = tmp_path / "canonical-venv"
    (canonical / "bin").mkdir(parents=True)
    python = canonical / "bin" / "python"
    python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    python.chmod(0o755)
    (repo / ".venv").symlink_to(canonical, target_is_directory=True)
    return repo, canonical


def _guard(
    repo: Path, *args: str, check: bool = False
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / GUARD.name), *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=check,
    )


def test_primary_worktree_accepts_its_canonical_environment(tmp_path: Path):
    repo, canonical = _init_repository(tmp_path)

    completed = _guard(repo, "check", check=True)
    resolved = _guard(repo, "canonical-venv", check=True)

    assert "primary worktree environment is canonical" in completed.stdout
    assert Path(resolved.stdout.strip()) == canonical.resolve()


def test_post_checkout_hook_blocks_uv_environment_creation_in_linked_worktree(
    tmp_path: Path,
):
    repo, _ = _init_repository(tmp_path)
    linked = tmp_path / "linked"
    _git(repo, "config", "core.hooksPath", ".githooks")

    _git(repo, "worktree", "add", "--detach", str(linked), "HEAD")

    sentinel = linked / ".venv"
    assert sentinel.is_file()
    assert not sentinel.is_symlink()
    assert sentinel.read_text(encoding="utf-8").startswith(SENTINEL_HEADER)
    completed = _guard(linked, "check", check=True)
    assert "linked worktree sentinel is active" in completed.stdout


def test_prepare_linked_replaces_only_a_shared_canonical_symlink(tmp_path: Path):
    repo, canonical = _init_repository(tmp_path)
    linked = tmp_path / "linked"
    _git(repo, "worktree", "add", "--detach", str(linked), "HEAD")
    (linked / ".venv").symlink_to(canonical, target_is_directory=True)

    completed = _guard(linked, "prepare-linked", check=True)

    assert "replaced shared environment symlink" in completed.stdout
    assert (linked / ".venv").is_file()
    assert not (linked / ".venv").is_symlink()


def test_prepare_linked_preserves_an_unknown_environment(tmp_path: Path):
    repo, _ = _init_repository(tmp_path)
    linked = tmp_path / "linked"
    _git(repo, "worktree", "add", "--detach", str(linked), "HEAD")
    unknown = tmp_path / "unknown-venv"
    unknown.mkdir()
    (linked / ".venv").symlink_to(unknown, target_is_directory=True)

    completed = _guard(linked, "prepare-linked")

    assert completed.returncode == CONFIG_ERROR
    assert "refusing to replace unknown .venv" in completed.stderr
    assert (linked / ".venv").resolve() == unknown.resolve()


def test_linked_sentinel_makes_uv_fail_before_creating_an_environment(
    tmp_path: Path,
):
    repo, _ = _init_repository(tmp_path)
    linked = tmp_path / "linked"
    _git(repo, "config", "core.hooksPath", ".githooks")
    _git(repo, "worktree", "add", "--detach", str(linked), "HEAD")

    completed = subprocess.run(
        ["uv", "run", "--no-sync", "python", "-V"],
        cwd=linked,
        text=True,
        capture_output=True,
        env={**os.environ, "UV_NO_CACHE": "1"},
        check=False,
    )

    assert completed.returncode != 0
    assert (linked / ".venv").is_file()
    assert not (linked / ".venv").is_dir()
