#!/usr/bin/env bash
#SBATCH --job-name=mara-mm-route
#SBATCH --partition=gpu-l40s-low
#SBATCH --gres=gpu:l40s:2
#SBATCH --cpus-per-task=16
#SBATCH --mem=96G
#SBATCH --time=08:00:00
#SBATCH --output=/mnt/scratch/users/tbczhang/outputs/MARA/slurm/%x-%j.out
#SBATCH --error=/mnt/scratch/users/tbczhang/outputs/MARA/slurm/%x-%j.err

source ~/.bashrc
set -euo pipefail

PROJECT_ROOT="${MARA_PROJECT_ROOT:-/mnt/scratch/users/tbczhang/projects/MARA}"
export MARA_PROJECT_ROOT="$PROJECT_ROOT"
HPC_HOME="${MARA_HPC_HOME:-/mnt/scratch/users/tbczhang/mara-hpc}"
OUT_ROOT="${MARA_MULTIMODAL_OUTPUT_DIR:-${MARA_PHASE3_OUTPUT_DIR:-/mnt/scratch/users/tbczhang/outputs/MARA/multimodal_route_slurm}}"
MANIFEST="${MARA_MULTIMODAL_MANIFEST:-${MARA_PHASE3_MANIFEST:-/mnt/scratch/users/tbczhang/outputs/MARA/manifests/plan5/current-direct-fix-20260621/slidevqa-test-shard0.multimodal.routes.json}}"
RUN_ID="${SLURM_JOB_ID:-manual-$(date +%Y%m%d_%H%M%S)}"
SUITE_NAME="${MARA_MULTIMODAL_SUITE_NAME:-${MARA_PHASE3_SUITE_NAME:-slidevqa-multimodal-route-slurm-${RUN_ID}}}"
LOG_ROOT="${OUT_ROOT}/logs/${RUN_ID}"
BENCHMARK_LOG="${LOG_ROOT}/benchmark.log"
BACKEND_HEALTH_JSON="${LOG_ROOT}/backend-health.json"
SEMANTIC_EVALUATOR="${MARA_SEMANTIC_EVALUATOR:-off}"
SEMANTIC_EVALUATOR_MODEL="${MARA_SEMANTIC_EVALUATOR_MODEL:-Qwen/Qwen3-8B}"
SEMANTIC_EVALUATOR_TIMEOUT_SECONDS="${MARA_SEMANTIC_EVALUATOR_TIMEOUT_SECONDS:-60}"
REQUIRE_HYBRID_ELIGIBLE="${MARA_MULTIMODAL_REQUIRE_HYBRID_ELIGIBLE:-0}"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/mnt/fastscratch/users/tbczhang/cache/uv}"
export UV_NO_CACHE="${UV_NO_CACHE:-1}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-/mnt/fastscratch/users/tbczhang/python}"
export PRE_COMMIT_HOME="${PRE_COMMIT_HOME:-/mnt/scratch/users/tbczhang/pre-commit-cache}"
export HF_HOME="${HF_HOME:-/users/tbczhang/fastscratch/cache/huggingface}"
export TIKTOKEN_CACHE_DIR="${TIKTOKEN_CACHE_DIR:-/users/tbczhang/fastscratch/cache/tiktoken}"
export CODEX_HOME="${CODEX_HOME:-/users/tbczhang/fastscratch/.codex}"
export MARA_TEXT_LLM_BASE_URL="${MARA_TEXT_LLM_BASE_URL:-http://127.0.0.1:8000/v1}"
export MARA_RETRIEVAL_BASE_URL="${MARA_RETRIEVAL_BASE_URL:-http://127.0.0.1:8002}"
export MARA_LLM_BASE_URL="${MARA_LLM_BASE_URL:-$MARA_TEXT_LLM_BASE_URL}"
export MARA_VLM_BASE_URL="${MARA_VLM_BASE_URL:-http://127.0.0.1:8001/v1}"
export MARA_VLM_API_KEY="${MARA_VLM_API_KEY:-local}"
export MARA_VLM_MODEL="${MARA_VLM_MODEL:-Qwen/Qwen3-VL-8B-Instruct}"
export MARA_VLM_MAX_MODEL_LEN="${MARA_VLM_MAX_MODEL_LEN:-8192}"
export MARA_VLM_GPU_MEMORY_UTILIZATION="${MARA_VLM_GPU_MEMORY_UTILIZATION:-0.70}"
export MARA_VLM_EVIDENCE_TEXT_CHARS="${MARA_VLM_EVIDENCE_TEXT_CHARS:-120}"
export MARA_VLM_TIMEOUT="${MARA_VLM_TIMEOUT:-120}"
export MARA_VLM_MAX_OUTPUT_TOKENS="${MARA_VLM_MAX_OUTPUT_TOKENS:-192}"
export MARA_VLM_MAX_IMAGES="${MARA_VLM_MAX_IMAGES:-1}"
export MARA_COLVISION_ENDPOINT="${MARA_COLVISION_ENDPOINT:-http://127.0.0.1:8003/visual-score}"
export MARA_COLVISION_DEVICE="${MARA_COLVISION_DEVICE:-cuda:0}"
export MARA_COLVISION_LOCAL_FILES_ONLY="${MARA_COLVISION_LOCAL_FILES_ONLY:-1}"
export MARA_RETRIEVAL_DEVICES="${MARA_RETRIEVAL_DEVICES:-cpu}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
MARA_VLM_SERVE_SCRIPT="${MARA_VLM_SERVE_SCRIPT:-serve_qwen3_vl_8b_4k.sh}"

SERVICE_PIDS=()

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*"
}

require_path() {
  local label="$1"
  local path="$2"
  shift 2
  for allowed in "$@"; do
    case "$path" in
      "$allowed"*) return 0 ;;
    esac
  done
  printf 'Refusing unsafe %s path: %s\n' "$label" "$path" >&2
  exit 2
}

http_ok() {
  local url="$1"
  curl -fsS --max-time 3 "$url" >/dev/null
}

wait_http() {
  local label="$1"
  local url="$2"
  local seconds="$3"
  local deadline=$((SECONDS + seconds))
  while ((SECONDS < deadline)); do
    if http_ok "$url"; then
      log "${label} health ok: ${url}"
      return 0
    fi
    sleep 5
  done
  log "${label} health failed after ${seconds}s: ${url}"
  return 1
}

start_service() {
  local name="$1"
  shift
  local log_file="${LOG_ROOT}/${name}.log"
  log "starting ${name}; log=${log_file}"
  "$@" >"$log_file" 2>&1 &
  SERVICE_PIDS+=("$!")
}

cleanup() {
  local pid
  for pid in "${SERVICE_PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT

require_path project "$PROJECT_ROOT" \
  "/mnt/scratch/users/tbczhang/projects/MARA" \
  "/users/tbczhang/scratch/projects/MARA"
require_path output "$OUT_ROOT" \
  "/mnt/scratch/users/tbczhang/outputs/MARA" \
  "/users/tbczhang/scratch/outputs/MARA"

source "${PROJECT_ROOT}/scripts/slurm/benchmark_runtime_isolation.sh"
mara_install_benchmark_runtime_cleanup
# normalize_semantic_evaluator.py is invoked with the fresh interpreter below.
# mara_bootstrap_benchmark_runtime performs uv sync --frozen --no-dev --extra mara
mara_configure_benchmark_runtime "$SUITE_NAME"
mara_assert_isolated_kh_app_data
require_path runtime "$KH_APP_DATA_DIR" \
  "/mnt/fastscratch/users/tbczhang/mara_runtime" \
  "/users/tbczhang/fastscratch/mara_runtime"

mkdir -p "$OUT_ROOT" "$LOG_ROOT" /mnt/scratch/users/tbczhang/outputs/MARA/slurm
cd "$PROJECT_ROOT"

GIT_COMMIT="$(git rev-parse HEAD)"
GIT_STATUS="$(git status --porcelain --untracked-files=normal)"
GIT_DIRTY=false
if [[ -n "$GIT_STATUS" ]]; then
  GIT_DIRTY=true
fi
if [[ -n "$GIT_STATUS" && "${MARA_ALLOW_DIRTY_BENCHMARK:-0}" != "1" ]]; then
  log "refusing benchmark from dirty worktree; set MARA_ALLOW_DIRTY_BENCHMARK=1 only for an explicitly non-formal development run"
  printf '%s\n' "$GIT_STATUS" >&2
  exit 2
fi
export MARA_BENCHMARK_GIT_COMMIT="$GIT_COMMIT"
mara_bootstrap_benchmark_runtime
export MARA_BENCHMARK_INDEX_CONTRACT="$(
  "$MARA_BENCHMARK_PYTHON" \
    "${PROJECT_ROOT}/scripts/slurm/benchmark_index_contract.py" \
    "$MANIFEST"
)"

log "repo=$(pwd)"
log "git_commit=${GIT_COMMIT} git_dirty=${GIT_DIRTY}"
log "index_contract=${MARA_BENCHMARK_INDEX_CONTRACT}"
log "kh_app_data_dir=${KH_APP_DATA_DIR}"
log "theflow_settings_module=${THEFLOW_SETTINGS_MODULE}"
log "theflow_settings_path=${MARA_BENCHMARK_FLOWSETTINGS_PATH}"
log "theflow_storage_prefix=${MARA_BENCHMARK_STORAGE_PREFIX}"
log "theflow_temp_path=${THEFLOW_TEMP_PATH}"
log "uv_project_environment=${UV_PROJECT_ENVIRONMENT}"
log "benchmark_python=${MARA_BENCHMARK_PYTHON}"
log "runtime_contract=${MARA_BENCHMARK_RUNTIME_CONTRACT}"
log "manifest=${MANIFEST}"
log "output=${OUT_ROOT}"
log "suite=${SUITE_NAME}"
log "node=${SLURMD_NODENAME:-$(hostname)}"
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader || true

SEMANTIC_EVALUATOR="$(
  "$MARA_BENCHMARK_PYTHON" \
    "${PROJECT_ROOT}/scripts/slurm/normalize_semantic_evaluator.py" \
    "$SEMANTIC_EVALUATOR"
)"
log "semantic_evaluator=${SEMANTIC_EVALUATOR}"

export MARA_BENCHMARK_EMBEDDING_CONTRACT="$(
  sha256sum \
    "${HPC_HOME}/serve_retrieval.sh" \
    "${HPC_HOME}/env-retrieval.sh" \
    "${HPC_HOME}/local_retrieval_server.py" \
    "${HPC_HOME}/configure_mara_local_models.py" |
    sha256sum |
    awk '{print $1}'
)"
export MARA_BENCHMARK_SERVICE_CONTRACT="$(
  sha256sum \
    "${HPC_HOME}/serve_qwen3_8b.sh" \
    "${HPC_HOME}/${MARA_VLM_SERVE_SCRIPT}" \
    "${HPC_HOME}/serve_retrieval.sh" \
    "${HPC_HOME}/serve_colvision.sh" \
    "${HPC_HOME}/configure_mara_local_models.py" |
    sha256sum |
    awk '{print $1}'
)"
log "embedding_contract=${MARA_BENCHMARK_EMBEDDING_CONTRACT}"
log "service_contract=${MARA_BENCHMARK_SERVICE_CONTRACT}"

if ! http_ok "http://127.0.0.1:8000/v1/models"; then
  start_service qwen3_8b \
    env CUDA_VISIBLE_DEVICES="${MARA_TEXT_GPU:-0}" \
    "${HPC_HOME}/serve_qwen3_8b.sh"
fi
if ! http_ok "http://127.0.0.1:8001/v1/models"; then
  start_service qwen3_vl_8b \
    env CUDA_VISIBLE_DEVICES="${MARA_VLM_GPU:-1}" \
    "${HPC_HOME}/${MARA_VLM_SERVE_SCRIPT}"
fi
if ! http_ok "http://127.0.0.1:8002/health"; then
  start_service retrieval \
    env CUDA_VISIBLE_DEVICES="${MARA_RETRIEVAL_GPU:-1}" \
    MARA_RETRIEVAL_DEVICES="${MARA_RETRIEVAL_DEVICES:-cpu}" \
    "${HPC_HOME}/serve_retrieval.sh"
fi
if ! http_ok "http://127.0.0.1:8003/health"; then
  start_service colvision \
    env CUDA_VISIBLE_DEVICES="${MARA_COLVISION_GPU:-${MARA_VLM_GPU:-1}}" \
    MARA_COLVISION_DEVICE="${MARA_COLVISION_DEVICE}" \
    "${HPC_HOME}/serve_colvision.sh"
fi

wait_http text_llm "http://127.0.0.1:8000/v1/models" 600
wait_http vlm "http://127.0.0.1:8001/v1/models" 600
wait_http retrieval "http://127.0.0.1:8002/health" 240
wait_http colvision "http://127.0.0.1:8003/health" 240

"$MARA_BENCHMARK_PYTHON" "${HPC_HOME}/configure_mara_local_models.py"

"$MARA_BENCHMARK_PYTHON" - <<'PY'
from ktem.docqa.visual_backends import visual_backend_health

print(
    "visual_backend_health=",
    visual_backend_health(
        {
            "route_policy": "visual",
            "visual_retriever_backend": "colqwen",
            "visual_generator_backend": "local_qwen3_vl",
            "generator_backend": "local_qwen3_vl",
            "requires_backend_config": True,
        }
    ),
)
PY

"$MARA_BENCHMARK_PYTHON" -m benchmark check-multimodal-backends \
  --output "$BACKEND_HEALTH_JSON" \
  --timeout-seconds "${MARA_MULTIMODAL_HEALTH_TIMEOUT_SECONDS:-3}" \
  --strict

NUM_SHARDS="${MARA_MULTIMODAL_NUM_SHARDS:-${MARA_PHASE3_NUM_SHARDS:-}}"
SHARD_INDEX="${MARA_MULTIMODAL_SHARD_INDEX:-${MARA_PHASE3_SHARD_INDEX:-}}"
SHARD_ARGS=()
if [[ -n "$NUM_SHARDS" ]]; then
  SHARD_ARGS+=(--num-shards "$NUM_SHARDS")
fi
if [[ -n "$SHARD_INDEX" ]]; then
  SHARD_ARGS+=(--shard-index "$SHARD_INDEX")
fi

ROUTE="${MARA_MULTIMODAL_ROUTE:-${MARA_PHASE3_ROUTE:-all}}"
LIMIT="${MARA_MULTIMODAL_LIMIT:-${MARA_PHASE3_LIMIT:-20}}"
SAMPLE_SEED="${MARA_MULTIMODAL_SAMPLE_SEED:-${MARA_PHASE3_SAMPLE_SEED:-0}}"
ROUTE_TIMEOUT_SECONDS="${MARA_MULTIMODAL_ROUTE_TIMEOUT_SECONDS:-${MARA_PHASE3_ROUTE_TIMEOUT_SECONDS:-240}}"
EXECUTION_CONTRACT="${MARA_EXECUTION_JOB_CONTRACT:-}"

# python -m benchmark run executes through the job-owned interpreter below.
"$MARA_BENCHMARK_PYTHON" -m benchmark run \
  --manifest "$MANIFEST" \
  --suite-name "$SUITE_NAME" \
  --route "$ROUTE" \
  --limit "$LIMIT" \
  --sample-seed "$SAMPLE_SEED" \
  "${SHARD_ARGS[@]}" \
  --output-dir "$OUT_ROOT" \
  --artifact-detail compact \
  --benchmark-prompt-policy gold_answer_v1 \
  --benchmark-prompt-profile auto \
  --benchmark-no-think \
  --semantic-evaluator "$SEMANTIC_EVALUATOR" \
  --semantic-evaluator-model "$SEMANTIC_EVALUATOR_MODEL" \
  --semantic-evaluator-timeout-seconds "$SEMANTIC_EVALUATOR_TIMEOUT_SECONDS" \
  --route-timeout-seconds "$ROUTE_TIMEOUT_SECONDS" \
  --backend-health-json "$BACKEND_HEALTH_JSON" \
  --docqa-citation-mode inline | tee "$BENCHMARK_LOG"

RUN_DIR="$(awk '/Outputs written to/ {print $NF}' "$BENCHMARK_LOG" | tail -n 1)"
if [[ -z "$RUN_DIR" || ! -f "$RUN_DIR/summary.json" || ! -f "$RUN_DIR/predictions.jsonl" ]]; then
  log "benchmark finished but summary.json was not found; run_dir=${RUN_DIR:-missing}"
  exit 1
fi

test -f "$RUN_DIR/artifact_manifest.json"
test -f "$RUN_DIR/artifact_complete.json"
if [[ -n "$EXECUTION_CONTRACT" ]]; then
  VALIDATION_ARGS=(
    --require-all-usable
    --artifact-dir "$RUN_DIR"
    --require-complete-marker
    --expected-keys-file "$EXECUTION_CONTRACT"
  )
else
  # Manual unsharded runs keep the full-manifest validator contract.
  VALIDATION_ARGS=(
    --require-all-usable
    --artifact-dir "$RUN_DIR"
    --require-complete-marker
    --manifest "$MANIFEST"
  )
fi
if [[ "$REQUIRE_HYBRID_ELIGIBLE" == "1" ]]; then
  VALIDATION_ARGS+=(--require-hybrid-eligible)
fi
"$MARA_BENCHMARK_PYTHON" \
  "${PROJECT_ROOT}/scripts/slurm/validate_benchmark_predictions.py" \
  "$RUN_DIR/predictions.jsonl" \
  "${VALIDATION_ARGS[@]}"

"$MARA_BENCHMARK_PYTHON" - "$RUN_DIR" <<'PY'
import json
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
phase3 = summary.get("phase3_multimodal_summary") or {}
print("run_dir=", run_dir)
print("num_examples=", summary.get("num_examples"))
print("num_predictions=", summary.get("num_predictions"))
print("num_skipped_routes=", summary.get("num_skipped_routes"))
print("avg_f1=", summary.get("avg_f1"))
print("avg_page_hit=", summary.get("avg_page_hit"))
print("page_image=", phase3.get("page_image"))
print("element=", phase3.get("element"))
print("hybrid=", phase3.get("hybrid"))
PY

mara_cleanup_benchmark_runtime
