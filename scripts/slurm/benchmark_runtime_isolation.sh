#!/usr/bin/env bash

# Benchmark jobs must never reuse the interactive MARA runtime.  This helper is
# intentionally shell-only so Slurm wrappers can establish the contract before
# importing any Python package (TheFlow discovers settings during import).

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

mara_benchmark_die() {
  printf 'MARA benchmark runtime contract failure: %s\n' "$*" >&2
  return 2
}

mara_benchmark_project_root() {
  local project_root="${MARA_PROJECT_ROOT:-$(pwd)}"
  project_root="$(realpath -m "$project_root")"
  git -C "$project_root" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    mara_benchmark_die "project root is not a checkout: $project_root"
    return 2
  }
  [[ -f "$project_root/flowsettings.py" ]] || {
    mara_benchmark_die "checkout flowsettings.py is missing: $project_root"
    return 2
  }
  [[ -f "$project_root/pyproject.toml" ]] || {
    mara_benchmark_die "checkout pyproject.toml is missing: $project_root"
    return 2
  }
  printf '%s' "$project_root"
}

mara_benchmark_path_inside() {
  local child="$1"
  local parent="$2"
  [[ "$child" == "$parent" || "$child" == "$parent"/* ]]
}

mara_benchmark_write_settings_source() {
  local settings_dir="$1"
  local source_checkout="$2"

  # TheFlow imports THEFLOW_SETTINGS_MODULE as a Python module name, not as a
  # filesystem path.  Keep a job-owned copy in a job-owned import directory.
  cp -- "$source_checkout/flowsettings.py" \
    "$settings_dir/mara_benchmark_flowsettings.py"
  cat >> "$settings_dir/mara_benchmark_flowsettings.py" <<'PY'

# MARA benchmark runtime overrides.  These values are exported before this
# module is imported and are deliberately not written back to the checkout.
STORAGE = dict(STORAGE)
STORAGE["prefix"] = os.environ["MARA_BENCHMARK_STORAGE_PREFIX"]
KH_APP_DATA_DIR = Path(os.environ["KH_APP_DATA_DIR"]).resolve()
THEFLOW_TEMP_PATH = os.environ["THEFLOW_TEMP_PATH"]
KH_SETTINGS_SOURCE = "benchmark-runtime"
PY
}

mara_configure_benchmark_runtime() {
  local suite_slug
  local task_slug
  local runtime_root
  local runtime_dir
  local suite_dir
  local project_root
  local owner_token

  project_root="$(mara_benchmark_project_root)" || return 2
  suite_slug="$(mara_benchmark_slug "${1:-benchmark}")"
  task_slug="$(mara_benchmark_slug "$(mara_benchmark_task_id)")"
  runtime_root="${MARA_BENCHMARK_RUNTIME_ROOT:-/mnt/fastscratch/users/tbczhang/mara_runtime/benchmark_runs}"
  runtime_root="$(realpath -m "$runtime_root")"
  runtime_dir="${runtime_root}/${suite_slug}/${task_slug}"
  suite_dir="$(dirname "$runtime_dir")"

  # A runtime under the source checkout could resolve to the checkout .theflow
  # tree.  Refuse it before creating anything there.
  if mara_benchmark_path_inside "$runtime_root" "$project_root"; then
    mara_benchmark_die "runtime root is inside the source checkout: $runtime_root"
    return 2
  fi
  if [[ -e "$runtime_dir" || -L "$runtime_dir" ]]; then
    mara_benchmark_die "job runtime already exists (cross-job reuse): $runtime_dir"
    return 2
  fi
  mkdir -p "$suite_dir" || return 2
  if ! mkdir "$runtime_dir"; then
    mara_benchmark_die "unable to claim exclusive job runtime: $runtime_dir"
    return 2
  fi

  export MARA_PROJECT_ROOT="$project_root"
  export MARA_BENCHMARK_PROJECT_ROOT="$project_root"
  export MARA_BENCHMARK_RUNTIME_ROOT="$runtime_root"
  export MARA_BENCHMARK_RUNTIME_DIR="$runtime_dir"
  export MARA_RUNTIME_DIR="$runtime_dir"
  export KH_APP_DATA_DIR="$runtime_dir/ktem_app_data"
  export MARA_BENCHMARK_THEFLOW_DIR="$runtime_dir/theflow"
  export MARA_BENCHMARK_STORAGE_PREFIX="$MARA_BENCHMARK_THEFLOW_DIR"
  export THEFLOW_TEMP_PATH="$runtime_dir/theflow-temp"
  export MARA_BENCHMARK_FLOWSETTINGS_PATH="${MARA_BENCHMARK_THEFLOW_DIR}/mara_benchmark_flowsettings.py"
  export MARA_BENCHMARK_FLOWSETTINGS_MODULE="mara_benchmark_flowsettings"
  export THEFLOW_SETTINGS_MODULE="$MARA_BENCHMARK_FLOWSETTINGS_MODULE"
  export UV_PROJECT_ENVIRONMENT="$runtime_dir/venv"
  export MARA_BENCHMARK_PYTHON="$UV_PROJECT_ENVIRONMENT/bin/python"
  export MARA_BENCHMARK_RUNTIME_CONTRACT="$runtime_dir/runtime-contract.json"
  export MARA_BENCHMARK_RUNTIME_OWNER_FILE="$runtime_dir/.owner"
  owner_token="${runtime_dir}|${task_slug}|${project_root}|$$"
  export MARA_BENCHMARK_RUNTIME_OWNER_TOKEN="$owner_token"
  export MARA_BENCHMARK_RUNTIME_ISOLATED=1
  export MARA_BENCHMARK_RUNTIME_BOOTSTRAPPED=0
  export MARA_BENCHMARK_RUNTIME_CLEANED=0

  mkdir -p "$KH_APP_DATA_DIR" "$MARA_BENCHMARK_THEFLOW_DIR" "$THEFLOW_TEMP_PATH"
  printf '%s\n' "$owner_token" > "$MARA_BENCHMARK_RUNTIME_OWNER_FILE"
  mara_benchmark_write_settings_source "$MARA_BENCHMARK_THEFLOW_DIR" "$project_root"

  # Put only this job's settings module first.  Existing model/download caches
  # remain shared through UV_CACHE_DIR/HF_HOME and are not redirected here.
  export PYTHONPATH="${MARA_BENCHMARK_THEFLOW_DIR}${PYTHONPATH:+:${PYTHONPATH}}"
}

mara_assert_isolated_kh_app_data() {
  local project_root
  local runtime_dir
  local expected_app
  local expected_settings
  local expected_python_env
  local expected_python
  local owner
  local canonical_venv

  if [[ "${MARA_BENCHMARK_RUNTIME_ISOLATED:-}" != "1" ]]; then
    mara_benchmark_die "missing benchmark marker; call mara_configure_benchmark_runtime first"
    return 2
  fi
  project_root="$(mara_benchmark_project_root)" || return 2
  runtime_dir="$(realpath -m "${MARA_BENCHMARK_RUNTIME_DIR:-}")"
  [[ -n "${MARA_BENCHMARK_RUNTIME_DIR:-}" && "$runtime_dir" != "/" ]] || {
    mara_benchmark_die "missing or invalid MARA_BENCHMARK_RUNTIME_DIR"
    return 2
  }
  [[ ! -L "${MARA_BENCHMARK_RUNTIME_DIR:-}" ]] || {
    mara_benchmark_die "job runtime path is a symlink (cross-job storage risk)"
    return 2
  }
  if mara_benchmark_path_inside "$runtime_dir" "$project_root"; then
    mara_benchmark_die "job runtime points inside checkout (checkout .theflow risk): $runtime_dir"
    return 2
  fi

  expected_app="$runtime_dir/ktem_app_data"
  expected_settings="$runtime_dir/theflow/mara_benchmark_flowsettings.py"
  expected_python_env="$runtime_dir/venv"
  expected_python="$expected_python_env/bin/python"
  [[ "${KH_APP_DATA_DIR:-}" == "$expected_app" ]] || {
    mara_benchmark_die "KH_APP_DATA_DIR is not job-owned: ${KH_APP_DATA_DIR:-<unset>}"
    return 2
  }
  [[ "${MARA_BENCHMARK_FLOWSETTINGS_PATH:-}" == "$expected_settings" ]] || {
    mara_benchmark_die "settings source is not job-owned: ${MARA_BENCHMARK_FLOWSETTINGS_PATH:-<unset>}"
    return 2
  }
  [[ "${THEFLOW_SETTINGS_MODULE:-}" == "${MARA_BENCHMARK_FLOWSETTINGS_MODULE:-}" && \
    "$THEFLOW_SETTINGS_MODULE" == "mara_benchmark_flowsettings" ]] || {
    mara_benchmark_die "TheFlow settings module is not the job module: ${THEFLOW_SETTINGS_MODULE:-<unset>}"
    return 2
  }
  [[ -f "$expected_settings" ]] || {
    mara_benchmark_die "job-owned TheFlow settings source is missing: $expected_settings"
    return 2
  }
  [[ "${MARA_BENCHMARK_STORAGE_PREFIX:-}" == "$runtime_dir/theflow" ]] || {
    mara_benchmark_die "STORAGE.prefix is not job-owned: ${MARA_BENCHMARK_STORAGE_PREFIX:-<unset>}"
    return 2
  }
  [[ "${THEFLOW_TEMP_PATH:-}" == "$runtime_dir/theflow-temp" ]] || {
    mara_benchmark_die "THEFLOW_TEMP_PATH is not job-owned: ${THEFLOW_TEMP_PATH:-<unset>}"
    return 2
  }
  [[ "${UV_PROJECT_ENVIRONMENT:-}" == "$expected_python_env" ]] || {
    mara_benchmark_die "benchmark selected the canonical/shared Python environment: ${UV_PROJECT_ENVIRONMENT:-<unset>}"
    return 2
  }
  [[ "${MARA_BENCHMARK_PYTHON:-}" == "$expected_python" ]] || {
    mara_benchmark_die "benchmark interpreter is not job-owned: ${MARA_BENCHMARK_PYTHON:-<unset>}"
    return 2
  }
  [[ "${MARA_BENCHMARK_RUNTIME_CONTRACT:-}" == "$runtime_dir/runtime-contract.json" ]] || {
    mara_benchmark_die "runtime contract output crosses job boundary"
    return 2
  }

  canonical_venv="$(realpath -m "$project_root/.venv")"
  if [[ "$canonical_venv" == "$expected_python_env" ||
    "$UV_PROJECT_ENVIRONMENT" == "$canonical_venv" ||
    "$(realpath -m "$UV_PROJECT_ENVIRONMENT")" == "$canonical_venv" ]]; then
    mara_benchmark_die "benchmark runtime aliases the checkout canonical .venv: $canonical_venv"
    return 2
  fi
  if [[ "${MARA_BENCHMARK_STORAGE_PREFIX}" == "$project_root"/* || "${THEFLOW_TEMP_PATH}" == "$project_root"/* ]]; then
    mara_benchmark_die "TheFlow storage/temp points into the source checkout"
    return 2
  fi
  owner="$(<"$MARA_BENCHMARK_RUNTIME_OWNER_FILE")" 2>/dev/null || {
    mara_benchmark_die "job runtime owner marker is missing"
    return 2
  }
  [[ "$owner" == "${MARA_BENCHMARK_RUNTIME_OWNER_TOKEN:-}" ]] || {
    mara_benchmark_die "job runtime owner marker does not belong to this job"
    return 2
  }
}

mara_benchmark_self_check() {
  mara_assert_isolated_kh_app_data
  "$MARA_BENCHMARK_PYTHON" - "$MARA_BENCHMARK_RUNTIME_CONTRACT" <<'PY'
import importlib.util
import json
import os
import sys
from pathlib import Path

contract_path = Path(sys.argv[1]).resolve()
project_root = Path(os.environ["MARA_BENCHMARK_PROJECT_ROOT"]).resolve()
runtime_dir = Path(os.environ["MARA_BENCHMARK_RUNTIME_DIR"]).resolve()
expected_python = Path(os.environ["MARA_BENCHMARK_PYTHON"]).absolute()

actual_python = Path(sys.executable).absolute()
if actual_python != expected_python:
    raise SystemExit(
        f"runtime interpreter mismatch: expected {expected_python}, got {actual_python}"
    )

import slide_cli
import ktem
from theflow.settings import settings as flowsettings


def resolved(value: object) -> Path:
    return Path(str(value)).expanduser().resolve()


def assert_inside(path: Path, parent: Path, label: str) -> None:
    try:
        path.relative_to(parent)
    except ValueError as exc:
        raise SystemExit(f"{label} crosses checkout boundary: {path}") from exc


slide_file = resolved(slide_cli.__file__)
ktem_file = resolved(ktem.__file__)
assert_inside(slide_file, project_root / "libs" / "slide_cli", "slide_cli.__file__")
assert_inside(ktem_file, project_root / "libs" / "ktem", "ktem.__file__")

settings_module = os.environ["THEFLOW_SETTINGS_MODULE"]
settings_spec = importlib.util.find_spec(settings_module)
if settings_spec is None or not settings_spec.origin:
    raise SystemExit(f"settings source cannot be resolved: {settings_module}")
settings_file = resolved(settings_spec.origin)
assert_inside(settings_file, runtime_dir / "theflow", "TheFlow settings source")

storage = getattr(flowsettings, "STORAGE", {})
storage_prefix = resolved(storage.get("prefix", ""))
expected_storage = resolved(os.environ["MARA_BENCHMARK_STORAGE_PREFIX"])
if storage_prefix != expected_storage:
    raise SystemExit(
        f"TheFlow STORAGE.prefix mismatch: expected {expected_storage}, got {storage_prefix}"
    )

app_data = resolved(os.environ["KH_APP_DATA_DIR"])
if resolved(getattr(flowsettings, "KH_APP_DATA_DIR", "")) != app_data:
    raise SystemExit("TheFlow KH_APP_DATA_DIR does not match the job runtime")

from theflow.storage import storage as flow_storage
from theflow.utils.paths import temp_path as resolve_temp_path

temp_path = resolved(resolve_temp_path())
expected_temp = resolved(os.environ["THEFLOW_TEMP_PATH"])
if temp_path != expected_temp:
    raise SystemExit(
        f"TheFlow temp path mismatch: expected {expected_temp}, got {temp_path}"
    )
if resolved(getattr(flow_storage, "_prefix", "")) != expected_storage:
    raise SystemExit("TheFlow LocalStorage prefix does not match the job runtime")

for name, value in {
    "KH_DATABASE": str(getattr(flowsettings, "KH_DATABASE", "")),
    "KH_FILESTORAGE_PATH": str(getattr(flowsettings, "KH_FILESTORAGE_PATH", "")),
    "KH_DOCSTORE.path": str((getattr(flowsettings, "KH_DOCSTORE", {}) or {}).get("path", "")),
    "KH_VECTORSTORE.path": str((getattr(flowsettings, "KH_VECTORSTORE", {}) or {}).get("path", "")),
}.items():
    path_value = value.removeprefix("sqlite:///")
    if not path_value:
        raise SystemExit(f"{name} is missing from the job settings")
    assert_inside(resolved(path_value), runtime_dir, name)

payload = {
    "sys.executable": str(actual_python),
    "slide_cli.__file__": str(slide_file),
    "ktem.__file__": str(ktem_file),
    "theflow_settings_module": settings_module,
    "theflow_settings_source": str(settings_file),
    "theflow_storage_prefix": str(storage_prefix),
    "KH_APP_DATA_DIR": str(app_data),
    "flowsettings.KH_APP_DATA_DIR": str(resolved(getattr(flowsettings, "KH_APP_DATA_DIR", ""))),
    "THEFLOW_TEMP_PATH": str(temp_path),
    "UV_PROJECT_ENVIRONMENT": os.environ["UV_PROJECT_ENVIRONMENT"],
}
contract_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
for key, value in payload.items():
    print(f"runtime_contract.{key}={value}")
PY
}

mara_bootstrap_benchmark_runtime() {
  mara_assert_isolated_kh_app_data
  local uv_command="${MARA_BENCHMARK_UV:-uv}"

  # UV_PROJECT_ENVIRONMENT points at this job only.  The frozen lockfile and
  # mara extra make the fresh interpreter deterministic without touching the
  # shared checkout .venv or performing editable installs there.
  (
    cd "$MARA_BENCHMARK_PROJECT_ROOT"
    "$uv_command" sync --frozen --no-dev --extra mara --python 3.10
  )
  [[ -x "$MARA_BENCHMARK_PYTHON" ]] || {
    mara_benchmark_die "frozen sync did not create $MARA_BENCHMARK_PYTHON"
    return 2
  }
  if ! mara_benchmark_self_check; then
    mara_benchmark_die "fresh interpreter runtime self-check failed"
    return 2
  fi
  if ! "$MARA_BENCHMARK_PYTHON" - <<'PY'
from slide_cli.docqa_runtime import create_docqa_runtime

runtime = create_docqa_runtime()
print(f"bootstrapped_runtime={type(runtime).__name__}")
PY
  then
    mara_benchmark_die "fresh DocQA runtime bootstrap failed"
    return 2
  fi
  export MARA_BENCHMARK_RUNTIME_BOOTSTRAPPED=1
}

mara_cleanup_benchmark_runtime() {
  local runtime_dir
  local suite_dir
  local runtime_root
  local runtime_root_name

  if [[ "${MARA_BENCHMARK_RUNTIME_CLEANED:-0}" == "1" ]]; then
    return 0
  fi
  mara_assert_isolated_kh_app_data || return 2
  runtime_dir="$(realpath -m "$MARA_BENCHMARK_RUNTIME_DIR")"
  suite_dir="$(dirname "$runtime_dir")"
  runtime_root="$(dirname "$suite_dir")"
  runtime_root_name="$(basename "$runtime_root")"

  case "$runtime_root_name" in
    benchmark_*) ;;
    *)
      mara_benchmark_die "refusing cleanup outside a benchmark_* root: $runtime_root"
      return 2
      ;;
  esac
  if [[ "$runtime_dir" != "$runtime_root"/*/* ]]; then
    mara_benchmark_die "refusing malformed benchmark runtime cleanup path: $runtime_dir"
    return 2
  fi
  if [[ ! -f "$MARA_BENCHMARK_RUNTIME_OWNER_FILE" ]]; then
    mara_benchmark_die "refusing cleanup without the job owner marker"
    return 2
  fi
  rm -rf -- "$runtime_dir"
  rmdir -- "$suite_dir" 2>/dev/null || true
  export MARA_BENCHMARK_RUNTIME_CLEANED=1
}

mara_install_benchmark_runtime_cleanup() {
  # Preserve the service wrapper's cleanup function when present, and preserve
  # the original exit status even if a defensive cleanup check reports a fault.
  trap '
    _mara_benchmark_exit_status=$?
    if declare -F cleanup >/dev/null 2>&1; then
      cleanup || true
    fi
    if [[ "${MARA_BENCHMARK_RUNTIME_CLEANED:-0}" != "1" && -n "${MARA_BENCHMARK_RUNTIME_DIR:-}" ]]; then
      mara_cleanup_benchmark_runtime || printf "MARA benchmark runtime cleanup refused; preserving unverified runtime\n" >&2
    fi
    exit "$_mara_benchmark_exit_status"
  ' EXIT
}
