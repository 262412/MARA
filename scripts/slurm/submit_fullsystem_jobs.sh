#!/usr/bin/env bash

set -euo pipefail

RUN_ROOT="${MARA_FULLSYSTEM_RUN_ROOT:?Set MARA_FULLSYSTEM_RUN_ROOT to a new run output directory}"
PROJECT_ROOT="${MARA_FULLSYSTEM_PROJECT_ROOT:?Set MARA_FULLSYSTEM_PROJECT_ROOT to the frozen benchmark worktree}"
EXPECTED_SHA="${MARA_FULLSYSTEM_EXPECTED_SHA:-$(git -C "$PROJECT_ROOT" rev-parse HEAD)}"
MANIFEST_DIR="${MARA_FULLSYSTEM_MANIFEST_DIR:-${RUN_ROOT}/manifests}"
SEED="${MARA_FULLSYSTEM_SAMPLE_SEED:-20260615}"
WAVE_SIZE="${MARA_FULLSYSTEM_WAVE_SIZE:-2}"
MIN_FREE_INODES="${MARA_FULLSYSTEM_MIN_FREE_INODES:-50000}"
# Measured producer peaks reached 91,304 inodes/job; keep a 92,000 reserve.
INODES_PER_JOB_RESERVE="${MARA_FULLSYSTEM_INODES_PER_JOB_RESERVE:-92000}"
TEXT_PARTITION="${MARA_FULLSYSTEM_TEXT_PARTITION:-gpu-a-lowsmall}"
TEXT_GRES="${MARA_FULLSYSTEM_TEXT_GRES:-gpu:a100:2}"
MULTIMODAL_PARTITION="${MARA_FULLSYSTEM_MULTIMODAL_PARTITION:-gpu-l40s-low}"
MULTIMODAL_GRES="${MARA_FULLSYSTEM_MULTIMODAL_GRES:-gpu:l40s:2}"
PLAN_PYTHON="${MARA_PLAN_PYTHON:-python3}"
PLAN_DIR="${RUN_ROOT}/09_synthesis"
PLAN_PATH="${PLAN_DIR}/benchmark_execution_plan.json"
JOB_TABLE="${PLAN_DIR}/slurm_submission_jobs.tsv"
PLAN_BUILDER="${PROJECT_ROOT}/scripts/slurm/build_benchmark_execution_plan.py"
BARRIER_SCRIPT="${PROJECT_ROOT}/scripts/slurm/benchmark_cleanup_barrier.sbatch"
SYNTHESIS_SCRIPT="${PROJECT_ROOT}/scripts/slurm/synthesize_benchmark_run.sbatch"
PDF_PATH="${MARA_FULLSYSTEM_PDF_PATH:-/mnt/scratch/users/tbczhang/datasets/MARA/mmdocrag/doc_pdfs/P18-1125.pdf}"

if [[ ! "$WAVE_SIZE" =~ ^[1-9][0-9]*$ ]]; then
  echo "MARA_FULLSYSTEM_WAVE_SIZE must be a positive integer" >&2
  exit 2
fi
if [[ ! "$MIN_FREE_INODES" =~ ^[0-9]+$ ]]; then
  echo "MARA_FULLSYSTEM_MIN_FREE_INODES must be a non-negative integer" >&2
  exit 2
fi
if [[ ! "$INODES_PER_JOB_RESERVE" =~ ^[1-9][0-9]*$ ]]; then
  echo "MARA_FULLSYSTEM_INODES_PER_JOB_RESERVE must be a positive integer" >&2
  exit 2
fi
if [[ "$(git -C "$PROJECT_ROOT" rev-parse HEAD)" != "$EXPECTED_SHA" ]]; then
  echo "Refusing submission: frozen worktree SHA changed." >&2
  exit 2
fi
if [[ -n "$(git -C "$PROJECT_ROOT" status --porcelain=v1 --untracked-files=normal)" ]]; then
  echo "Refusing submission: frozen worktree is dirty." >&2
  exit 2
fi
if [[ -e "$PLAN_PATH" || -e "$JOB_TABLE" ]]; then
  echo "Refusing submission: execution plan already exists: $PLAN_PATH" >&2
  exit 2
fi

check_sha256() {
  local expected="$1"
  local path="$2"
  local actual
  actual="$(sha256sum "$path" | awk '{print $1}')"
  if [[ "$actual" != "$expected" ]]; then
    echo "Refusing submission: checksum mismatch for $path" >&2
    exit 2
  fi
}

check_inode_quota() {
  local wave_job_count="${1:-$WAVE_SIZE}"
  if [[ ! "$wave_job_count" =~ ^[1-9][0-9]*$ ]]; then
    echo "MARA_FULLSYSTEM wave job count must be a positive integer" >&2
    exit 2
  fi
  local quota_line used_inodes soft_limit
  quota_line="$(lfs quota -u "$(id -un)" /mnt/fastscratch | awk '
    previous == "/mnt/fastscratch" {
      count = 0
      for (field_index = 1; field_index <= NF; field_index++) {
        if ($field_index ~ /^[0-9]+$/) {
          numbers[++count] = $field_index
        }
      }
      if (count >= 5) {
        print numbers[4], numbers[5]
      }
    }
    {previous = $1}
  ')"
  read -r used_inodes soft_limit <<<"$quota_line"
  if [[ ! "$used_inodes" =~ ^[0-9]+$ || ! "$soft_limit" =~ ^[0-9]+$ ]]; then
    echo "Refusing submission: unable to parse fastscratch inode quota." >&2
    exit 2
  fi
  local projected_peak=$((used_inodes + wave_job_count * INODES_PER_JOB_RESERVE))
  if ((projected_peak + MIN_FREE_INODES >= soft_limit)); then
    echo "Refusing submission: projected wave inode usage exceeds configured reserve; used=${used_inodes} projected_peak=${projected_peak} soft_limit=${soft_limit} wave_size=${wave_job_count} per_job_reserve=${INODES_PER_JOB_RESERVE} reserve=${MIN_FREE_INODES}" >&2
    exit 2
  fi
  printf 'inode_preflight=ok used=%s projected_peak=%s soft_limit=%s wave_size=%s per_job_reserve=%s reserve=%s\n' \
    "$used_inodes" "$projected_peak" "$soft_limit" "$wave_job_count" "$INODES_PER_JOB_RESERVE" "$MIN_FREE_INODES"
}

check_partitions() {
  if ! sinfo -h -p "$TEXT_PARTITION" >/dev/null 2>&1; then
    echo "Refusing submission: text partition is unavailable: $TEXT_PARTITION" >&2
    exit 2
  fi
  if ! sinfo -h -p "$MULTIMODAL_PARTITION" >/dev/null 2>&1; then
    echo "Refusing submission: multimodal partition is unavailable: $MULTIMODAL_PARTITION" >&2
    exit 2
  fi
  printf 'partition_preflight=text:%s gres:%s multimodal:%s gres:%s\n' \
    "$TEXT_PARTITION" "$TEXT_GRES" "$MULTIMODAL_PARTITION" "$MULTIMODAL_GRES"
}

check_partitions
check_sha256 d97c07b630800b9f0f67d25ad149fece14f5cbf41105712a4fdaa20ddde9c597 "${MANIFEST_DIR}/alce-asqa-stat200.routes.json"
check_sha256 3f894c95a58a0ca1e2f22968dd044e6d6c80cf726be98903cf87d3c0471efe2c "${MANIFEST_DIR}/financebench-stat150.routes.json"
check_sha256 b880f78b55fcf55388261ebbb32df18e6c9a785a9d4f40d5d95d6b115a0b0a45 "${MANIFEST_DIR}/mmdocrag-dev15-stat120-controller-t360.routes.json"
check_sha256 00adca473f2fe3900227154778d7f68f4e83a335c985ff63a8ef4fb99f846f02 "${MANIFEST_DIR}/mmdocrag-dev15-stat120.routes.json"
check_sha256 3a2b23f1d3cd7d3ec34cdec7f2a50a798ff3f220907394af35a24b5c4ca5d85a "${MANIFEST_DIR}/qasper-dev-stat200.routes.json"
check_sha256 98fcf8fbc6f637ba5c5388a87aaac2ff20f33b7c4214f749de2f2187f48aaac3 "${MANIFEST_DIR}/ragtruth-stat300.routes.json"
check_sha256 9afb4fbeff44c180f0ecc66261942384f7fc0502b2c4fdf647715ad04708f4f8 "${MANIFEST_DIR}/slidevqa-test-stat120.routes.json"
check_sha256 3ba4d053607b39409b66b70d9827dc49b3da1eb4b59b56948c8f12399cace272 "$PDF_PATH"

mkdir -p "$RUN_ROOT/00_health" "$RUN_ROOT/01_core_text" \
  "$RUN_ROOT/05_page_image_vlm" "$PLAN_DIR" "$RUN_ROOT/slurm"

JOB_SPECS=()

add_text_matrix() {
  local dataset="$1" manifest="$2" num_shards="$3" limit="$4" timeout="$5"
  local shard suite
  for ((shard = 0; shard < num_shards; shard++)); do
    suite="full-${EXPECTED_SHA:0:7}-${dataset}-all-n${limit}-shard$(printf '%02d' "$shard")of${num_shards}"
    JOB_SPECS+=("text,${dataset},all,${shard},${num_shards},${limit},${timeout},${suite},${manifest},${RUN_ROOT}/01_core_text")
  done
}

add_multimodal_matrix() {
  local dataset="$1" manifest="$2" route_csv="$3" num_shards="$4" limit="$5" timeout="$6"
  local route shard suite
  IFS=',' read -r -a routes <<<"$route_csv"
  for route in "${routes[@]}"; do
    for ((shard = 0; shard < num_shards; shard++)); do
      suite="full-${EXPECTED_SHA:0:7}-${dataset}-${route//_/-}-n${limit}-shard$(printf '%02d' "$shard")of${num_shards}"
      JOB_SPECS+=("multimodal,${dataset},${route},${shard},${num_shards},${limit},${timeout},${suite},${manifest},${RUN_ROOT}/05_page_image_vlm")
    done
  done
}

add_text_matrix financebench "${MANIFEST_DIR}/financebench-stat150.routes.json" 3 50 180
add_text_matrix qasper "${MANIFEST_DIR}/qasper-dev-stat200.routes.json" 4 50 180
add_text_matrix ragtruth "${MANIFEST_DIR}/ragtruth-stat300.routes.json" 6 50 180
add_text_matrix alce_asqa "${MANIFEST_DIR}/alce-asqa-stat200.routes.json" 4 50 180
add_multimodal_matrix slidevqa "${MANIFEST_DIR}/slidevqa-test-stat120.routes.json" all 4 30 360
add_multimodal_matrix mmdocrag "${MANIFEST_DIR}/mmdocrag-dev15-stat120.routes.json" text_rag,element_rag 4 30 360
add_multimodal_matrix mmdocrag "${MANIFEST_DIR}/mmdocrag-dev15-stat120-controller-t360.routes.json" controller_auto 4 30 360
add_multimodal_matrix mmdocrag "${MANIFEST_DIR}/mmdocrag-dev15-stat120.routes.json" page_image_rag_vlm,hybrid_rag 4 30 600

PLAN_JOB_ARGS=()
for spec in "${JOB_SPECS[@]}"; do
  PLAN_JOB_ARGS+=(--job "$spec")
done
"$PLAN_PYTHON" "$PLAN_BUILDER" build \
  --output-plan "$PLAN_PATH" \
  --output-table "$JOB_TABLE" \
  --source-sha "$EXPECTED_SHA" \
  --sample-seed "$SEED" \
  "${PLAN_JOB_ARGS[@]}"

RUNTIME_ROOT="/mnt/fastscratch/users/tbczhang/mara_runtime/benchmark_${RUN_ROOT##*/}"
RECEIPT_ROOT="${PLAN_DIR}/runtime_receipts"
PREVIOUS_BARRIER=""
WAVE_INDEX=0
WAVE_JOB_IDS=()
WAVE_RUNTIME_DIRS=()
WAVE_RUNTIME_RECEIPTS=()
WAVE_DEPENDENCY=""
BARRIER_TABLE="${PLAN_DIR}/wave_barriers.tsv"
mkdir -p "$RECEIPT_ROOT"
printf 'wave_index\tbarrier_job_id\tdependency\truntime_list\truntime_receipt_list\n' >"$BARRIER_TABLE"

runtime_dir_for_job() {
  local kind="$1"
  local suite="$2"
  local job_id="$3"
  local runtime_suite="$suite"

  # text_route_rerun.sbatch appends -${SLURM_JOB_ID} to NAME before the
  # runtime isolation helper adds /job${SLURM_JOB_ID}.
  if [[ "$kind" == "text" ]]; then
    runtime_suite="${suite}-${job_id}"
  fi
  printf '%s/%s/job%s\n' "$RUNTIME_ROOT" "$runtime_suite" "$job_id"
}

runtime_receipt_for_job() {
  local job_id="$1"
  printf '%s/%s.receipt\n' "$RECEIPT_ROOT" "$job_id"
}

submit_wave_barrier() {
  if ((${#WAVE_JOB_IDS[@]} == 0)); then
    return 0
  fi
  local next_wave_job_count="${1:-0}"
  if [[ ! "$next_wave_job_count" =~ ^[0-9]+$ ]]; then
    echo "MARA_FULLSYSTEM next wave job count must be a non-negative integer" >&2
    exit 2
  fi
  local runtime_list="${PLAN_DIR}/wave_${WAVE_INDEX}_runtime_dirs.txt"
  local runtime_receipt_list="${PLAN_DIR}/wave_${WAVE_INDEX}_runtime_receipts.txt"
  local dependency="afterany:$(IFS=:; echo "${WAVE_JOB_IDS[*]}")"
  printf '%s\n' "${WAVE_RUNTIME_DIRS[@]}" >"$runtime_list"
  printf '%s\n' "${WAVE_RUNTIME_RECEIPTS[@]}" >"$runtime_receipt_list"
  local barrier_id
  barrier_id="$(sbatch --parsable \
    --dependency="$dependency" \
    --output="${RUN_ROOT}/slurm/cleanup-barrier-wave${WAVE_INDEX}-%j.out" \
    --error="${RUN_ROOT}/slurm/cleanup-barrier-wave${WAVE_INDEX}-%j.err" \
    --export="ALL,MARA_RUNTIME_DIR_LIST=${runtime_list},MARA_RUNTIME_RECEIPT_LIST=${runtime_receipt_list},MARA_NEXT_WAVE_JOB_COUNT=${next_wave_job_count},MARA_FULLSYSTEM_INODES_PER_JOB_RESERVE=${INODES_PER_JOB_RESERVE},MARA_FULLSYSTEM_MIN_FREE_INODES=${MIN_FREE_INODES}" \
    "$BARRIER_SCRIPT")"
  barrier_id="${barrier_id%%;*}"
  printf '%s\t%s\t%s\t%s\t%s\n' "$WAVE_INDEX" "$barrier_id" "$dependency" "$runtime_list" "$runtime_receipt_list" >>"$BARRIER_TABLE"
  PREVIOUS_BARRIER="$barrier_id"
  WAVE_JOB_IDS=()
  WAVE_RUNTIME_DIRS=()
  WAVE_RUNTIME_RECEIPTS=()
  WAVE_INDEX=$((WAVE_INDEX + 1))
}

submit_job() {
  local spec="$1"
  local kind dataset route shard num_shards limit timeout suite manifest output_root
  IFS=',' read -r kind dataset route shard num_shards limit timeout suite manifest output_root <<<"$spec"
  local partition gres dependency_args=""
  if [[ "$kind" == "text" ]]; then
    partition="$TEXT_PARTITION"
    gres="$TEXT_GRES"
  else
    partition="$MULTIMODAL_PARTITION"
    gres="$MULTIMODAL_GRES"
  fi
  if [[ -n "$PREVIOUS_BARRIER" ]]; then
    dependency_args="--dependency=afterok:${PREVIOUS_BARRIER}"
  fi
  local contract_path="${PLAN_DIR}/job_contracts/${suite}.json"
  local semantic_trace_exports=""
  if [[ "$dataset" == "qasper" ]]; then
    semantic_trace_exports=",MARA_SEMANTIC_PROPOSITION_DEBUG_TRACE=1,MARA_REQUIRE_SEMANTIC_DEBUG_TRACE=1"
  fi
  local job_id
  if [[ "$kind" == "text" ]]; then
    job_id="$(sbatch --parsable $dependency_args \
      --job-name="$suite" \
      --partition="$partition" --gres="$gres" \
      --output="${RUN_ROOT}/slurm/%x-%j.out" \
      --error="${RUN_ROOT}/slurm/%x-%j.err" \
      --export="ALL,MARA_PROJECT_ROOT=${PROJECT_ROOT},MARA_HPC_HOME=/mnt/scratch/users/tbczhang/mara-hpc,MARA_TEXT_RUN_ROOT=${RUN_ROOT},MARA_TEXT_OUTPUT_DIR=${output_root},MARA_TEXT_HEALTH_DIR=${RUN_ROOT}/00_health,MARA_TEXT_MANIFEST=${manifest},MARA_TEXT_ROUTE=${route},MARA_TEXT_LIMIT=${limit},MARA_TEXT_SAMPLE_SEED=${SEED},MARA_TEXT_MAX_CONTEXT_LENGTH=3000,MARA_TEXT_ROUTE_TIMEOUT_SECONDS=${timeout},MARA_TEXT_ARTIFACT_DETAIL=compact${semantic_trace_exports},MARA_REQUIRE_CONTRACT_SMOKE=0,MARA_SEMANTIC_EVALUATOR=off,MARA_TEXT_SUITE_NAME=${suite},MARA_TEXT_NUM_SHARDS=${num_shards},MARA_TEXT_SHARD_INDEX=${shard},MARA_EXECUTION_PLAN=${PLAN_PATH},MARA_EXECUTION_TABLE=${JOB_TABLE},MARA_EXECUTION_JOB_CONTRACT=${contract_path},MARA_EXECUTION_JOB_KEY=${suite},MARA_BENCHMARK_RUNTIME_ROOT=${RUNTIME_ROOT},MARA_BENCHMARK_RUNTIME_RECEIPT_DIR=${RECEIPT_ROOT},MARA_TEXT_GPU=0,MARA_RETRIEVAL_GPU=1,MARA_RETRIEVAL_DEVICES=cuda,UV_NO_CACHE=1" \
      "${PROJECT_ROOT}/scripts/slurm/text_route_rerun.sbatch")"
  else
    job_id="$(sbatch --parsable $dependency_args \
      --job-name="$suite" \
      --partition="$partition" --gres="$gres" \
      --output="${RUN_ROOT}/slurm/%x-%j.out" \
      --error="${RUN_ROOT}/slurm/%x-%j.err" \
      --export="ALL,MARA_PROJECT_ROOT=${PROJECT_ROOT},MARA_HPC_HOME=/mnt/scratch/users/tbczhang/mara-hpc,MARA_BENCHMARK_RUNTIME_ROOT=${RUNTIME_ROOT},MARA_BENCHMARK_RUNTIME_RECEIPT_DIR=${RECEIPT_ROOT},MARA_MULTIMODAL_OUTPUT_DIR=${output_root},MARA_MULTIMODAL_MANIFEST=${manifest},MARA_MULTIMODAL_ROUTE=${route},MARA_MULTIMODAL_LIMIT=${limit},MARA_MULTIMODAL_SAMPLE_SEED=${SEED},MARA_MULTIMODAL_ROUTE_TIMEOUT_SECONDS=${timeout},MARA_MULTIMODAL_SUITE_NAME=${suite},MARA_MULTIMODAL_NUM_SHARDS=${num_shards},MARA_MULTIMODAL_SHARD_INDEX=${shard},MARA_EXECUTION_PLAN=${PLAN_PATH},MARA_EXECUTION_TABLE=${JOB_TABLE},MARA_EXECUTION_JOB_CONTRACT=${contract_path},MARA_EXECUTION_JOB_KEY=${suite},MARA_RETRIEVAL_DEVICES=cuda,MARA_VLM_SERVE_SCRIPT=serve_qwen3_vl_8b_4k.sh,MARA_VLM_MAX_MODEL_LEN=8192,MARA_VLM_GPU_MEMORY_UTILIZATION=0.70,MARA_VLM_MAX_IMAGES=1,MARA_VLM_MAX_OUTPUT_TOKENS=96,MARA_VLM_TIMEOUT=180,MARA_VLM_EVIDENCE_TEXT_CHARS=120,MARA_PAGE_IMAGE_RANK_CANDIDATE_LIMIT=48,MARA_COLVISION_DEVICE=cuda:0,MARA_COLVISION_LOCAL_FILES_ONLY=1,UV_NO_CACHE=1" \
      "${PROJECT_ROOT}/scripts/slurm/multimodal_route_rerun.sbatch")"
  fi
  job_id="${job_id%%;*}"
  "$PLAN_PYTHON" "$PLAN_BUILDER" record-submission \
    --plan "$PLAN_PATH" --table "$JOB_TABLE" --job-key "$suite" \
    --job-id "$job_id" --wave-index "$WAVE_INDEX" --dependency "${dependency_args#--dependency=}"
  local runtime_dir
  runtime_dir="$(runtime_dir_for_job "$kind" "$suite" "$job_id")"
  local runtime_receipt
  runtime_receipt="$(runtime_receipt_for_job "$job_id")"
  WAVE_JOB_IDS+=("$job_id")
  WAVE_RUNTIME_DIRS+=("$runtime_dir")
  WAVE_RUNTIME_RECEIPTS+=("$runtime_receipt")
  echo "submitted ${suite}: ${job_id} wave=${WAVE_INDEX}"
  if ((${#WAVE_JOB_IDS[@]} >= WAVE_SIZE)); then
    submit_wave_barrier "$NEXT_WAVE_SIZE"
  fi
}

for ((job_index = 0; job_index < ${#JOB_SPECS[@]}; job_index++)); do
  if ((job_index % WAVE_SIZE == 0)); then
    remaining_jobs=$((${#JOB_SPECS[@]} - job_index))
    CURRENT_WAVE_SIZE="$WAVE_SIZE"
    if ((CURRENT_WAVE_SIZE > remaining_jobs)); then
      CURRENT_WAVE_SIZE="$remaining_jobs"
    fi
    NEXT_WAVE_SIZE=$((remaining_jobs - CURRENT_WAVE_SIZE))
    if ((NEXT_WAVE_SIZE > WAVE_SIZE)); then
      NEXT_WAVE_SIZE="$WAVE_SIZE"
    fi
    if ((job_index == 0)); then
      check_inode_quota "$CURRENT_WAVE_SIZE"
    fi
  fi
  submit_job "${JOB_SPECS[$job_index]}"
done
submit_wave_barrier 0

if [[ -z "$PREVIOUS_BARRIER" ]]; then
  echo "No benchmark jobs were submitted." >&2
  exit 2
fi

SYNTHESIS_JOB_ID="$(sbatch --parsable \
  --dependency="afterok:${PREVIOUS_BARRIER}" \
  --output="${RUN_ROOT}/slurm/synthesis-%j.out" \
  --error="${RUN_ROOT}/slurm/synthesis-%j.err" \
  --export="ALL,MARA_PROJECT_ROOT=${PROJECT_ROOT},MARA_EXECUTION_PLAN=${PLAN_PATH},MARA_EXECUTION_TABLE=${JOB_TABLE},MARA_SYNTHESIS_OUTPUT_DIR=${PLAN_DIR},MARA_PLAN_PYTHON=${PLAN_PYTHON}" \
  "$SYNTHESIS_SCRIPT")"
SYNTHESIS_JOB_ID="${SYNTHESIS_JOB_ID%%;*}"
printf 'synthesis_job_id=%s\n' "$SYNTHESIS_JOB_ID" >"${PLAN_DIR}/synthesis_submission.txt"
printf 'execution_plan=%s\njob_table=%s\nsynthesis_job_id=%s\n' "$PLAN_PATH" "$JOB_TABLE" "$SYNTHESIS_JOB_ID"
