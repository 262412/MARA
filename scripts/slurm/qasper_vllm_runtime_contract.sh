#!/usr/bin/env bash

# Shared QASPER vLLM/cache contract copied from the provider probe that passed
# on job 10396493.  Natural and provider-backed launchers must not drift here.

mara_configure_qasper_vllm_runtime() {
  export HF_HOME=/mnt/fastscratch/users/tbczhang/cache/huggingface
  export XDG_CACHE_HOME=/mnt/fastscratch/users/tbczhang/cache
  export UV_CACHE_DIR=/mnt/fastscratch/users/tbczhang/cache/uv
  export UV_NO_CACHE=1
  export UV_LINK_MODE=copy
  export HF_HUB_OFFLINE=1
  export TRANSFORMERS_OFFLINE=1
  export VLLM_WORKER_MULTIPROC_METHOD=spawn
  export FLASHINFER_WORKSPACE_BASE=/mnt/fastscratch/users/tbczhang/cache/flashinfer-workspace
  export FLASHINFER_CUBIN_DIR="$FLASHINFER_WORKSPACE_BASE/.cache/flashinfer/cubins"
  export TRITON_CACHE_DIR=/mnt/fastscratch/users/tbczhang/cache/triton
  export CUDA_CACHE_PATH=/mnt/fastscratch/users/tbczhang/cache/cuda
}

mara_assert_writable_provider_cache() {
  local cache_dir="$1"
  local cache_label="$2"
  local write_probe

  mkdir -p "$cache_dir"
  [[ -d "$cache_dir" && -w "$cache_dir" ]] || {
    printf 'provider toolchain preflight failed: %s cache is not writable: %s\n' \
      "$cache_label" "$cache_dir" >&2
    return 1
  }
  write_probe="$(mktemp "$cache_dir/.mara-write-probe.XXXXXX")" || {
    printf 'provider toolchain preflight failed: cannot write %s cache: %s\n' \
      "$cache_label" "$cache_dir" >&2
    return 1
  }
  rm -f -- "$write_probe"
}

mara_preflight_qasper_vllm_runtime() {
  local artifact_dir="$1"
  local NINJA_BIN
  local GCC_BIN
  local GXX_BIN

  [[ -n "${VLLM_BIN:-}" && -x "$VLLM_BIN" ]] || {
    printf 'vLLM binary is missing: %s\n' "${VLLM_BIN:-unset}" >&2
    return 2
  }
  [[ -n "${VLLM_ENV_BIN:-}" && -n "${VLLM_PYTHON:-}" && -x "$VLLM_PYTHON" ]] || {
    printf 'vLLM Python is missing: %s\n' "${VLLM_PYTHON:-unset}" >&2
    return 2
  }

  module load cuda/12.8.0-gcc14.2.0
  module list 2> "$artifact_dir/modules.txt"
  [[ -n "${CUDA_HOME:-}" && -x "$CUDA_HOME/bin/nvcc" ]] || {
    printf 'CUDA toolkit preflight failed: CUDA_HOME=%s\n' "${CUDA_HOME:-unset}" >&2
    return 2
  }
  {
    printf 'CUDA_HOME=%s\n' "$CUDA_HOME"
    printf 'nvcc=%s\n' "$(command -v nvcc)"
    "$CUDA_HOME/bin/nvcc" --version
  } > "$artifact_dir/cuda_toolchain.txt"

  export PATH="$VLLM_ENV_BIN:$PATH"
  NINJA_BIN="$(command -v ninja || true)"
  GCC_BIN="$(command -v gcc || true)"
  GXX_BIN="$(command -v g++ || true)"
  [[ -n "$NINJA_BIN" && -x "$NINJA_BIN" ]] || {
    printf 'provider toolchain preflight failed: ninja is not executable on PATH\n' >&2
    return 2
  }
  [[ "$(realpath -m "$NINJA_BIN")" == "$(realpath -m "$VLLM_ENV_BIN/ninja")" ]] || {
    printf 'provider toolchain preflight failed: expected vLLM ninja=%s actual=%s\n' \
      "$VLLM_ENV_BIN/ninja" "$NINJA_BIN" >&2
    return 2
  }
  [[ -n "$GCC_BIN" && -x "$GCC_BIN" && -n "$GXX_BIN" && -x "$GXX_BIN" ]] || {
    printf 'provider toolchain preflight failed: gcc/g++ is not executable on PATH\n' >&2
    return 2
  }
  ninja --version >/dev/null
  gcc -dumpfullversion -dumpversion >/dev/null
  g++ -dumpfullversion -dumpversion >/dev/null

  mara_assert_writable_provider_cache "$FLASHINFER_WORKSPACE_BASE" flashinfer_workspace
  mara_assert_writable_provider_cache "$FLASHINFER_CUBIN_DIR" flashinfer_cubin
  mara_assert_writable_provider_cache "$TRITON_CACHE_DIR" triton
  mara_assert_writable_provider_cache "$CUDA_CACHE_PATH" cuda

  "$VLLM_PYTHON" - <<'PY' > "$artifact_dir/provider_python_stack.txt"
import importlib.metadata
import shutil

for package in ("vllm", "flashinfer-python", "torch", "ninja"):
    print(f"{package}={importlib.metadata.version(package)}")
print(f"ninja_resolved={shutil.which('ninja')}")
if shutil.which("ninja") is None:
    raise SystemExit("ninja is not visible to the vLLM Python process")
PY

  {
    printf 'PATH=%s\n' "$PATH"
    printf 'vllm=%s\n' "$VLLM_BIN"
    printf 'vllm_python=%s\n' "$VLLM_PYTHON"
    printf 'ninja=%s\n' "$NINJA_BIN"
    printf 'ninja_version=%s\n' "$(ninja --version)"
    printf 'gcc=%s\n' "$GCC_BIN"
    printf 'gcc_version=%s\n' "$(gcc -dumpfullversion -dumpversion)"
    printf 'gxx=%s\n' "$GXX_BIN"
    printf 'gxx_version=%s\n' "$(g++ -dumpfullversion -dumpversion)"
    printf 'flashinfer_workspace=%s\n' "$FLASHINFER_WORKSPACE_BASE"
    printf 'flashinfer_cubin=%s\n' "$FLASHINFER_CUBIN_DIR"
    printf 'triton_cache=%s\n' "$TRITON_CACHE_DIR"
    printf 'cuda_cache=%s\n' "$CUDA_CACHE_PATH"
  } > "$artifact_dir/provider_toolchain.txt"
}
