from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SLURM_SCRIPT = PROJECT_ROOT / "scripts/slurm/multimodal_route_rerun.sbatch"
TEXT_SLURM_SCRIPT = PROJECT_ROOT / "scripts/slurm/text_route_rerun.sbatch"
RUNTIME_HELPER = PROJECT_ROOT / "scripts/slurm/benchmark_runtime_isolation.sh"
ARTIFACT_VALIDATOR = PROJECT_ROOT / "scripts/slurm/validate_benchmark_predictions.py"
CONTRACT_SMOKE_VALIDATOR = PROJECT_ROOT / "scripts/slurm/validate_contract_smoke.py"
INDEX_CONTRACT = PROJECT_ROOT / "scripts/slurm/benchmark_index_contract.py"
SEMANTIC_EVALUATOR_NORMALIZER = (
    PROJECT_ROOT / "scripts/slurm/normalize_semantic_evaluator.py"
)
RUNBOOK = PROJECT_ROOT / "docs/development/multimodal_route_runbook.md"


def _require_posix_bash() -> None:
    if os.name == "nt":
        pytest.skip("Slurm shell validation requires a POSIX bash environment")


def test_multimodal_slurm_script_is_parseable_and_uses_safe_storage_layout():
    _require_posix_bash()
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
    assert (
        'MARA_VLM_SERVE_SCRIPT="${MARA_VLM_SERVE_SCRIPT:-serve_qwen3_vl_8b_4k.sh}"'
        in text
    )
    assert '"${HPC_HOME}/${MARA_VLM_SERVE_SCRIPT}"' in text
    assert 'MARA_VLM_MAX_MODEL_LEN="${MARA_VLM_MAX_MODEL_LEN:-8192}"' in text
    assert (
        'MARA_VLM_GPU_MEMORY_UTILIZATION="${MARA_VLM_GPU_MEMORY_UTILIZATION:-0.70}"'
        in text
    )
    assert 'CUDA_VISIBLE_DEVICES="${MARA_VLM_GPU:-1}"' in text
    assert 'CUDA_VISIBLE_DEVICES="${MARA_COLVISION_GPU:-${MARA_VLM_GPU:-1}}"' in text
    assert 'ROUTE="${MARA_MULTIMODAL_ROUTE:-${MARA_PHASE3_ROUTE:-all}}"' in text
    assert 'MARA_VLM_EVIDENCE_TEXT_CHARS="${MARA_VLM_EVIDENCE_TEXT_CHARS:-120}"' in text
    assert 'MARA_VLM_TIMEOUT="${MARA_VLM_TIMEOUT:-120}"' in text
    assert 'MARA_VLM_MAX_OUTPUT_TOKENS="${MARA_VLM_MAX_OUTPUT_TOKENS:-192}"' in text
    assert 'MARA_COLVISION_DEVICE="${MARA_COLVISION_DEVICE:-cuda:0}"' in text
    assert (
        'ROUTE_TIMEOUT_SECONDS="${MARA_MULTIMODAL_ROUTE_TIMEOUT_SECONDS:-${MARA_PHASE3_ROUTE_TIMEOUT_SECONDS:-240}}"'
        in text
    )
    assert "--benchmark-prompt-policy gold_answer_v1" in text
    assert "--benchmark-no-think" in text
    assert "--route-timeout-seconds" in text
    assert "check-multimodal-backends" in text
    assert "backend-health.json" in text
    assert "--backend-health-json" in text
    assert "phase3_multimodal_summary" in text


def test_benchmark_runtime_isolation_helper_assigns_per_array_task_app_data(tmp_path):
    _require_posix_bash()
    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                "set -euo pipefail; "
                f"source {RUNTIME_HELPER}; "
                "SLURM_ARRAY_JOB_ID=12345 "
                "SLURM_ARRAY_TASK_ID=7 "
                "SLURM_JOB_ID=67890 "
                f"MARA_BENCHMARK_RUNTIME_ROOT={tmp_path} "
                "mara_configure_benchmark_runtime 'statistical suite'; "
                "printf '%s\n' \"$KH_APP_DATA_DIR\""
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    app_data_dir = Path(result.stdout.strip())
    assert app_data_dir == (
        tmp_path / "statistical-suite" / "array12345-task7-job67890" / "ktem_app_data"
    )
    assert app_data_dir.is_dir()


def test_multimodal_slurm_script_requires_isolated_benchmark_runtime():
    text = SLURM_SCRIPT.read_text(encoding="utf-8")

    assert "benchmark_runtime_isolation.sh" in text
    assert "mara_configure_benchmark_runtime" in text
    assert "mara_assert_isolated_kh_app_data" in text
    assert "mara_bootstrap_benchmark_runtime" in text
    assert "configure_mara_local_models.py" in text
    assert text.index("mara_bootstrap_benchmark_runtime") < text.index(
        "configure_mara_local_models.py"
    )
    assert (
        'KH_APP_DATA_DIR="${KH_APP_DATA_DIR:-/users/tbczhang/fastscratch/mara_runtime/ktem_app_data}"'
        not in text
    )
    assert "${MARA_RUNTIME_DIR}/ktem_app_data" not in text


def test_text_route_slurm_script_requires_isolated_benchmark_runtime():
    _require_posix_bash()
    result = subprocess.run(
        ["bash", "-n", str(TEXT_SLURM_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    text = TEXT_SLURM_SCRIPT.read_text(encoding="utf-8")
    assert "benchmark_runtime_isolation.sh" in text
    assert "mara_configure_benchmark_runtime" in text
    assert "mara_assert_isolated_kh_app_data" in text
    assert "mara_bootstrap_benchmark_runtime" in text
    assert text.index("mara_bootstrap_benchmark_runtime") < text.index(
        "configure_mara_local_models.py"
    )
    assert "--docqa-citation-mode inline" in text
    assert 'SEMANTIC_EVALUATOR="${MARA_SEMANTIC_EVALUATOR:-off}"' in text
    assert (
        'SEMANTIC_EVALUATOR_MODEL="${MARA_SEMANTIC_EVALUATOR_MODEL:-Qwen/Qwen3-8B}"'
        in text
    )
    assert '--semantic-evaluator "$SEMANTIC_EVALUATOR"' in text
    assert '--semantic-evaluator-model "$SEMANTIC_EVALUATOR_MODEL"' in text
    assert (
        '--semantic-evaluator-timeout-seconds "$SEMANTIC_EVALUATOR_TIMEOUT_SECONDS"'
        in text
    )
    assert 'MAX_CONTEXT_LENGTH="${MARA_TEXT_MAX_CONTEXT_LENGTH:-3000}"' in text
    assert '--max-context-length "$MAX_CONTEXT_LENGTH"' in text
    assert (
        'KH_APP_DATA_DIR="${KH_APP_DATA_DIR:-/users/tbczhang/fastscratch/mara_runtime/ktem_app_data}"'
        not in text
    )
    assert "${MARA_RUNTIME_DIR}/ktem_app_data" not in text


def test_text_route_slurm_script_can_emit_and_validate_full_contract_artifacts():
    text = TEXT_SLURM_SCRIPT.read_text(encoding="utf-8")

    assert 'ARTIFACT_DETAIL="${MARA_TEXT_ARTIFACT_DETAIL:-compact}"' in text
    assert '--artifact-detail "$ARTIFACT_DETAIL"' in text
    assert 'REQUIRE_CONTRACT_SMOKE="${MARA_REQUIRE_CONTRACT_SMOKE:-0}"' in text
    assert str(CONTRACT_SMOKE_VALIDATOR.name) in text
    assert '--suite-kind "$CONTRACT_SMOKE_SUITE_KIND"' in text
    assert text.index(CONTRACT_SMOKE_VALIDATOR.name) < text.index(
        "mara_cleanup_benchmark_runtime"
    )


def test_semantic_evaluator_normalizer_maps_local_alias_and_rejects_invalid_values():
    local = subprocess.run(
        [sys.executable, str(SEMANTIC_EVALUATOR_NORMALIZER), "local"],
        check=False,
        capture_output=True,
        text=True,
    )
    invalid = subprocess.run(
        [sys.executable, str(SEMANTIC_EVALUATOR_NORMALIZER), "not-a-backend"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert local.returncode == 0, local.stderr
    assert local.stdout.strip() == "local_qwen3_8b"
    assert invalid.returncode == 2
    assert "semantic evaluator must be" in invalid.stderr


def test_slurm_scripts_validate_semantic_evaluator_before_runtime_and_services():
    for script in (TEXT_SLURM_SCRIPT, SLURM_SCRIPT):
        text = script.read_text(encoding="utf-8")
        assert "normalize_semantic_evaluator.py" in text
        assert text.index("normalize_semantic_evaluator.py") < text.index(
            "mara_bootstrap_benchmark_runtime"
        )
        assert text.index("normalize_semantic_evaluator.py") < text.index(
            "start_service qwen3_8b"
        )


def test_text_route_slurm_script_uses_job_scoped_service_ports():
    text = TEXT_SLURM_SCRIPT.read_text(encoding="utf-8")

    assert "PORT_OFFSET=$((10#${SLURM_JOB_ID:-$$} % 10000))" in text
    assert 'TEXT_LLM_PORT="${MARA_TEXT_LLM_PORT:-$((20000 + PORT_OFFSET))}"' in text
    assert 'RETRIEVAL_PORT="${MARA_RETRIEVAL_PORT:-$((40000 + PORT_OFFSET))}"' in text
    assert 'MARA_QWEN3_8B_PORT="$TEXT_LLM_PORT"' in text
    assert 'MARA_RETRIEVAL_PORT="$RETRIEVAL_PORT"' in text
    assert 'MARA_TEXT_LLM_BASE_URL="$TEXT_LLM_BASE_URL"' in text
    assert 'MARA_RETRIEVAL_BASE_URL="$RETRIEVAL_BASE_URL"' in text
    assert 'MARA_LLM_BASE_URL="$TEXT_LLM_BASE_URL"' in text


def test_multimodal_slurm_script_exports_complete_runtime_topology():
    text = SLURM_SCRIPT.read_text(encoding="utf-8")

    assert (
        'MARA_TEXT_LLM_BASE_URL="${MARA_TEXT_LLM_BASE_URL:-http://127.0.0.1:8000/v1}"'
        in text
    )
    assert (
        'MARA_RETRIEVAL_BASE_URL="${MARA_RETRIEVAL_BASE_URL:-http://127.0.0.1:8002}"'
        in text
    )
    assert 'MARA_LLM_BASE_URL="${MARA_LLM_BASE_URL:-$MARA_TEXT_LLM_BASE_URL}"' in text
    assert (
        'MARA_COLVISION_ENDPOINT="${MARA_COLVISION_ENDPOINT:-http://127.0.0.1:8003/visual-score}"'
        in text
    )


def test_text_route_slurm_script_rejects_all_failed_artifacts():
    text = TEXT_SLURM_SCRIPT.read_text(encoding="utf-8")

    assert "validate_benchmark_predictions.py" in text
    assert text.index("validate_benchmark_predictions.py") < text.index(
        "mara_cleanup_benchmark_runtime"
    )


def test_multimodal_slurm_script_forwards_offline_semantic_evaluator_contract():
    text = SLURM_SCRIPT.read_text(encoding="utf-8")

    assert 'SEMANTIC_EVALUATOR="${MARA_SEMANTIC_EVALUATOR:-off}"' in text
    assert (
        'SEMANTIC_EVALUATOR_MODEL="${MARA_SEMANTIC_EVALUATOR_MODEL:-Qwen/Qwen3-8B}"'
        in text
    )
    assert '--semantic-evaluator "$SEMANTIC_EVALUATOR"' in text
    assert '--semantic-evaluator-model "$SEMANTIC_EVALUATOR_MODEL"' in text
    assert (
        '--semantic-evaluator-timeout-seconds "$SEMANTIC_EVALUATOR_TIMEOUT_SECONDS"'
        in text
    )


def test_multimodal_slurm_script_can_enforce_required_hybrid_eligibility():
    text = SLURM_SCRIPT.read_text(encoding="utf-8")

    assert "MARA_MULTIMODAL_REQUIRE_HYBRID_ELIGIBLE" in text
    assert "--require-hybrid-eligible" in text
    assert "validate_benchmark_predictions.py" in text
    assert text.index("validate_benchmark_predictions.py") < text.index(
        "mara_cleanup_benchmark_runtime"
    )


def test_benchmark_runtime_isolation_helper_bootstraps_empty_runtime():
    text = RUNTIME_HELPER.read_text(encoding="utf-8")

    assert "mara_bootstrap_benchmark_runtime" in text
    assert "mara_cleanup_benchmark_runtime" in text
    assert "create_docqa_runtime" in text
    assert "mara_assert_isolated_kh_app_data" in text


def test_text_route_slurm_script_records_and_enforces_clean_git_contract():
    text = TEXT_SLURM_SCRIPT.read_text(encoding="utf-8")

    assert "git rev-parse HEAD" in text
    assert "git status --porcelain" in text
    assert "MARA_ALLOW_DIRTY_BENCHMARK" in text
    assert "MARA_BENCHMARK_SERVICE_CONTRACT" in text


def test_slurm_scripts_export_content_digest_index_contract():
    for script in (TEXT_SLURM_SCRIPT, SLURM_SCRIPT):
        text = script.read_text(encoding="utf-8")
        assert "benchmark_index_contract.py" in text
        assert "MARA_BENCHMARK_INDEX_CONTRACT" in text
        assert text.index("benchmark_index_contract.py") < text.index(
            "python -m benchmark run"
        )


def test_index_contract_changes_when_document_content_changes(tmp_path):
    document = tmp_path / "document.txt"
    manifest = tmp_path / "manifest.json"
    document.write_text("version one", encoding="utf-8")
    manifest.write_text(
        (
            '{"schema_version":"1.0","documents":['
            f'{{"document_id":"doc","path":"{document}"}}'
            '],"examples":[],"routes":[]}'
        ),
        encoding="utf-8",
    )

    first = subprocess.run(
        [sys.executable, str(INDEX_CONTRACT), str(manifest)],
        check=False,
        capture_output=True,
        text=True,
    )
    document.write_text("version two", encoding="utf-8")
    second = subprocess.run(
        [sys.executable, str(INDEX_CONTRACT), str(manifest)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first.stdout.startswith("sha256:")
    assert first.stdout != second.stdout


def test_benchmark_runtime_cleanup_removes_only_configured_job_runtime(tmp_path):
    _require_posix_bash()
    runtime_root = tmp_path / "benchmark_runs_test"
    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                "set -euo pipefail; "
                f"source {RUNTIME_HELPER}; "
                f"MARA_BENCHMARK_RUNTIME_ROOT={runtime_root} "
                "mara_configure_benchmark_runtime 'cleanup suite'; "
                'touch "$KH_APP_DATA_DIR/sentinel"; '
                "mara_cleanup_benchmark_runtime; "
                'test ! -e "$MARA_BENCHMARK_RUNTIME_DIR"'
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_slurm_scripts_cleanup_runtime_only_after_artifact_validation():
    validation_markers = {
        TEXT_SLURM_SCRIPT: 'test -f "$RUN_DIR/summary.json"',
        SLURM_SCRIPT: '! -f "$RUN_DIR/summary.json"',
    }
    for script, validation_marker in validation_markers.items():
        text = script.read_text(encoding="utf-8")
        assert "mara_cleanup_benchmark_runtime" in text
        assert text.index(validation_marker) < text.index(
            "mara_cleanup_benchmark_runtime"
        )


def test_multimodal_runbook_documents_submission_and_evidence_locations():
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "sbatch scripts/slurm/multimodal_route_rerun.sbatch" in text
    assert "MARA_MULTIMODAL_LIMIT" in text
    assert "gold_answer_v1" in text
    assert "--benchmark-no-think" in text
    assert "summary.json" in text
    assert "backend-health.json" in text
    assert "check-multimodal-backends" in text
    assert "isolated `KH_APP_DATA_DIR`" in text
    assert "benchmark_runtime_isolation.sh" in text
    assert "shared Chroma" in text
    assert "failure taxonomy" in text.lower()
    assert "phase3_multimodal_summary" in text
    assert "page_image" in text
    assert "element" in text
    assert "hybrid" in text
