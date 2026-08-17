#!/usr/bin/env bash
#SBATCH --job-name=mara-benchmark-cleanup-barrier
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:10:00

set -euo pipefail

RUNTIME_LIST="${MARA_RUNTIME_DIR_LIST:?MARA_RUNTIME_DIR_LIST is required}"
WAIT_SECONDS="${MARA_CLEANUP_BARRIER_WAIT_SECONDS:-120}"
DEADLINE=$((SECONDS + WAIT_SECONDS))

while ((SECONDS < DEADLINE)); do
  remaining=0
  while IFS= read -r runtime_dir; do
    [[ -z "$runtime_dir" ]] && continue
    if [[ -e "$runtime_dir" || -L "$runtime_dir" ]]; then
      remaining=$((remaining + 1))
      printf 'runtime_pending=%s\n' "$runtime_dir"
    fi
  done <"$RUNTIME_LIST"
  if ((remaining == 0)); then
    printf 'runtime_cleanup_verified=%s\n' "$RUNTIME_LIST"
    exit 0
  fi
  sleep 2
done

printf 'runtime_cleanup_barrier_failed=%s\n' "$RUNTIME_LIST" >&2
exit 2
