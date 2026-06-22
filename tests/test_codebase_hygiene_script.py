from __future__ import annotations

import importlib.util
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


def _load_hygiene_module():
    spec = importlib.util.spec_from_file_location("check_codebase_hygiene", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def test_default_selection_ignores_deleted_tracked_python_files(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_hygiene_module()
    existing = tmp_path / "existing.py"
    existing.write_text("def ok():\n    return 1\n", encoding="utf-8")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="existing.py\ndeleted_debug.py\n",
            stderr="",
        )

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module._selected_python_files([]) == [existing]
