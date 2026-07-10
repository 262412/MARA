from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.check_supply_chain_policy import scan_repository

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_repository_satisfies_supply_chain_policy():
    assert scan_repository(REPO_ROOT) == []


def test_supply_chain_policy_cli_is_fail_closed():
    completed = subprocess.run(
        [sys.executable, "scripts/check_supply_chain_policy.py"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "Supply-chain policy passed."
