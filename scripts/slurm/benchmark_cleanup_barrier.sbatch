#!/usr/bin/env bash
#SBATCH --job-name=mara-benchmark-cleanup-barrier
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:10:00

set -euo pipefail

RUNTIME_LIST="${MARA_RUNTIME_DIR_LIST:?MARA_RUNTIME_DIR_LIST is required}"
RUNTIME_RECEIPT_LIST="${MARA_RUNTIME_RECEIPT_LIST:?MARA_RUNTIME_RECEIPT_LIST is required}"
WAIT_SECONDS="${MARA_CLEANUP_BARRIER_WAIT_SECONDS:-120}"
POLL_SECONDS="${MARA_CLEANUP_BARRIER_POLL_SECONDS:-2}"
NEXT_WAVE_JOB_COUNT="${MARA_NEXT_WAVE_JOB_COUNT:-0}"
INODES_PER_JOB_RESERVE="${MARA_FULLSYSTEM_INODES_PER_JOB_RESERVE:-}"
MIN_FREE_INODES="${MARA_FULLSYSTEM_MIN_FREE_INODES:-}"

if [[ ! -f "$RUNTIME_LIST" || -L "$RUNTIME_LIST" ]]; then
  printf 'runtime_cleanup_barrier_failed=invalid_runtime_list:%s\n' "$RUNTIME_LIST" >&2
  exit 2
fi
if [[ ! -f "$RUNTIME_RECEIPT_LIST" || -L "$RUNTIME_RECEIPT_LIST" ]]; then
  printf 'runtime_cleanup_barrier_failed=invalid_runtime_receipt_list:%s\n' "$RUNTIME_RECEIPT_LIST" >&2
  exit 2
fi
if [[ ! "$WAIT_SECONDS" =~ ^[0-9]+$ ]]; then
  printf 'runtime_cleanup_barrier_failed=invalid_wait_seconds:%s\n' "$WAIT_SECONDS" >&2
  exit 2
fi
if [[ ! "$POLL_SECONDS" =~ ^[1-9][0-9]*$ ]]; then
  printf 'runtime_cleanup_barrier_failed=invalid_poll_seconds:%s\n' "$POLL_SECONDS" >&2
  exit 2
fi
if [[ ! "$NEXT_WAVE_JOB_COUNT" =~ ^[0-9]+$ ]]; then
  printf 'runtime_cleanup_barrier_failed=invalid_next_wave_job_count:%s\n' "$NEXT_WAVE_JOB_COUNT" >&2
  exit 2
fi
if ((NEXT_WAVE_JOB_COUNT > 0)); then
  if [[ ! "$INODES_PER_JOB_RESERVE" =~ ^[1-9][0-9]*$ ]]; then
    printf 'runtime_cleanup_barrier_failed=invalid_inode_reserve:%s\n' "$INODES_PER_JOB_RESERVE" >&2
    exit 2
  fi
  if [[ ! "$MIN_FREE_INODES" =~ ^[0-9]+$ ]]; then
    printf 'runtime_cleanup_barrier_failed=invalid_min_free_inodes:%s\n' "$MIN_FREE_INODES" >&2
    exit 2
  fi
fi

RUNTIME_DIRS=()
while IFS= read -r runtime_dir; do
  [[ -z "$runtime_dir" ]] && continue
  if [[ "$runtime_dir" != /* ]]; then
    printf 'runtime_cleanup_barrier_failed=non_absolute_runtime:%s\n' "$runtime_dir" >&2
    exit 2
  fi
  RUNTIME_DIRS+=("$runtime_dir")
done <"$RUNTIME_LIST"

if ((${#RUNTIME_DIRS[@]} == 0)); then
  printf 'runtime_cleanup_barrier_failed=empty_runtime_list:%s\n' "$RUNTIME_LIST" >&2
  exit 2
fi

RUNTIME_RECEIPTS=()
while IFS= read -r receipt_path; do
  [[ -z "$receipt_path" ]] && continue
  if [[ "$receipt_path" != /* ]]; then
    printf 'runtime_cleanup_barrier_failed=non_absolute_receipt:%s\n' "$receipt_path" >&2
    exit 2
  fi
  RUNTIME_RECEIPTS+=("$receipt_path")
done <"$RUNTIME_RECEIPT_LIST"

if ((${#RUNTIME_RECEIPTS[@]} == 0)); then
  printf 'runtime_cleanup_barrier_failed=empty_runtime_receipt_list:%s\n' "$RUNTIME_RECEIPT_LIST" >&2
  exit 2
fi
if ((${#RUNTIME_RECEIPTS[@]} != ${#RUNTIME_DIRS[@]})); then
  printf 'runtime_cleanup_barrier_failed=runtime_receipt_count_mismatch runtime_count=%s receipt_count=%s\n' \
    "${#RUNTIME_DIRS[@]}" "${#RUNTIME_RECEIPTS[@]}" >&2
  exit 2
fi

ACTUAL_RUNTIME_DIRS=()
for receipt_index in "${!RUNTIME_RECEIPTS[@]}"; do
  receipt_path="${RUNTIME_RECEIPTS[$receipt_index]}"
  if [[ ! -f "$receipt_path" || -L "$receipt_path" ]]; then
    printf 'runtime_cleanup_barrier_failed=missing_runtime_receipt:%s\n' "$receipt_path" >&2
    exit 2
  fi
  receipt_lines=()
  mapfile -t receipt_lines <"$receipt_path"
  if ((${#receipt_lines[@]} != 2)) ||
    [[ ! "${receipt_lines[0]:-}" =~ ^slurm_job_id=[0-9]+$ ]] ||
    [[ ! "${receipt_lines[1]:-}" =~ ^runtime_dir=/.+ ]]; then
    printf 'runtime_cleanup_barrier_failed=corrupt_runtime_receipt:%s\n' "$receipt_path" >&2
    exit 2
  fi
  receipt_job_id="${receipt_lines[0]#slurm_job_id=}"
  expected_receipt_name="${receipt_job_id}.receipt"
  if [[ "${receipt_path##*/}" != "$expected_receipt_name" ]]; then
    printf 'runtime_cleanup_barrier_failed=runtime_receipt_job_mismatch:%s\n' "$receipt_path" >&2
    exit 2
  fi
  actual_runtime_dir="${receipt_lines[1]#runtime_dir=}"
  if [[ "$actual_runtime_dir" != "${RUNTIME_DIRS[$receipt_index]}" ]]; then
    printf 'runtime_cleanup_barrier_failed=runtime_path_mismatch receipt=%s expected=%s actual=%s\n' \
      "$receipt_path" "${RUNTIME_DIRS[$receipt_index]}" "$actual_runtime_dir" >&2
    exit 2
  fi
  ACTUAL_RUNTIME_DIRS+=("$actual_runtime_dir")
done

DEADLINE=$((SECONDS + WAIT_SECONDS))

check_next_wave_inode_quota() {
  local quota_output quota_line used_inodes soft_limit projected_peak
  if [[ -n "${MARA_CLEANUP_BARRIER_QUOTA_LINE:-}" ]]; then
    quota_output="$MARA_CLEANUP_BARRIER_QUOTA_LINE"
  elif ! quota_output="$(lfs quota -u "$(id -un)" /mnt/fastscratch)"; then
    printf 'runtime_cleanup_barrier_failed=inode_quota_command\n' >&2
    return 2
  fi
  quota_line="$(awk '
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
  ' <<<"$quota_output")"
  if ! read -r used_inodes soft_limit <<<"$quota_line"; then
    printf 'runtime_cleanup_barrier_failed=inode_quota_parse\n' >&2
    return 2
  fi
  if [[ ! "$used_inodes" =~ ^[0-9]+$ || ! "$soft_limit" =~ ^[0-9]+$ ]]; then
    printf 'runtime_cleanup_barrier_failed=inode_quota_parse\n' >&2
    return 2
  fi
  projected_peak=$((used_inodes + NEXT_WAVE_JOB_COUNT * INODES_PER_JOB_RESERVE))
  if ((projected_peak + MIN_FREE_INODES >= soft_limit)); then
    printf 'runtime_cleanup_barrier_failed=inode_admission used=%s projected_peak=%s soft_limit=%s next_wave_jobs=%s per_job_reserve=%s reserve=%s\n' \
      "$used_inodes" "$projected_peak" "$soft_limit" "$NEXT_WAVE_JOB_COUNT" \
      "$INODES_PER_JOB_RESERVE" "$MIN_FREE_INODES" >&2
    return 2
  fi
  printf 'inode_admission=ok used=%s projected_peak=%s soft_limit=%s next_wave_jobs=%s per_job_reserve=%s reserve=%s\n' \
    "$used_inodes" "$projected_peak" "$soft_limit" "$NEXT_WAVE_JOB_COUNT" \
    "$INODES_PER_JOB_RESERVE" "$MIN_FREE_INODES"
}

while :; do
  remaining=0
  for runtime_dir in "${ACTUAL_RUNTIME_DIRS[@]}"; do
    if [[ -e "$runtime_dir" || -L "$runtime_dir" ]]; then
      remaining=$((remaining + 1))
      printf 'runtime_pending=%s\n' "$runtime_dir"
    fi
  done
  if ((remaining == 0)); then
    if ((NEXT_WAVE_JOB_COUNT > 0)); then
      check_next_wave_inode_quota
    fi
    printf 'runtime_cleanup_verified=%s\n' "$RUNTIME_LIST"
    exit 0
  fi
  if ((SECONDS >= DEADLINE)); then
    break
  fi
  sleep "$POLL_SECONDS"
done

printf 'runtime_cleanup_barrier_failed=%s\n' "$RUNTIME_LIST" >&2
exit 2
