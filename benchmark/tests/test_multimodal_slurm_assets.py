from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SLURM_SCRIPT = PROJECT_ROOT / "scripts/slurm/multimodal_route_rerun.sbatch"
RUNBOOK = PROJECT_ROOT / "docs/development/multimodal_route_runbook.md"


def test_multimodal_slurm_script_is_parseable_and_uses_safe_storage_layout():
    result = subprocess.run(
        ["bash", "-n", str(SLURM_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    text = SLURM_SCRIPT.read_text(encoding="utf-8")
    assert "source ~/.bashrc" in text
    assert text.index("source ~/.bashrc") < text.index("set -euo pipefail")
    assert "/mnt/scratch/users/tbczhang/outputs/MARA" in text
    assert "/mnt/data2/users/tbczhang" not in text
    assert "projects/MARA/outputs" not in text


def test_multimodal_slurm_script_health_checks_backends_and_runs_no_think_routes():
    text = SLURM_SCRIPT.read_text(encoding="utf-8")

    assert "http://127.0.0.1:8000/v1/models" in text
    assert "http://127.0.0.1:8001/v1/models" in text
    assert "http://127.0.0.1:8002/health" in text
    assert "http://127.0.0.1:8003/health" in text
    assert "serve_qwen3_vl_8b.sh" in text
    assert 'CUDA_VISIBLE_DEVICES="${MARA_VLM_GPU:-1}"' in text
    assert 'ROUTE="${MARA_MULTIMODAL_ROUTE:-${MARA_PHASE3_ROUTE:-all}}"' in text
    assert "--benchmark-prompt-policy gold_answer_v1" in text
    assert "--benchmark-no-think" in text
    assert "--route-timeout-seconds" in text
    assert "phase3_multimodal_summary" in text


def test_multimodal_runbook_documents_submission_and_evidence_locations():
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "sbatch scripts/slurm/multimodal_route_rerun.sbatch" in text
    assert "MARA_MULTIMODAL_LIMIT" in text
    assert "gold_answer_v1" in text
    assert "--benchmark-no-think" in text
    assert "summary.json" in text
    assert "phase3_multimodal_summary" in text
    assert "page_image" in text
    assert "element" in text
    assert "hybrid" in text
