from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_HELPER = PROJECT_ROOT / "scripts/slurm/benchmark_runtime_isolation.sh"
TEXT_SLURM_SCRIPT = PROJECT_ROOT / "scripts/slurm/text_route_rerun.sbatch"
MULTIMODAL_SLURM_SCRIPT = PROJECT_ROOT / "scripts/slurm/multimodal_route_rerun.sbatch"


def _require_posix_bash() -> None:
    if os.name == "nt":
        pytest.skip("Slurm shell validation requires a POSIX bash environment")


def _bash(
    source: str, *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    _require_posix_bash()
    return subprocess.run(
        ["bash", "-c", source],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _fake_uv(tmp_path: Path) -> Path:
    canonical_env = (PROJECT_ROOT / ".venv").resolve()
    fake_uv = tmp_path / "fake-uv"
    fake_uv.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'mkdir -p "$UV_PROJECT_ENVIRONMENT/bin"\n'
        f'ln -s "{canonical_env}/bin/python" "$UV_PROJECT_ENVIRONMENT/bin/python"\n'
        f'ln -s "{canonical_env}/lib" "$UV_PROJECT_ENVIRONMENT/lib"\n'
        f'cp "{canonical_env}/pyvenv.cfg" "$UV_PROJECT_ENVIRONMENT/pyvenv.cfg"\n',
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    return fake_uv


def _fresh_runtime_command(
    fake_uv: Path, runtime_root: Path, job_id: int, output: Path
) -> str:
    source_roots = ":".join(
        str(PROJECT_ROOT / relative)
        for relative in ("libs/slide_cli", "libs/ktem", "libs/kotaemon", ".")
    )
    return f"""
    set -euo pipefail
    export MARA_PROJECT_ROOT={PROJECT_ROOT}
    export MARA_BENCHMARK_RUNTIME_ROOT={runtime_root}
    export MARA_BENCHMARK_UV={fake_uv}
    export PYTHONPATH={source_roots}
    export SLURM_JOB_ID={job_id}
    source {RUNTIME_HELPER}
    mara_configure_benchmark_runtime concurrent-suite
    mara_bootstrap_benchmark_runtime
    cp "$MARA_BENCHMARK_RUNTIME_CONTRACT" {output}
    "$MARA_BENCHMARK_PYTHON" - <<'PY'
from slide_cli.docqa_runtime import create_docqa_runtime
print(f"fresh_docqa={{type(create_docqa_runtime()).__name__}}")
PY
    mara_cleanup_benchmark_runtime
    """


def _editable_install_fingerprint() -> dict[str, tuple[int, int, str]]:
    site_packages = next((PROJECT_ROOT / ".venv" / "lib").glob("python*/site-packages"))
    paths = sorted(
        set(site_packages.glob("direct_url.json"))
        | set(site_packages.glob("*/direct_url.json"))
        | set(site_packages.glob("__editable__*finder.py"))
    )
    return {
        str(path.relative_to(site_packages)): (
            path.stat().st_size,
            path.stat().st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in paths
    }


def test_configure_assigns_exclusive_theflow_settings_and_python_runtime(tmp_path):
    runtime_root = tmp_path / "benchmark_runs"
    result = _bash(
        f"""
        set -euo pipefail
        export MARA_PROJECT_ROOT={PROJECT_ROOT}
        export MARA_BENCHMARK_RUNTIME_ROOT={runtime_root}
        export SLURM_JOB_ID=901
        source {RUNTIME_HELPER}
        mara_configure_benchmark_runtime isolated-suite
        printf 'runtime=%s\\n' "$MARA_BENCHMARK_RUNTIME_DIR"
        printf 'app=%s\\n' "$KH_APP_DATA_DIR"
        printf 'settings_module=%s\\n' "$THEFLOW_SETTINGS_MODULE"
        printf 'settings_path=%s\\n' "$MARA_BENCHMARK_FLOWSETTINGS_PATH"
        printf 'storage=%s\\n' "$MARA_BENCHMARK_STORAGE_PREFIX"
        printf 'temp=%s\\n' "$THEFLOW_TEMP_PATH"
        printf 'python_env=%s\\n' "$UV_PROJECT_ENVIRONMENT"
        printf 'python=%s\\n' "$MARA_BENCHMARK_PYTHON"
        """,
    )

    assert result.returncode == 0, result.stderr
    runtime = runtime_root / "isolated-suite" / "job901"
    expected = {
        "runtime": f"runtime={runtime}",
        "app": f"app={runtime / 'ktem_app_data'}",
        "settings_module": "settings_module=mara_benchmark_flowsettings",
        "settings_path": f"settings_path={runtime / 'theflow' / 'mara_benchmark_flowsettings.py'}",
        "storage": f"storage={runtime / 'theflow'}",
        "temp": f"temp={runtime / 'theflow-temp'}",
        "python_env": f"python_env={runtime / 'venv'}",
        "python": f"python={runtime / 'venv' / 'bin' / 'python'}",
    }
    assert (
        expected.items()
        <= {line.split("=", 1)[0]: line for line in result.stdout.splitlines()}.items()
    )
    assert (runtime / "theflow" / "mara_benchmark_flowsettings.py").is_file()
    assert (runtime / ".owner").is_file()


def test_runtime_contract_rejects_checkout_theflow_and_shared_canonical_venv(tmp_path):
    result = _bash(
        f"""
        set -euo pipefail
        export MARA_PROJECT_ROOT={PROJECT_ROOT}
        export MARA_BENCHMARK_RUNTIME_ROOT={tmp_path / 'benchmark_runs'}
        export SLURM_JOB_ID=904
        source {RUNTIME_HELPER}
        mara_configure_benchmark_runtime shared-venv-suite
        export UV_PROJECT_ENVIRONMENT={PROJECT_ROOT}/.venv
        mara_assert_isolated_kh_app_data
        """,
    )

    assert result.returncode != 0
    assert "canonical" in result.stderr.lower() or "shared" in result.stderr.lower()

    checkout_result = _bash(
        f"""
        set -u
        export MARA_PROJECT_ROOT={PROJECT_ROOT}
        export MARA_BENCHMARK_RUNTIME_ROOT={PROJECT_ROOT}/.theflow
        export SLURM_JOB_ID=902
        source {RUNTIME_HELPER}
        mara_configure_benchmark_runtime checkout-suite
        """
    )
    assert checkout_result.returncode != 0
    assert (
        "checkout" in checkout_result.stderr.lower()
        or ".theflow" in checkout_result.stderr
    )


def test_runtime_contract_rejects_shared_storage_and_existing_job_runtime(tmp_path):
    runtime_root = tmp_path / "benchmark_runs"
    result = _bash(
        f"""
        set -euo pipefail
        export MARA_PROJECT_ROOT={PROJECT_ROOT}
        export MARA_BENCHMARK_RUNTIME_ROOT={runtime_root}
        export SLURM_JOB_ID=905
        source {RUNTIME_HELPER}
        mara_configure_benchmark_runtime shared-runtime-suite
        if (mara_configure_benchmark_runtime shared-runtime-suite); then
          printf 'unexpected shared runtime success\n' >&2
          exit 1
        fi
        original_storage="$MARA_BENCHMARK_STORAGE_PREFIX"
        export MARA_BENCHMARK_STORAGE_PREFIX={tmp_path / 'shared-theflow'}
        if mara_assert_isolated_kh_app_data; then
          printf 'unexpected shared storage success\n' >&2
          exit 1
        fi
        export MARA_BENCHMARK_STORAGE_PREFIX="$original_storage"
        mara_cleanup_benchmark_runtime
        """,
    )

    assert result.returncode == 0, result.stderr
    assert "cross-job reuse" in result.stderr
    assert "STORAGE.prefix is not job-owned" in result.stderr


def test_runtime_cleanup_rejects_foreign_owner_and_preserves_runtime(tmp_path):
    runtime_root = tmp_path / "benchmark_runs"
    result = _bash(
        f"""
        set -euo pipefail
        export MARA_PROJECT_ROOT={PROJECT_ROOT}
        export MARA_BENCHMARK_RUNTIME_ROOT={runtime_root}
        export SLURM_JOB_ID=903
        source {RUNTIME_HELPER}
        mara_configure_benchmark_runtime owner-suite
        runtime="$MARA_BENCHMARK_RUNTIME_DIR"
        export MARA_BENCHMARK_RUNTIME_OWNER_TOKEN=foreign-owner
        if mara_cleanup_benchmark_runtime; then
          printf 'unexpected cleanup success\\n' >&2
          exit 1
        fi
        test -d "$runtime"
        """,
    )

    assert result.returncode == 0, result.stderr


def test_slurm_scripts_bootstrap_and_run_with_frozen_runtime_interpreter():
    for script in (TEXT_SLURM_SCRIPT, MULTIMODAL_SLURM_SCRIPT):
        text = script.read_text(encoding="utf-8")
        assert "UV_PROJECT_ENVIRONMENT" in text
        assert "MARA_BENCHMARK_PYTHON" in text
        assert "--frozen" in text
        assert "--extra mara" in text
        assert "uv run --python 3.10" not in text
        assert text.index("mara_bootstrap_benchmark_runtime") < text.index(
            "MARA_BENCHMARK_PYTHON"
        ) or text.index("MARA_BENCHMARK_PYTHON") < text.index(
            "mara_bootstrap_benchmark_runtime"
        )


def test_runtime_self_check_records_module_and_storage_provenance():
    text = RUNTIME_HELPER.read_text(encoding="utf-8")
    for marker in (
        "sys.executable",
        "slide_cli.__file__",
        "ktem.__file__",
        "STORAGE",
        "THEFLOW_TEMP_PATH",
        "KH_APP_DATA_DIR",
        "MARA_BENCHMARK_RUNTIME_CONTRACT",
    ):
        assert marker in text


def test_ordinary_runtime_without_benchmark_marker_is_unchanged():
    result = _bash(
        f"""
        set -euo pipefail
        before="${{KH_APP_DATA_DIR-<unset>}}|${{MARA_RUNTIME_DIR-<unset>}}|${{THEFLOW_SETTINGS_MODULE-<unset>}}|${{UV_PROJECT_ENVIRONMENT-<unset>}}"
        source {RUNTIME_HELPER}
        after="${{KH_APP_DATA_DIR-<unset>}}|${{MARA_RUNTIME_DIR-<unset>}}|${{THEFLOW_SETTINGS_MODULE-<unset>}}|${{UV_PROJECT_ENVIRONMENT-<unset>}}"
        test "$before" = "$after"
        test -z "${{MARA_BENCHMARK_RUNTIME_ISOLATED-}}"
        """,
    )
    assert result.returncode == 0, result.stderr


def test_fresh_checkout_docqa_does_not_create_source_theflow(tmp_path):
    source_checkout = tmp_path / "source-checkout"
    source_checkout.mkdir()
    subprocess.run(["git", "init", "-q", source_checkout], check=True)
    for name in ("flowsettings.py", "pyproject.toml"):
        (source_checkout / name).write_bytes((PROJECT_ROOT / name).read_bytes())
    runtime_root = tmp_path / "benchmark_runs"
    source_roots = ":".join(
        str(PROJECT_ROOT / relative)
        for relative in ("libs/slide_cli", "libs/ktem", "libs/kotaemon", ".")
    )
    result = _bash(
        f"""
        set -euo pipefail
        export MARA_PROJECT_ROOT={source_checkout}
        export MARA_BENCHMARK_RUNTIME_ROOT={runtime_root}
        export PYTHONPATH={source_roots}
        export SLURM_JOB_ID=906
        source {RUNTIME_HELPER}
        mara_configure_benchmark_runtime fresh-checkout-suite
        {PROJECT_ROOT / '.venv/bin/python'} - <<'PY'
from slide_cli.docqa_runtime import create_docqa_runtime
from theflow.storage import storage

print(type(create_docqa_runtime()).__name__)
print(storage._prefix)
PY
        mara_cleanup_benchmark_runtime
        """,
    )

    assert result.returncode == 0, result.stderr
    assert "DocQARuntime" in result.stdout
    assert (
        str(runtime_root / "fresh-checkout-suite" / "job906" / "theflow")
        in result.stdout
    )
    assert not (source_checkout / ".theflow").exists()


def test_two_fresh_docqa_subprocesses_keep_runtime_and_source_storage_disjoint(
    tmp_path,
):
    fake_uv = _fake_uv(tmp_path)
    runtime_root = tmp_path / "benchmark_runs"
    outputs = [tmp_path / "contract-1.json", tmp_path / "contract-2.json"]
    processes = [
        subprocess.Popen(
            [
                "bash",
                "-c",
                _fresh_runtime_command(fake_uv, runtime_root, job_id, output),
            ],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for job_id, output in ((9101, outputs[0]), (9102, outputs[1]))
    ]
    results = [process.communicate(timeout=90) for process in processes]

    for process, (stdout, stderr) in zip(processes, results):
        returncode = process.returncode
        assert returncode == 0, f"{stdout}\n{stderr}"
        assert "bootstrapped_runtime=DocQARuntime" in stdout
        assert "fresh_docqa=DocQARuntime" in stdout
    contracts = [json.loads(output.read_text(encoding="utf-8")) for output in outputs]
    assert contracts[0]["KH_APP_DATA_DIR"] != contracts[1]["KH_APP_DATA_DIR"]
    assert (
        contracts[0]["theflow_storage_prefix"] != contracts[1]["theflow_storage_prefix"]
    )
    assert all(
        str(PROJECT_ROOT / ".theflow") not in contract["theflow_storage_prefix"]
        for contract in contracts
    )


def test_runtime_bootstrap_does_not_change_canonical_venv_or_editable_origins(tmp_path):
    fake_uv = _fake_uv(tmp_path)
    before_link = os.readlink(PROJECT_ROOT / ".venv")
    before_editable = _editable_install_fingerprint()
    result = _bash(
        _fresh_runtime_command(
            fake_uv,
            tmp_path / "benchmark_runs",
            9103,
            tmp_path / "contract.json",
        )
    )
    assert result.returncode == 0, result.stderr
    assert os.readlink(PROJECT_ROOT / ".venv") == before_link
    assert _editable_install_fingerprint() == before_editable


def test_mixed_checkout_module_origin_fails_closed(tmp_path):
    fake_uv = _fake_uv(tmp_path)
    foreign_root = tmp_path / "foreign"
    foreign_root.mkdir()
    (foreign_root / "slide_cli").mkdir()
    (foreign_root / "slide_cli" / "__init__.py").write_text(
        "# intentionally foreign package origin\n", encoding="utf-8"
    )
    result = _bash(
        f"""
        set -euo pipefail
        export MARA_PROJECT_ROOT={PROJECT_ROOT}
        export MARA_BENCHMARK_RUNTIME_ROOT={tmp_path / 'benchmark_runs'}
        export MARA_BENCHMARK_UV={fake_uv}
        export PYTHONPATH={foreign_root}:{PROJECT_ROOT / 'libs/ktem'}:{PROJECT_ROOT / 'libs/kotaemon'}:{PROJECT_ROOT}
        export SLURM_JOB_ID=9104
        source {RUNTIME_HELPER}
        mara_install_benchmark_runtime_cleanup
        mara_configure_benchmark_runtime mixed-origin-suite
        if mara_bootstrap_benchmark_runtime; then
          printf 'unexpected mixed-origin success\\n' >&2
          exit 1
        fi
        """,
    )
    assert result.returncode == 0, result.stderr
    assert "checkout boundary" in result.stderr or "ktem.__file__" in result.stderr
    assert not (tmp_path / "benchmark_runs" / "mixed-origin-suite" / "job9104").exists()
