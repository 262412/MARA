from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = REPO_ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _baseline(**files):
    return {
        "version": 1,
        "budgets": {
            "function_lines": 80,
            "class_lines": 300,
            "module_lines": 600,
        },
        "files": files,
    }


def test_baseline_guard_allows_only_monotonic_debt_reduction():
    guard = _load_script("check_hygiene_baseline.py")
    base = _baseline(
        **{
            "large.py": {
                "module_lines": 900,
                "functions": {"large": 120},
                "classes": {"Large": 350},
                "non_actionable_broad_exceptions": 3,
            }
        }
    )
    reduced = _baseline(
        **{
            "large.py": {
                "module_lines": 850,
                "functions": {"large": 100},
                "classes": {"Large": 320},
                "non_actionable_broad_exceptions": 2,
            }
        }
    )

    assert guard.compare_baselines(base, reduced) == []
    assert guard.compare_baselines(base, _baseline()) == []


def test_baseline_guard_rejects_raised_and_new_exemptions():
    guard = _load_script("check_hygiene_baseline.py")
    base = _baseline(
        **{
            "large.py": {
                "module_lines": 900,
                "functions": {"large": 120},
                "classes": {},
                "non_actionable_broad_exceptions": 1,
            }
        }
    )
    widened = _baseline(
        **{
            "large.py": {
                "module_lines": 901,
                "functions": {"large": 121, "new_large": 81},
                "classes": {},
                "non_actionable_broad_exceptions": 2,
            },
            "new.py": {
                "module_lines": 601,
                "functions": {},
                "classes": {},
                "non_actionable_broad_exceptions": 0,
            },
        }
    )

    violations = guard.compare_baselines(base, widened)
    message = "\n".join(violations)
    assert "large.py: module_lines increased from 900 to 901" in message
    assert "large.py: new function exemption new_large" in message
    assert "large.py: non_actionable_broad_exceptions increased" in message
    assert "new.py: new baseline file exemption" in message


def test_baseline_guard_cli_compares_against_git_merge_base(tmp_path):
    guard_path = REPO_ROOT / "scripts" / "check_hygiene_baseline.py"
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "ci@example.invalid"], cwd=repo)
    subprocess.run(["git", "config", "user.name", "CI"], cwd=repo)
    baseline_path = repo / "scripts" / "codebase_hygiene_baseline.json"
    baseline_path.parent.mkdir()
    baseline_path.write_text(json.dumps(_baseline()), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True)
    baseline_path.write_text(
        json.dumps(
            _baseline(
                **{
                    "new.py": {
                        "module_lines": 601,
                        "functions": {},
                        "classes": {},
                        "non_actionable_broad_exceptions": 0,
                    }
                }
            )
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "widen"], cwd=repo, check=True)

    result = subprocess.run(
        [
            sys.executable,
            str(guard_path),
            "--repo",
            str(repo),
            "--base-ref",
            base.strip(),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "new.py: new baseline file exemption" in result.stdout
    assert "Reduce or remove the exemption" in result.stdout


def test_coverage_policy_has_real_package_floors_and_excludes_tests():
    coverage_gate = _load_script("run_coverage_gates.py")

    assert coverage_gate.COVERAGE_FLOORS == {
        "benchmark": 90,
        "slide_cli": 70,
        "kotaemon": 60,
        "ktem": 50,
    }
    assert all("test" not in path for path in coverage_gate.PRODUCTION_PATHS.values())
    assert "*/tests/*" in coverage_gate.COVERAGE_OMIT
    assert "*/ktem_tests/*" in coverage_gate.COVERAGE_OMIT


def test_coverage_policy_captures_python_subprocesses(tmp_path):
    coverage_gate = _load_script("run_coverage_gates.py")

    config_path = coverage_gate.write_coverage_config(tmp_path)
    config = config_path.read_text(encoding="utf-8")

    assert "patch = subprocess" in config
    assert "parallel = True" in config
    assert "relative_files = True" in config


def test_qasper_local_gate_covers_provider_generation_and_audit():
    qasper_gate = _load_script("run_qasper_local_gate.py")

    required_tests = {
        "benchmark/tests/test_qasper_contract_probe_assertion_scope.py",
        "benchmark/tests/test_qasper_contract_probe_generation.py",
        "benchmark/tests/test_qasper_contract_probe_audit.py",
        "libs/ktem/ktem_tests/test_qasper_assertion_scope_contract.py",
        "libs/ktem/ktem_tests/test_mara_semantic_local_consistency.py",
        "libs/ktem/ktem_tests/test_qasper_frozen_audit_authority.py",
        "libs/ktem/ktem_tests/test_mara_semantic_audit_repair.py",
        "libs/ktem/ktem_tests/test_qasper_stage9_10397107_auditor_serialization.py",
        "benchmark/tests/test_qasper_stage9_causal_transaction.py",
    }

    assert required_tests <= set(qasper_gate.QASPER_LOCAL_GATE_TESTS)
    assert all(
        (REPO_ROOT / path).is_file() for path in qasper_gate.QASPER_LOCAL_GATE_TESTS
    )


def test_qasper_local_gate_builds_an_explicit_pytest_command():
    qasper_gate = _load_script("run_qasper_local_gate.py")

    command = qasper_gate.pytest_command("--maxfail=1")

    assert command[:4] == [sys.executable, "-m", "pytest", "-q"]
    assert command[-1] == "--maxfail=1"
    assert (
        command.count("benchmark/tests/test_qasper_contract_probe_generation.py") == 1
    )
    assert command.count("benchmark/tests/test_qasper_contract_probe_audit.py") == 1


def test_qasper_local_gate_is_mandatory_before_provider_backed_runs():
    contract = (
        REPO_ROOT / "docs" / "development" / "codebase-hygiene-contract.md"
    ).read_text(encoding="utf-8")

    assert "Before any QASPER Provider probe, natural probe, or 6x3 submission" in (
        contract
    )
    assert "scripts/run_qasper_local_gate.py" in contract


def test_diff_coverage_uses_only_changed_production_statements(tmp_path):
    diff_gate = _load_script("check_diff_coverage.py")
    payload = {
        "files": {
            "benchmark/example.py": {
                "executed_lines": [1, 2, 5],
                "missing_lines": [3],
                "excluded_lines": [4],
            },
            "benchmark/tests/test_example.py": {
                "executed_lines": [1, 2, 3],
                "missing_lines": [],
                "excluded_lines": [],
            },
        }
    }
    coverage_json = tmp_path / "coverage.json"
    coverage_json.write_text(json.dumps(payload), encoding="utf-8")
    changed = {
        "benchmark/example.py": {1, 2, 3, 4, 5},
        "benchmark/tests/test_example.py": {1, 2, 3},
    }

    result = diff_gate.calculate_diff_coverage(coverage_json, changed)

    assert result.covered == 3
    assert result.total == 4
    assert result.percent == 75.0


def test_collection_gate_parses_root_summary_and_enforces_floor(monkeypatch, capsys):
    collection_gate = _load_script("check_pytest_collection.py")

    assert (
        collection_gate.parse_collected_count("1512 tests collected in 14.57s\n")
        == 1512
    )
    with pytest.raises(ValueError, match="collection summary"):
        collection_gate.parse_collected_count("collection output without a summary")

    completed = subprocess.CompletedProcess(
        args=[sys.executable, "-m", "pytest"],
        returncode=0,
        stdout="1259 tests collected in 1.00s\n",
    )
    monkeypatch.setattr(
        collection_gate.subprocess, "run", lambda *args, **kwargs: completed
    )

    assert collection_gate.run_collection(minimum=1260, pytest_args=()) == 1
    assert "below required minimum 1260" in capsys.readouterr().out


def test_collection_gate_preserves_pytest_collection_failure(monkeypatch):
    collection_gate = _load_script("check_pytest_collection.py")
    completed = subprocess.CompletedProcess(
        args=[sys.executable, "-m", "pytest"],
        returncode=2,
        stdout="collection error\n",
    )
    monkeypatch.setattr(
        collection_gate.subprocess, "run", lambda *args, **kwargs: completed
    )

    assert collection_gate.run_collection(minimum=1260, pytest_args=()) == 2
