#!/usr/bin/env bash

mara_benchmark_slug() {
  local value="${1:-benchmark}"
  value="${value//[^A-Za-z0-9._-]/-}"
  value="${value#-}"
  value="${value%-}"
  printf '%s' "${value:-benchmark}"
}

mara_benchmark_task_id() {
  if [[ -n "${SLURM_ARRAY_JOB_ID:-}" || -n "${SLURM_ARRAY_TASK_ID:-}" ]]; then
    printf 'array%s-task%s-job%s' \
      "${SLURM_ARRAY_JOB_ID:-manual}" \
      "${SLURM_ARRAY_TASK_ID:-0}" \
      "${SLURM_JOB_ID:-manual}"
    return 0
  fi

  if [[ -n "${SLURM_JOB_ID:-}" ]]; then
    printf 'job%s' "$SLURM_JOB_ID"
    return 0
  fi

  printf 'manual-%s-%s' "$(date +%Y%m%d_%H%M%S)" "$$"
}

mara_configure_benchmark_runtime() {
  local suite_slug
  local task_slug
  local runtime_root

  suite_slug="$(mara_benchmark_slug "${1:-benchmark}")"
  task_slug="$(mara_benchmark_slug "$(mara_benchmark_task_id)")"
  runtime_root="${MARA_BENCHMARK_RUNTIME_ROOT:-/users/tbczhang/fastscratch/mara_runtime/benchmark_runs}"

  export MARA_BENCHMARK_RUNTIME_DIR="${runtime_root}/${suite_slug}/${task_slug}"
  export MARA_RUNTIME_DIR="$MARA_BENCHMARK_RUNTIME_DIR"
  export KH_APP_DATA_DIR="${MARA_BENCHMARK_RUNTIME_DIR}/ktem_app_data"
  export MARA_BENCHMARK_RUNTIME_ISOLATED=1

  mkdir -p "$KH_APP_DATA_DIR"
}

mara_assert_isolated_kh_app_data() {
  local shared_runtime_1="/users/tbczhang/fastscratch/mara_runtime/ktem_app_data"
  local shared_runtime_2="/mnt/fastscratch/users/tbczhang/mara_runtime/ktem_app_data"

  if [[ "${MARA_BENCHMARK_RUNTIME_ISOLATED:-}" != "1" ]]; then
    printf 'Refusing benchmark run without isolated KH_APP_DATA_DIR. Call mara_configure_benchmark_runtime first.\n' >&2
    return 2
  fi

  if [[ -z "${KH_APP_DATA_DIR:-}" || -z "${MARA_BENCHMARK_RUNTIME_DIR:-}" ]]; then
    printf 'Refusing benchmark run with missing MARA benchmark runtime variables.\n' >&2
    return 2
  fi

  if [[ "$KH_APP_DATA_DIR" != "${MARA_BENCHMARK_RUNTIME_DIR}/ktem_app_data" ]]; then
    printf 'Refusing benchmark run with mismatched KH_APP_DATA_DIR: %s\n' "$KH_APP_DATA_DIR" >&2
    return 2
  fi

  case "$KH_APP_DATA_DIR" in
    "$shared_runtime_1"|"$shared_runtime_1/"|"$shared_runtime_2"|"$shared_runtime_2/")
      printf 'Refusing benchmark run against shared KH_APP_DATA_DIR: %s\n' "$KH_APP_DATA_DIR" >&2
      return 2
      ;;
  esac
}

mara_bootstrap_benchmark_runtime() {
  mara_assert_isolated_kh_app_data

  uv run --python 3.10 python - <<'PY'
from slide_cli.docqa_runtime import create_docqa_runtime

runtime = create_docqa_runtime()
print(f"bootstrapped_runtime={type(runtime).__name__}")
PY
}

mara_cleanup_benchmark_runtime() {
  mara_assert_isolated_kh_app_data

  local runtime_dir
  local suite_dir
  local runtime_root
  local runtime_root_name

  runtime_dir="$(realpath -m "$MARA_BENCHMARK_RUNTIME_DIR")"
  suite_dir="$(dirname "$runtime_dir")"
  runtime_root="$(dirname "$suite_dir")"
  runtime_root_name="$(basename "$runtime_root")"

  case "$runtime_root_name" in
    benchmark_*) ;;
    *)
      printf 'Refusing benchmark cleanup outside a benchmark_* root: %s\n' \
        "$runtime_root" >&2
      return 2
      ;;
  esac

  if [[ "$runtime_dir" != "$runtime_root"/*/* ]]; then
    printf 'Refusing malformed benchmark runtime cleanup path: %s\n' \
      "$runtime_dir" >&2
    return 2
  fi

  rm -rf -- "$runtime_dir"
  rmdir -- "$suite_dir" 2>/dev/null || true
}
