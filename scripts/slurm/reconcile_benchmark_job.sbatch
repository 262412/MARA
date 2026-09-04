#!/usr/bin/env bash
#SBATCH --job-name=mara-benchmark-reconcile
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00

set -euo pipefail

PROJECT_ROOT="${MARA_RECONCILE_PROJECT_ROOT:?Set MARA_RECONCILE_PROJECT_ROOT}"
PLAN_PATH="${MARA_RECONCILE_PLAN:?Set MARA_RECONCILE_PLAN}"
TABLE_PATH="${MARA_RECONCILE_TABLE:?Set MARA_RECONCILE_TABLE}"
JOB_KEY="${MARA_RECONCILE_JOB_KEY:?Set MARA_RECONCILE_JOB_KEY}"
TARGET_JOB_ID="${MARA_RECONCILE_TARGET_JOB_ID:?Set MARA_RECONCILE_TARGET_JOB_ID}"
PLAN_PYTHON="${MARA_RECONCILE_PYTHON:-python3}"

case "$(realpath -m "$PROJECT_ROOT")" in
  /mnt/scratch/users/tbczhang/projects/MARA*) ;;
  *)
    printf 'Refusing reconciliation outside a MARA worktree: %s\n' "$PROJECT_ROOT" >&2
    exit 2
    ;;
esac
case "$(realpath -m "$PLAN_PATH")" in
  /mnt/scratch/users/tbczhang/outputs/MARA/*) ;;
  *)
    printf 'Refusing reconciliation plan outside MARA outputs: %s\n' "$PLAN_PATH" >&2
    exit 2
    ;;
esac

slurm_state=""
slurm_exit_code=""
for _attempt in {1..10}; do
  status_line="$(
    sacct -X -n -P -o State,ExitCode -j "$TARGET_JOB_ID" 2>/dev/null |
      awk -F'|' 'NF >= 2 && $1 != "" {print $1 "|" $2; exit}'
  )"
  slurm_state="${status_line%%|*}"
  slurm_state="${slurm_state%%+*}"
  slurm_exit_code="${status_line#*|}"
  case "$slurm_state" in
    BOOT_FAIL|CANCELLED|COMPLETED|DEADLINE|FAILED|NODE_FAIL|OUT_OF_MEMORY|PREEMPTED|REVOKED|SPECIAL_EXIT|TIMEOUT)
      break
      ;;
  esac
  sleep 2
done

args=(
  "$PLAN_PYTHON"
  "$PROJECT_ROOT/scripts/slurm/build_benchmark_execution_plan.py"
  reconcile-completion
  --plan "$PLAN_PATH"
  --table "$TABLE_PATH"
  --job-key "$JOB_KEY"
  --job-id "$TARGET_JOB_ID"
  --slurm-state "${slurm_state:-UNKNOWN}"
  --slurm-exit-code "$slurm_exit_code"
)
if [[ -n "${MARA_RECONCILE_ARTIFACT_DIR:-}" ]]; then
  args+=(--artifact-dir "$MARA_RECONCILE_ARTIFACT_DIR")
fi
set +e
"${args[@]}"
reconciliation_status=$?
set -e
if [[ "$reconciliation_status" == "2" ]]; then
  printf 'Target job failure was recorded in the execution plan.\n'
  exit 0
fi
exit "$reconciliation_status"
