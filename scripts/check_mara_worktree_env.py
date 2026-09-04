#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SENTINEL_HEADER = "MARA_LINKED_WORKTREE_NO_VENV=1"
CONFIG_ERROR = getattr(os, "EX_CONFIG", 78)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(detail or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def _checkout_root() -> Path:
    return Path(_git(Path.cwd(), "rev-parse", "--show-toplevel")).resolve()


def _common_git_dir(root: Path) -> Path:
    value = Path(_git(root, "rev-parse", "--git-common-dir"))
    if not value.is_absolute():
        value = root / value
    return value.resolve()


def _primary_root(root: Path) -> Path:
    return _common_git_dir(root).parent.resolve()


def _canonical_venv(root: Path) -> Path:
    primary_venv = _primary_root(root) / ".venv"
    if not primary_venv.is_symlink():
        raise RuntimeError(
            f"primary .venv must be a symlink before sharing dependencies: {primary_venv}"
        )
    return primary_venv.resolve(strict=True)


def _is_sentinel(path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        with path.open(encoding="utf-8") as stream:
            first_line = stream.readline().strip()
    except OSError:
        return False
    return first_line == SENTINEL_HEADER


def _write_sentinel(path: Path, canonical: Path) -> None:
    path.write_text(
        f"{SENTINEL_HEADER}\n"
        "This linked worktree must not create or share a project virtual environment.\n"
        f"Canonical dependencies: {canonical}\n"
        "Run scripts/run_with_canonical_env.sh for source-overlay checks.\n",
        encoding="utf-8",
    )


def check(root: Path) -> None:
    primary = _primary_root(root)
    canonical = _canonical_venv(root)
    venv = root / ".venv"
    if root == primary:
        if not venv.is_symlink() or venv.resolve(strict=True) != canonical:
            raise RuntimeError(f"primary .venv is not canonical: {venv}")
        print(f"MARA primary worktree environment is canonical: {canonical}")
        return
    if _is_sentinel(venv):
        print(f"MARA linked worktree sentinel is active: {venv}")
        return
    if venv.is_symlink() and venv.resolve(strict=False) == canonical:
        raise RuntimeError(
            f"linked worktree shares the canonical environment: {root}; "
            "run scripts/check_mara_worktree_env.py prepare-linked"
        )
    raise RuntimeError(f"linked worktree is not protected by a .venv sentinel: {root}")


def prepare_linked(root: Path) -> None:
    primary = _primary_root(root)
    canonical = _canonical_venv(root)
    if root == primary:
        raise RuntimeError("refusing to prepare the primary worktree as linked")
    venv = root / ".venv"
    if _is_sentinel(venv):
        print(f"MARA linked worktree sentinel is already active: {venv}")
        return
    if venv.is_symlink():
        target = venv.resolve(strict=False)
        if target != canonical:
            raise RuntimeError(f"refusing to replace unknown .venv target: {target}")
        venv.unlink()
        _write_sentinel(venv, canonical)
        print(f"MARA replaced shared environment symlink with sentinel: {venv}")
        return
    if venv.exists():
        raise RuntimeError(f"refusing to replace unknown .venv: {venv}")
    _write_sentinel(venv, canonical)
    print(f"MARA created linked worktree sentinel: {venv}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "prepare-linked", "canonical-venv"))
    args = parser.parse_args()
    try:
        root = _checkout_root()
        if args.action == "check":
            check(root)
        elif args.action == "prepare-linked":
            prepare_linked(root)
        else:
            print(_canonical_venv(root))
    except (OSError, RuntimeError) as exc:
        print(f"MARA environment guard: {exc}", file=sys.stderr)
        return CONFIG_ERROR
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
