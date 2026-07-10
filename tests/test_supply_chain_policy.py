from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.check_supply_chain_policy import _check_action_pins, scan_repository

REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_INSTALLERS = (
    "scripts/run_linux.sh",
    "scripts/run_macos.sh",
    "scripts/run_windows.bat",
    "scripts/setup.sh",
    "scripts/setup.ps1",
    "scripts/update_linux.sh",
    "scripts/update_macos.sh",
    "scripts/update_windows.bat",
)


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


def test_canonical_installers_use_only_the_frozen_source_lock():
    for relative in ("install.sh", "install.ps1"):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "uv sync" in source
        assert "--frozen" in source
        assert "--no-dev" in source
        assert "pip install" not in source
        assert "mara-app[mara]" not in source


def test_legacy_installers_are_formally_retired_and_fail_closed():
    for relative in LEGACY_INSTALLERS:
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "retired" in source.lower(), relative
        assert "install.sh" in source or "install.ps1" in source, relative
        if relative.endswith((".bat", ".ps1")):
            assert "exit" in source.lower() and "64" in source, relative
        else:
            assert "exit 64" in source, relative


def test_action_policy_rejects_unknown_digests_and_malformed_version_comments():
    unknown = (
        "steps:\n"
        "  - uses: actions/checkout@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        " # v4.2.2\n"
    )
    malformed = (
        "steps:\n"
        "  - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683"
        " # release-4\n"
    )

    unknown_rules = {
        item.rule for item in _check_action_pins(Path("test.yml"), unknown)
    }
    malformed_rules = {
        item.rule for item in _check_action_pins(Path("test.yml"), malformed)
    }

    assert "action-allowlist" in unknown_rules
    assert "action-version-comment" in malformed_rules
