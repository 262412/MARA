#!/usr/bin/env bash
#SBATCH --job-name=qasper-stage2
#SBATCH --partition=gpu-l40s-low,gpu-l40s
#SBATCH --gres=gpu:l40s:2
#SBATCH --cpus-per-task=24
#SBATCH --mem=192G
#SBATCH --time=04:00:00
#SBATCH --output=/mnt/scratch/users/tbczhang/outputs/MARA/slurm/%x-%j.out
#SBATCH --error=/mnt/scratch/users/tbczhang/outputs/MARA/slurm/%x-%j.err

source ~/.bashrc
set -euo pipefail

PROJECT_ROOT="${MARA_PROJECT_ROOT:?Set MARA_PROJECT_ROOT}"
EXPECTED_SHA="${MARA_EXPECTED_SHA:?Set MARA_EXPECTED_SHA}"
OUTPUT_ROOT="${MARA_TEXT_RUN_ROOT:?Set MARA_TEXT_RUN_ROOT}"
MANIFEST="${MARA_TEXT_MANIFEST:?Set MARA_TEXT_MANIFEST}"
SUBMISSION_SCRIPT_PATH="${MARA_SUBMISSION_SCRIPT_PATH:-$PROJECT_ROOT/scripts/slurm/qasper_natural_stage2_canary.sbatch}"
VLLM_BIN="${VLLM_BIN:-/mnt/fastscratch/users/tbczhang/envs/mara-hpc-vllm/bin/vllm}"
VLLM_ENV_BIN="${VLLM_BIN%/*}"
VLLM_PYTHON="$VLLM_ENV_BIN/python"
AUDITOR_MODEL="${MARA_QASPER_CONTRACT_AUDITOR_MODEL:-Qwen/Qwen3-VL-8B-Instruct}"
AUDITOR_PORT="${MARA_QASPER_CONTRACT_AUDITOR_PORT:-$((33000 + SLURM_JOB_ID % 10000))}"
AUDITOR_BASE_URL="http://127.0.0.1:${AUDITOR_PORT}/v1"
MARA_AUDITOR_STARTUP_ONLY="${MARA_AUDITOR_STARTUP_ONLY:-0}"
AUDITOR_PID=
AUDITOR_READY=0
AUDITOR_FAILURE_RECORDED=0
STARTUP_PHASE=source_preflight
STARTUP_FAILURE_MESSAGE=

case "$MARA_AUDITOR_STARTUP_ONLY" in
  0) export MARA_AUDITOR_RUN_MODE=natural_stage2 ;;
  1) export MARA_AUDITOR_RUN_MODE=startup_canary ;;
  *) printf 'MARA_AUDITOR_STARTUP_ONLY must be 0 or 1\n' >&2; exit 2 ;;
esac

PROJECT_ROOT="$(realpath -e "$PROJECT_ROOT")"
OUTPUT_ROOT="$(realpath -m "$OUTPUT_ROOT")"
SUBMISSION_SCRIPT_PATH="$(realpath -e "$SUBMISSION_SCRIPT_PATH")"
case "$OUTPUT_ROOT" in
  /mnt/scratch/users/tbczhang/outputs/MARA/*|/users/tbczhang/scratch/outputs/MARA/*) ;;
  *) printf 'Refusing unsafe output root: %s\n' "$OUTPUT_ROOT" >&2; exit 2 ;;
esac
[[ "$SUBMISSION_SCRIPT_PATH" == "$PROJECT_ROOT/scripts/slurm/qasper_natural_stage2_canary.sbatch" ]] || {
  printf 'submission script must use the tracked stable launcher path\n' >&2
  exit 2
}
mkdir -p "$OUTPUT_ROOT"
test -s "$MANIFEST"
cd "$PROJECT_ROOT"
[[ "$(git rev-parse HEAD)" == "$EXPECTED_SHA" ]] || {
  printf 'source SHA mismatch: expected=%s actual=%s\n' \
    "$EXPECTED_SHA" "$(git rev-parse HEAD)" >&2
  exit 2
}
[[ -z "$(git status --porcelain=v1)" ]] || {
  printf 'source checkout is dirty; refusing QASPER Natural launch\n' >&2
  exit 2
}
git ls-files --error-unmatch \
  scripts/slurm/qasper_natural_stage2_canary.sbatch >/dev/null

export MARA_PROJECT_ROOT="$PROJECT_ROOT"
export MARA_EXPECTED_SHA="$EXPECTED_SHA"
export MARA_TEXT_RUN_ROOT="$OUTPUT_ROOT"
export MARA_TEXT_MANIFEST="$MANIFEST"
export MARA_SUBMISSION_SCRIPT_PATH="$SUBMISSION_SCRIPT_PATH"
export MARA_QASPER_CONTRACT_AUDITOR_MODEL="$AUDITOR_MODEL"
export MARA_QASPER_CONTRACT_AUDITOR_BASE_URL="$AUDITOR_BASE_URL"
export VLLM_BIN VLLM_ENV_BIN VLLM_PYTHON

source "$PROJECT_ROOT/scripts/slurm/qasper_vllm_runtime_contract.sh"
mara_configure_qasper_vllm_runtime

SCRIPT_IDENTITY="$OUTPUT_ROOT/submission_script_identity.json"
SCRIPT_CHECKSUM="$OUTPUT_ROOT/submission_script.sha256"
STARTUP_TRANSACTION="$OUTPUT_ROOT/auditor_startup_transaction.json"
AUDITOR_MODELS="$OUTPUT_ROOT/auditor_models.json"
AUDITOR_LOG="$OUTPUT_ROOT/auditor_provider.log"
TRANSACTION_WRITER="$PROJECT_ROOT/scripts/slurm/qasper_auditor_startup_transaction.py"

"$VLLM_PYTHON" "$TRANSACTION_WRITER" script-identity \
  --script "$SUBMISSION_SCRIPT_PATH" \
  --project-root "$PROJECT_ROOT" \
  --source-sha "$EXPECTED_SHA" \
  --output "$SCRIPT_IDENTITY" \
  --checksum-output "$SCRIPT_CHECKSUM"
sha256sum --check "$SCRIPT_CHECKSUM"

record_startup_event() {
  local status="$1"
  local phase="$2"
  shift 2
  "$VLLM_PYTHON" "$TRANSACTION_WRITER" record \
    --output "$STARTUP_TRANSACTION" \
    --script-identity "$SCRIPT_IDENTITY" \
    --status "$status" \
    --phase "$phase" \
    "$@"
}

cleanup() {
  local status="$?"
  trap - EXIT
  if (( status != 0 && AUDITOR_READY == 0 && AUDITOR_FAILURE_RECORDED == 0 )); then
    record_startup_event failed "$STARTUP_PHASE" \
      --failed-before-transport \
      --exit-code "$status" \
      --failure-message "${STARTUP_FAILURE_MESSAGE:-auditor startup failed during $STARTUP_PHASE}" || true
  fi
  if [[ -n "$AUDITOR_PID" ]]; then
    kill "$AUDITOR_PID" 2>/dev/null || true
    wait "$AUDITOR_PID" 2>/dev/null || true
  fi
  exit "$status"
}
trap cleanup EXIT

wait_for_auditor() {
  local pid="$1"
  local deadline=$((SECONDS + 600))
  while ((SECONDS < deadline)); do
    if curl --silent --show-error --fail --max-time 3 \
      "$AUDITOR_BASE_URL/models" >/dev/null 2>&1; then
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      STARTUP_FAILURE_MESSAGE="auditor provider exited before health check"
      tail -n 200 "$AUDITOR_LOG" >&2 || true
      return 1
    fi
    sleep 5
  done
  STARTUP_FAILURE_MESSAGE="auditor provider health check timed out"
  tail -n 200 "$AUDITOR_LOG" >&2 || true
  return 1
}

record_startup_event starting source_preflight
STARTUP_PHASE=cuda_and_provider_toolchain_preflight
record_startup_event starting "$STARTUP_PHASE"
mara_preflight_qasper_vllm_runtime "$OUTPUT_ROOT"

STARTUP_PHASE=auditor_startup
record_startup_event starting auditor_startup
env CUDA_VISIBLE_DEVICES=0 "$VLLM_BIN" serve "$AUDITOR_MODEL" \
  --served-model-name "$AUDITOR_MODEL" \
  --host 127.0.0.1 \
  --port "$AUDITOR_PORT" \
  --dtype auto \
  --max-model-len 4096 \
  --max-num-seqs 1 \
  --gpu-memory-utilization 0.45 \
  --enforce-eager \
  --limit-mm-per-prompt '{"image": 1}' \
  > "$AUDITOR_LOG" 2>&1 &
AUDITOR_PID=$!
if wait_for_auditor "$AUDITOR_PID"; then
  :
else
  wait_status=$?
  record_startup_event failed auditor_startup \
    --failed-before-transport \
    --exit-code "$wait_status" \
    --failure-message "$STARTUP_FAILURE_MESSAGE"
  AUDITOR_FAILURE_RECORDED=1
  exit "$wait_status"
fi
curl --silent --show-error --fail "$AUDITOR_BASE_URL/models" > "$AUDITOR_MODELS"
record_startup_event ready auditor_startup --models-artifact "$AUDITOR_MODELS"
AUDITOR_READY=1

if [[ "$MARA_AUDITOR_STARTUP_ONLY" == "1" ]]; then
  printf 'auditor_startup_canary=passed\n'
  exit 0
fi

export MARA_HPC_HOME="${MARA_HPC_HOME:-/mnt/scratch/users/tbczhang/mara-hpc}"
export MARA_TEXT_OUTPUT_DIR="$OUTPUT_ROOT/online"
export MARA_TEXT_HEALTH_DIR="$OUTPUT_ROOT/health"
export MARA_TEXT_SUITE_NAME="${MARA_TEXT_SUITE_NAME:-qasper-stage2-${EXPECTED_SHA:0:7}}"
export MARA_TEXT_ROUTE=text_rag
export MARA_TEXT_LIMIT=6
export MARA_TEXT_SAMPLE_SEED=20260615
export MARA_TEXT_MAX_CONTEXT_LENGTH=3000
export MARA_TEXT_ROUTE_TIMEOUT_SECONDS=240
export MARA_TEXT_ARTIFACT_DETAIL=full
export MARA_SEMANTIC_EVALUATOR=off
export MARA_REQUIRE_CONTRACT_SMOKE=0
export MARA_REQUIRE_SEMANTIC_DEBUG_TRACE=1
export MARA_SEMANTIC_PROPOSITION_DEBUG_TRACE=1
export MARA_QASPER_RETRIEVAL_INDEX_MODE=produce
export MARA_QASPER_RETRIEVAL_INDEX_ARTIFACT="$OUTPUT_ROOT/retrieval_index_artifact.json"
export MARA_QASPER_RETRIEVAL_INDEX_SNAPSHOT="$OUTPUT_ROOT/retrieval_index_snapshot"
export MARA_QASPER_NATURAL_PROBE_OUTPUT_DIR="$OUTPUT_ROOT/natural_probe"
export MARA_BENCHMARK_RUNTIME_ROOT="${MARA_BENCHMARK_RUNTIME_ROOT:-/mnt/fastscratch/users/tbczhang/mara_runtime/benchmark_qasper_stage2_${EXPECTED_SHA:0:12}}"
export MARA_QWEN3_8B_GPU_MEMORY_UTILIZATION=0.44
export MARA_TEXT_GPU=1
export MARA_RETRIEVAL_GPU=1
export MARA_RETRIEVAL_DEVICES=cuda

bash "$PROJECT_ROOT/scripts/slurm/text_route_rerun.sbatch"
