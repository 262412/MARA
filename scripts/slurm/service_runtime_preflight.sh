#!/usr/bin/env bash

# Validate the persistent model-service runtime before a benchmark creates its
# job-owned Python environment. The function is sourceable by Slurm wrappers
# and directly executable by launchers and characterization tests.

mara_service_runtime_fail() {
  local reason="$1"
  local path="${2:-}"
  printf 'service_runtime_preflight_failed=%s path=%s\n' "$reason" "$path" >&2
  return 2
}

mara_preflight_service_runtime() {
  local hpc_home="${1:-}"
  local mode="${2:-}"
  local vlm_serve_script="${3:-serve_qwen3_vl_8b_4k.sh}"
  local path
  local resolved_path
  local service_runtime_digest
  local -a required_files
  local -a required_executables
  local -a identity_paths

  [[ "$hpc_home" == /* ]] || {
    mara_service_runtime_fail non_absolute_hpc_home "$hpc_home"
    return 2
  }
  [[ -d "$hpc_home" ]] || {
    mara_service_runtime_fail missing_directory "$hpc_home"
    return 2
  }
  case "$mode" in
    text | multimodal | full) ;;
    *)
      mara_service_runtime_fail invalid_mode "$mode"
      return 2
      ;;
  esac

  required_files=(
    "$hpc_home/env.sh"
    "$hpc_home/env-retrieval.sh"
    "$hpc_home/configure_mara_local_models.py"
    "$hpc_home/local_retrieval_server.py"
    "$hpc_home/.venv/bin/activate"
    "$hpc_home/.venv-retrieval/bin/activate"
  )
  required_executables=(
    "$hpc_home/serve_qwen3_8b.sh"
    "$hpc_home/serve_retrieval.sh"
    "$hpc_home/.venv/bin/python"
    "$hpc_home/.venv/bin/vllm"
    "$hpc_home/.venv-retrieval/bin/python"
  )
  if [[ "$mode" == "multimodal" || "$mode" == "full" ]]; then
    required_files+=("$hpc_home/local_colvision_server.py")
    required_executables+=(
      "$hpc_home/$vlm_serve_script"
      "$hpc_home/serve_colvision.sh"
    )
  fi

  for path in "${required_files[@]}"; do
    [[ -f "$path" ]] || {
      mara_service_runtime_fail missing_file "$path"
      return 2
    }
  done
  for path in "${required_executables[@]}"; do
    [[ -x "$path" ]] || {
      mara_service_runtime_fail missing_executable "$path"
      return 2
    }
  done

  identity_paths=("${required_files[@]}" "${required_executables[@]}")
  service_runtime_digest="$({
    for path in "${identity_paths[@]}"; do
      resolved_path="$(realpath "$path")" || return 2
      printf 'path=%s\nresolved=%s\n' "$path" "$resolved_path"
      sha256sum "$path"
    done
  } | sha256sum | awk '{print $1}')" || {
    mara_service_runtime_fail identity_digest "$hpc_home"
    return 2
  }

  printf 'service_runtime_preflight=ok mode=%s hpc_home=%s\n' "$mode" "$hpc_home"
  printf 'service_runtime_digest=%s\n' "$service_runtime_digest"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  set -euo pipefail
  mara_preflight_service_runtime "${1:-}" "${2:-}" "${3:-serve_qwen3_vl_8b_4k.sh}"
fi
