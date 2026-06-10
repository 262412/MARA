# Storage Layout Contract

This contract keeps MARA development from exhausting `scratch` or
`fastscratch` file quotas. It is mandatory for local development, model
serving, DocQA work, and any task that may create many files.

## Required Layout

Use this layout:

```text
Source/Git repository:
~/scratch/projects/MARA
= /mnt/scratch/users/tbczhang/projects/MARA

Python virtual environment:
~/fastscratch/envs/mara
= /mnt/fastscratch/users/tbczhang/envs/mara

Project .venv:
~/scratch/projects/MARA/.venv
must be a symlink to ~/fastscratch/envs/mara

Caches:
~/fastscratch/cache

Codex state:
~/fastscratch/.codex

MARA runtime data:
~/fastscratch/mara_runtime
```

Do not create real virtual environments, package caches, model caches, app data,
logs, or large generated working directories directly under `scratch`.

## Required Environment Variables

Interactive shells and automation must keep these variables on `fastscratch`:

```bash
export XDG_CACHE_HOME=$HOME/fastscratch/cache
export XDG_CONFIG_HOME=$HOME/fastscratch/cache/xdg-config
export XDG_DATA_HOME=$HOME/fastscratch/cache/xdg-data
export PIP_CACHE_DIR=$HOME/fastscratch/cache/pip
export UV_CACHE_DIR=$HOME/fastscratch/cache/uv
export UV_PYTHON_INSTALL_DIR=$HOME/fastscratch/cache/uv/python
export HF_HOME=$HOME/fastscratch/cache/huggingface
export HF_HUB_CACHE=$HF_HOME/hub
export HF_XET_CACHE=$HF_HOME/xet
export TORCH_HOME=$HOME/fastscratch/cache/torch
export TIKTOKEN_CACHE_DIR=$HOME/fastscratch/cache/tiktoken
export VLLM_CACHE_ROOT=$HOME/fastscratch/cache/vllm
export VLLM_MEDIA_CACHE=$HOME/fastscratch/cache/vllm-media-cache
export TRITON_CACHE_DIR=$HOME/fastscratch/cache/triton
export FLASHINFER_WORKSPACE_BASE=$HOME/fastscratch/cache/flashinfer-workspace
export FLASHINFER_CUBIN_DIR=$FLASHINFER_WORKSPACE_BASE/.cache/flashinfer/cubins
export CUDA_CACHE_PATH=$HOME/fastscratch/cache/cuda
export CODEX_HOME=$HOME/fastscratch/.codex
export MARA_RUNTIME_DIR=$HOME/fastscratch/mara_runtime
export KH_APP_DATA_DIR=$MARA_RUNTIME_DIR/ktem_app_data
```

`flowsettings.py` must respect `KH_APP_DATA_DIR` so app initialization,
DocQA indexing, graph caches, uploaded files, and SQLite state stay in
`fastscratch`.

## Preflight Check

Run this check before large development sessions, dependency installs, model
downloads, `MARA app init`, DocQA indexing, or model-serving work:

```bash
cd ~/scratch/projects/MARA
source ~/.bashrc

ls -ld .venv
readlink -f .venv
readlink -f .venv/bin/python
df -h .venv ktem_app_data

printf 'UV_CACHE_DIR=%s\n' "$UV_CACHE_DIR"
printf 'UV_PYTHON_INSTALL_DIR=%s\n' "$UV_PYTHON_INSTALL_DIR"
printf 'HF_HOME=%s\n' "$HF_HOME"
printf 'TIKTOKEN_CACHE_DIR=%s\n' "$TIKTOKEN_CACHE_DIR"
printf 'CODEX_HOME=%s\n' "$CODEX_HOME"
printf 'KH_APP_DATA_DIR=%s\n' "$KH_APP_DATA_DIR"

lfs quota -h -u tbczhang /mnt/fastscratch
```

The correct `.venv` result is a symlink that resolves to:

```text
/mnt/fastscratch/users/tbczhang/envs/mara
```

Stop before running `uv`, `pip`, tests, `MARA app init`, or model setup if:

- `.venv` is a real directory instead of a symlink.
- Any cache or runtime environment variable points to `scratch` or home.
- `lfs quota` shows `fastscratch` file usage above the soft quota.

## Repair Procedure

If `.venv` is a real directory in the repository, move it out of `scratch` and
replace it with a symlink:

```bash
cd ~/scratch/projects/MARA
mv .venv ~/fastscratch/envs/mara_from_scratch_backup
ln -s ~/fastscratch/envs/mara_from_scratch_backup .venv
```

If a clean environment is required:

```bash
cd ~/scratch/projects/MARA
rm -rf .venv
python -m venv ~/fastscratch/envs/mara
ln -s ~/fastscratch/envs/mara .venv
source .venv/bin/activate
```

Before deleting or compressing caches, inspect quota and directory ownership.
Prefer archiving cache backups into a single tar file over keeping hundreds of
thousands of small files. Do not delete user data, model weights, or active
runtime state without explicit user approval.

## Ignore Rules

The repository `.gitignore` must ignore these generated paths:

```gitignore
.venv
.venv/
logs
logs/
.theflow
.theflow/
ktem_app_data
ktem_app_data/
.mypy_cache/
.pytest_cache/
__pycache__/
```

The no-slash entries intentionally cover symlinks such as `.venv` and
`ktem_app_data`; the slash entries cover real directories if one is accidentally
created.
