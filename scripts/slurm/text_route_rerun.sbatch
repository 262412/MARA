#!/usr/bin/env bash
#SBATCH --job-name=mara-text-route
#SBATCH --partition=gpu-a100-lowbig
#SBATCH --gres=gpu:a100:2
#SBATCH --cpus-per-task=24
#SBATCH --mem=192G
#SBATCH --time=04:00:00
#SBATCH --output=/mnt/scratch/users/tbczhang/outputs/MARA/slurm/%x-%j.out
#SBATCH --error=/mnt/scratch/users/tbczhang/outputs/MARA/slurm/%x-%j.err

source ~/.bashrc
set -euo pipefail

PROJECT_ROOT="${MARA_PROJECT_ROOT:-/mnt/scratch/users/tbczhang/projects/MARA}"
HPC_HOME="${MARA_HPC_HOME:-/mnt/scratch/users/tbczhang/mara-hpc}"
RUN_ROOT="${MARA_TEXT_RUN_ROOT:-${MARA_FINAL_RUN_ROOT:-/mnt/scratch/users/tbczhang/outputs/MARA/text_route_slurm}}"
OUT_ROOT="${MARA_TEXT_OUTPUT_DIR:-${MARA_FINAL_OUTPUT_DIR:-${RUN_ROOT}/01_core_text}}"
HEALTH_ROOT="${MARA_TEXT_HEALTH_DIR:-${RUN_ROOT}/00_health}"
RUN_ID="${SLURM_JOB_ID:-manual-$(date +%Y%m%d_%H%M%S)}"
PORT_OFFSET=$((10#${SLURM_JOB_ID:-$$} % 10000))
TEXT_LLM_PORT="${MARA_TEXT_LLM_PORT:-$((20000 + PORT_OFFSET))}"
RETRIEVAL_PORT="${MARA_RETRIEVAL_PORT:-$((40000 + PORT_OFFSET))}"
TEXT_LLM_BASE_URL="http://127.0.0.1:${TEXT_LLM_PORT}/v1"
RETRIEVAL_BASE_URL="http://127.0.0.1:${RETRIEVAL_PORT}"

MANIFEST="${MARA_TEXT_MANIFEST:-${MARA_FINAL_MANIFEST:?Set MARA_TEXT_MANIFEST or MARA_FINAL_MANIFEST to a frozen manifest path}}"
NAME="${MARA_TEXT_SUITE_NAME:-${MARA_FINAL_SUITE_NAME:?Set MARA_TEXT_SUITE_NAME or MARA_FINAL_SUITE_NAME}}"
ROUTE="${MARA_TEXT_ROUTE:-${MARA_FINAL_ROUTE:-all}}"
LIMIT="${MARA_TEXT_LIMIT:-${MARA_FINAL_LIMIT:-10}}"
SAMPLE_SEED="${MARA_TEXT_SAMPLE_SEED:-${MARA_FINAL_SAMPLE_SEED:-20260615}}"
MAX_CONTEXT_LENGTH="${MARA_TEXT_MAX_CONTEXT_LENGTH:-3000}"
ROUTE_TIMEOUT_SECONDS="${MARA_TEXT_ROUTE_TIMEOUT_SECONDS:-${MARA_FINAL_ROUTE_TIMEOUT_SECONDS:-240}}"
SEMANTIC_EVALUATOR="${MARA_SEMANTIC_EVALUATOR:-off}"
SEMANTIC_EVALUATOR_MODEL="${MARA_SEMANTIC_EVALUATOR_MODEL:-Qwen/Qwen3-8B}"
SEMANTIC_EVALUATOR_TIMEOUT_SECONDS="${MARA_SEMANTIC_EVALUATOR_TIMEOUT_SECONDS:-60}"
ARTIFACT_DETAIL="${MARA_TEXT_ARTIFACT_DETAIL:-compact}"
REQUIRE_CONTRACT_SMOKE="${MARA_REQUIRE_CONTRACT_SMOKE:-0}"
CONTRACT_SMOKE_SUITE_KIND="${MARA_CONTRACT_SMOKE_SUITE_KIND:-}"
SUITE_NAME="${NAME}-${RUN_ID}"
LOG_ROOT="${OUT_ROOT}/logs/${RUN_ID}"
BENCHMARK_LOG="${LOG_ROOT}/benchmark.log"
HEALTH_JSON="${HEALTH_ROOT}/${NAME}-${RUN_ID}.json"
TOOL_CALL_SMOKE_JSON="${HEALTH_ROOT}/${NAME}-${RUN_ID}-tool-calls.json"
TOOL_CALL_SMOKE_LOG="${LOG_ROOT}/tool-call-smoke.log"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/users/tbczhang/fastscratch/cache/uv}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-/users/tbczhang/fastscratch/cache/uv/python}"
export PRE_COMMIT_HOME="${PRE_COMMIT_HOME:-/users/tbczhang/scratch/pre-commit-cache}"
export HF_HOME="${HF_HOME:-/users/tbczhang/fastscratch/cache/huggingface}"
export TIKTOKEN_CACHE_DIR="${TIKTOKEN_CACHE_DIR:-/users/tbczhang/fastscratch/cache/tiktoken}"
export CODEX_HOME="${CODEX_HOME:-/users/tbczhang/fastscratch/.codex}"
export MARA_TEXT_LLM_BASE_URL="$TEXT_LLM_BASE_URL"
export MARA_RETRIEVAL_BASE_URL="$RETRIEVAL_BASE_URL"
export MARA_LLM_BASE_URL="$TEXT_LLM_BASE_URL"

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
mara_configure_benchmark_runtime "$SUITE_NAME"
mara_assert_isolated_kh_app_data
require_path runtime "$KH_APP_DATA_DIR" \
  "/mnt/fastscratch/users/tbczhang/mara_runtime" \
  "/users/tbczhang/fastscratch/mara_runtime"

mkdir -p "$OUT_ROOT" "$LOG_ROOT" "$HEALTH_ROOT" /mnt/scratch/users/tbczhang/outputs/MARA/slurm
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
export MARA_BENCHMARK_INDEX_CONTRACT="$(
  uv run --python 3.10 python \
    "${PROJECT_ROOT}/scripts/slurm/benchmark_index_contract.py" \
    "$MANIFEST"
)"

log "repo=$(pwd)"
log "git_commit=${GIT_COMMIT} git_dirty=${GIT_DIRTY}"
log "index_contract=${MARA_BENCHMARK_INDEX_CONTRACT}"
log "run_root=${RUN_ROOT}"
log "kh_app_data_dir=${KH_APP_DATA_DIR}"
log "manifest=${MANIFEST}"
log "output=${OUT_ROOT}"
log "suite=${SUITE_NAME}"
log "route=${ROUTE} limit=${LIMIT} sample_seed=${SAMPLE_SEED} max_context=${MAX_CONTEXT_LENGTH} route_timeout=${ROUTE_TIMEOUT_SECONDS}"
log "artifact_detail=${ARTIFACT_DETAIL} require_contract_smoke=${REQUIRE_CONTRACT_SMOKE} contract_smoke_suite_kind=${CONTRACT_SMOKE_SUITE_KIND:-none}"
log "text_llm_base_url=${TEXT_LLM_BASE_URL}"
log "retrieval_base_url=${RETRIEVAL_BASE_URL}"
log "node=${SLURMD_NODENAME:-$(hostname)}"
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader || true

SEMANTIC_EVALUATOR="$(
  uv run --python 3.10 python \
    "${PROJECT_ROOT}/scripts/slurm/normalize_semantic_evaluator.py" \
    "$SEMANTIC_EVALUATOR"
)"
log "semantic_evaluator=${SEMANTIC_EVALUATOR}"

mara_bootstrap_benchmark_runtime
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
    "${HPC_HOME}/serve_retrieval.sh" \
    "${HPC_HOME}/configure_mara_local_models.py" |
    sha256sum |
    awk '{print $1}'
)"
log "embedding_contract=${MARA_BENCHMARK_EMBEDDING_CONTRACT}"
log "service_contract=${MARA_BENCHMARK_SERVICE_CONTRACT}"

if ! http_ok "${TEXT_LLM_BASE_URL}/models"; then
  start_service qwen3_8b \
    env CUDA_VISIBLE_DEVICES="${MARA_TEXT_GPU:-0}" \
    MARA_QWEN3_8B_PORT="$TEXT_LLM_PORT" \
    "${HPC_HOME}/serve_qwen3_8b.sh"
fi

if ! http_ok "${RETRIEVAL_BASE_URL}/health"; then
  start_service retrieval \
    env CUDA_VISIBLE_DEVICES="${MARA_RETRIEVAL_GPU:-1}" \
    MARA_RETRIEVAL_PORT="$RETRIEVAL_PORT" \
    MARA_RETRIEVAL_DEVICES="${MARA_RETRIEVAL_DEVICES:-cuda}" \
    "${HPC_HOME}/serve_retrieval.sh"
fi

wait_http text_llm "${TEXT_LLM_BASE_URL}/models" 600
wait_http retrieval "${RETRIEVAL_BASE_URL}/health" 240

uv run --python 3.10 python \
  "${PROJECT_ROOT}/scripts/slurm/smoke_openai_tool_calls.py" \
  --base-url "$TEXT_LLM_BASE_URL" \
  --output "$TOOL_CALL_SMOKE_JSON" |
  tee "$TOOL_CALL_SMOKE_LOG"
grep -Fx "citation_tool_call_error_count=0" "$TOOL_CALL_SMOKE_LOG"
grep -Fx "inline_structured_citation_path_executed=true" "$TOOL_CALL_SMOKE_LOG"

uv run --python 3.10 python "${HPC_HOME}/configure_mara_local_models.py"

uv run --python 3.10 python - \
  "$HEALTH_JSON" \
  "${TEXT_LLM_BASE_URL}/models" \
  "${RETRIEVAL_BASE_URL}/health" <<'PY'
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

out = Path(sys.argv[1])
text_llm_health_url = sys.argv[2]
retrieval_health_url = sys.argv[3]

def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))

payload = {
    "created_at": datetime.now(timezone.utc).isoformat(),
    "text_llm": fetch_json(text_llm_health_url),
    "retrieval": fetch_json(retrieval_health_url),
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
print(f"health_json={out}")
PY

NUM_SHARDS="${MARA_TEXT_NUM_SHARDS:-${MARA_FINAL_NUM_SHARDS:-}}"
SHARD_INDEX="${MARA_TEXT_SHARD_INDEX:-${MARA_FINAL_SHARD_INDEX:-}}"
SHARD_ARGS=()
if [[ -n "$NUM_SHARDS" ]]; then
  SHARD_ARGS+=(--num-shards "$NUM_SHARDS")
fi
if [[ -n "$SHARD_INDEX" ]]; then
  SHARD_ARGS+=(--shard-index "$SHARD_INDEX")
fi

uv run --python 3.10 python -m benchmark run \
  --manifest "$MANIFEST" \
  --suite-name "$SUITE_NAME" \
  --route "$ROUTE" \
  --limit "$LIMIT" \
  --sample-seed "$SAMPLE_SEED" \
  "${SHARD_ARGS[@]}" \
  --output-dir "$OUT_ROOT" \
  --artifact-detail "$ARTIFACT_DETAIL" \
  --benchmark-prompt-policy gold_answer_v1 \
  --benchmark-prompt-profile auto \
  --benchmark-answer-mode scoring_adapter_v1 \
  --benchmark-no-think \
  --max-context-length "$MAX_CONTEXT_LENGTH" \
  --semantic-evaluator "$SEMANTIC_EVALUATOR" \
  --semantic-evaluator-model "$SEMANTIC_EVALUATOR_MODEL" \
  --semantic-evaluator-timeout-seconds "$SEMANTIC_EVALUATOR_TIMEOUT_SECONDS" \
  --route-timeout-seconds "$ROUTE_TIMEOUT_SECONDS" \
  --docqa-citation-mode inline | tee "$BENCHMARK_LOG"

RUN_DIR="$(awk '/Outputs written to/ {print $NF}' "$BENCHMARK_LOG" | tail -n 1)"
test -n "$RUN_DIR"
test -f "$RUN_DIR/summary.json"
test -f "$RUN_DIR/route_metrics.csv"
test -f "$RUN_DIR/predictions.jsonl"
test -f "$RUN_DIR/report.md"
VALIDATION_ARGS=(--require-all-usable)
if [[ "${SUITE_NAME,,}" == *qasper* ]]; then
  VALIDATION_ARGS+=(--require-qasper-answerability)
fi
uv run --python 3.10 python \
  "${PROJECT_ROOT}/scripts/slurm/validate_benchmark_predictions.py" \
  "$RUN_DIR/predictions.jsonl" \
  "${VALIDATION_ARGS[@]}"
if [[ "$REQUIRE_CONTRACT_SMOKE" == "1" ]]; then
  if [[ -z "$CONTRACT_SMOKE_SUITE_KIND" ]]; then
    log "MARA_CONTRACT_SMOKE_SUITE_KIND is required for contract smoke validation"
    exit 2
  fi
  uv run --python 3.10 python \
    "${PROJECT_ROOT}/scripts/slurm/validate_contract_smoke.py" \
    "$RUN_DIR" \
    --suite-kind "$CONTRACT_SMOKE_SUITE_KIND"
fi

log "outputs=${RUN_DIR}"
mara_cleanup_benchmark_runtime
