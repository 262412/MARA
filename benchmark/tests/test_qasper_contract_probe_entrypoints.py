from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEXT_SLURM_SCRIPT = PROJECT_ROOT / "scripts/slurm/text_route_rerun.sbatch"
PROBE_MODULES = (
    "scripts.slurm.qasper_debug_contract_probe",
    "scripts.slurm.validate_qasper_contract_probe",
)


def test_live_probe_receives_the_job_owned_formal_audit_path() -> None:
    slurm_script = TEXT_SLURM_SCRIPT.read_text(encoding="utf-8")
    assert '--audit-output "$CONTRACT_PROBE_AUDIT_PATH"' in slurm_script


def _job_owned_python(tmp_path: Path) -> Path:
    if os.name == "nt":
        pytest.skip("Slurm job-owned Python entrypoints require POSIX symlinks")
    executable = tmp_path / "job-runtime" / "venv" / "bin" / "python"
    executable.parent.mkdir(parents=True)
    executable.symlink_to(Path(sys.executable).resolve())
    return executable


@pytest.mark.parametrize("module", PROBE_MODULES)
def test_qasper_probe_module_entrypoint_matches_job_runtime(
    tmp_path: Path,
    module: str,
) -> None:
    slurm_script = TEXT_SLURM_SCRIPT.read_text(encoding="utf-8")
    expected_invocation = f'"$MARA_BENCHMARK_PYTHON" -m \\\n    {module}'
    assert expected_invocation in slurm_script

    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment["PYTHONPATH"] = str(tmp_path / "empty-pythonpath")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    result = subprocess.run(
        [str(_job_owned_python(tmp_path)), "-m", module, "--help"],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
