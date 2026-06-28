#!/usr/bin/env bash
#SBATCH --job-name=mara-p3-mm
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
HPC_HOME="${MARA_HPC_HOME:-/mnt/scratch/users/tbczhang/mara-hpc}"
OUT_ROOT="${MARA_PHASE3_OUTPUT_DIR:-/mnt/scratch/users/tbczhang/outputs/MARA/phase3_multimodal_slurm}"
MANIFEST="${MARA_PHASE3_MANIFEST:-/mnt/scratch/users/tbczhang/outputs/MARA/manifests/plan5/current-direct-fix-20260621/slidevqa-test-shard0.multimodal.routes.json}"
RUN_ID="${SLURM_JOB_ID:-manual-$(date +%Y%m%d_%H%M%S)}"
SUITE_NAME="${MARA_PHASE3_SUITE_NAME:-phase3-slidevqa-multimodal-slurm-${RUN_ID}}"
LOG_ROOT="${OUT_ROOT}/logs/${RUN_ID}"
BENCHMARK_LOG="${LOG_ROOT}/benchmark.log"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/users/tbczhang/fastscratch/cache/uv}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-/users/tbczhang/fastscratch/cache/uv/python}"
export PRE_COMMIT_HOME="${PRE_COMMIT_HOME:-/users/tbczhang/scratch/pre-commit-cache}"
export HF_HOME="${HF_HOME:-/users/tbczhang/fastscratch/cache/huggingface}"
export TIKTOKEN_CACHE_DIR="${TIKTOKEN_CACHE_DIR:-/users/tbczhang/fastscratch/cache/tiktoken}"
export CODEX_HOME="${CODEX_HOME:-/users/tbczhang/fastscratch/.codex}"
export KH_APP_DATA_DIR="${KH_APP_DATA_DIR:-/users/tbczhang/fastscratch/mara_runtime/ktem_app_data}"
export MARA_VLM_BASE_URL="${MARA_VLM_BASE_URL:-http://127.0.0.1:8001/v1}"
export MARA_VLM_API_KEY="${MARA_VLM_API_KEY:-local}"
export MARA_VLM_MODEL="${MARA_VLM_MODEL:-Qwen/Qwen3-VL-8B-Instruct}"
export MARA_COLVISION_ENDPOINT="${MARA_COLVISION_ENDPOINT:-http://127.0.0.1:8003/visual-score}"
export MARA_COLVISION_DEVICE="${MARA_COLVISION_DEVICE:-cpu}"
export MARA_COLVISION_LOCAL_FILES_ONLY="${MARA_COLVISION_LOCAL_FILES_ONLY:-1}"
export MARA_RETRIEVAL_DEVICES="${MARA_RETRIEVAL_DEVICES:-cpu}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"

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

mkdir -p "$OUT_ROOT" "$LOG_ROOT" /mnt/scratch/users/tbczhang/outputs/MARA/slurm
cd "$PROJECT_ROOT"

log "repo=$(pwd)"
log "manifest=${MANIFEST}"
log "output=${OUT_ROOT}"
log "suite=${SUITE_NAME}"
log "node=${SLURMD_NODENAME:-$(hostname)}"
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader || true

if ! http_ok "http://127.0.0.1:8000/v1/models"; then
  start_service qwen3_8b \
    env CUDA_VISIBLE_DEVICES="${MARA_TEXT_GPU:-0}" \
    "${HPC_HOME}/serve_qwen3_8b.sh"
fi
if ! http_ok "http://127.0.0.1:8001/v1/models"; then
  start_service qwen3_vl_8b \
    env CUDA_VISIBLE_DEVICES="${MARA_VLM_GPU:-1}" \
    "${HPC_HOME}/serve_qwen3_vl_8b.sh"
fi
if ! http_ok "http://127.0.0.1:8002/health"; then
  start_service retrieval \
    env CUDA_VISIBLE_DEVICES="${MARA_RETRIEVAL_GPU:-1}" \
    MARA_RETRIEVAL_DEVICES="${MARA_RETRIEVAL_DEVICES:-cpu}" \
    "${HPC_HOME}/serve_retrieval.sh"
fi
if ! http_ok "http://127.0.0.1:8003/health"; then
  start_service colvision \
    env MARA_COLVISION_DEVICE="${MARA_COLVISION_DEVICE:-cpu}" \
    "${HPC_HOME}/serve_colvision.sh"
fi

wait_http text_llm "http://127.0.0.1:8000/v1/models" 600
wait_http vlm "http://127.0.0.1:8001/v1/models" 600
wait_http retrieval "http://127.0.0.1:8002/health" 240
wait_http colvision "http://127.0.0.1:8003/health" 240

uv run --python 3.10 python - <<'PY'
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

SHARD_ARGS=()
if [[ -n "${MARA_PHASE3_NUM_SHARDS:-}" ]]; then
  SHARD_ARGS+=(--num-shards "${MARA_PHASE3_NUM_SHARDS}")
fi
if [[ -n "${MARA_PHASE3_SHARD_INDEX:-}" ]]; then
  SHARD_ARGS+=(--shard-index "${MARA_PHASE3_SHARD_INDEX}")
fi

uv run --python 3.10 python -m benchmark run \
  --manifest "$MANIFEST" \
  --suite-name "$SUITE_NAME" \
  --route "${MARA_PHASE3_ROUTE:-all}" \
  --limit "${MARA_PHASE3_LIMIT:-20}" \
  --sample-seed "${MARA_PHASE3_SAMPLE_SEED:-0}" \
  "${SHARD_ARGS[@]}" \
  --output-dir "$OUT_ROOT" \
  --artifact-detail compact \
  --benchmark-prompt-policy gold_answer_v1 \
  --benchmark-prompt-profile auto \
  --benchmark-no-think \
  --route-timeout-seconds "${MARA_PHASE3_ROUTE_TIMEOUT_SECONDS:-180}" \
  --docqa-citation-mode inline | tee "$BENCHMARK_LOG"

RUN_DIR="$(awk '/Outputs written to/ {print $NF}' "$BENCHMARK_LOG" | tail -n 1)"
if [[ -z "$RUN_DIR" || ! -f "$RUN_DIR/summary.json" ]]; then
  log "benchmark finished but summary.json was not found; run_dir=${RUN_DIR:-missing}"
  exit 1
fi

uv run --python 3.10 python - "$RUN_DIR" <<'PY'
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
