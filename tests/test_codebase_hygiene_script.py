from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_codebase_hygiene.py"


def _write_baseline(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _path_key(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _run_hygiene(path: Path, baseline: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--baseline",
            str(baseline),
            str(path),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_rejects_new_over_budget_function(tmp_path: Path) -> None:
    target = tmp_path / "large_function.py"
    body = ["def too_long():", *[f"    value = {i}" for i in range(81)]]
    target.write_text("\n".join(body) + "\n", encoding="utf-8")
    baseline = _write_baseline(tmp_path, {"version": 1, "files": {}})

    result = _run_hygiene(target, baseline)

    assert result.returncode == 1
    assert "function too long" in result.stdout
    assert "too_long" in result.stdout


def test_allows_existing_over_budget_function_without_growth(
    tmp_path: Path,
) -> None:
    target = tmp_path / "legacy_function.py"
    body = ["def legacy():", *[f"    value = {i}" for i in range(81)]]
    target.write_text("\n".join(body) + "\n", encoding="utf-8")
    baseline = _write_baseline(
        tmp_path,
        {
            "version": 1,
            "files": {
                _path_key(target): {
                    "module_lines": 0,
                    "functions": {"legacy": 82},
                    "classes": {},
                    "non_actionable_broad_exceptions": 0,
                }
            },
        },
    )

    result = _run_hygiene(target, baseline)

    assert result.returncode == 0
    assert "No codebase hygiene ratchet violations." in result.stdout


def test_rejects_new_non_actionable_broad_exception(tmp_path: Path) -> None:
    target = tmp_path / "broad_exception.py"
    target.write_text(
        "\n".join(
            [
                "def hides_failure():",
                "    try:",
                "        risky_call()",
                "    except Exception:",
                "        pass",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    baseline = _write_baseline(tmp_path, {"version": 1, "files": {}})

    result = _run_hygiene(target, baseline)

    assert result.returncode == 1
    assert "non-actionable broad exception" in result.stdout
    assert "broad_exception.py" in result.stdout
