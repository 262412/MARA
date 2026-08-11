# Storage Layout Contract

This contract keeps MARA development from exhausting `scratch` or
`fastscratch` file quotas and keeps datasets out of the Git repository. It is
mandatory for local development, model serving, DocQA work, dataset work, and
any task that may create many files.

## Required Layout

Use this layout:

```text
Source/Git repository:
~/scratch/projects/MARA
= /mnt/scratch/users/tbczhang/projects/MARA

Python virtual environment:
~/fastscratch/envs/mara
= /mnt/fastscratch/users/tbczhang/envs/mara

uv-managed Python installations:
~/fastscratch/python
= /mnt/fastscratch/users/tbczhang/python

Project .venv:
~/scratch/projects/MARA/.venv
must be a symlink to ~/fastscratch/envs/mara

Caches:
~/fastscratch/cache

High-file-count disposable pre-commit hook cache:
~/scratch/pre-commit-cache

Codex state:
~/fastscratch/.codex

MARA runtime data:
~/fastscratch/mara_runtime

Original or important datasets:
~/data/datasets/MARA
= /mnt/data2/users/tbczhang/datasets/MARA

Compute-time dataset copies:
~/scratch/datasets/MARA
or, for high-I/O small-file workloads, ~/fastscratch/datasets/MARA

Compute-time outputs:
~/scratch/outputs/MARA
```

Do not create real virtual environments, package caches, model caches, app data,
logs, datasets, outputs, or large generated working directories directly under
the Git repository.

## Dataset Layout

Datasets are split by purpose.

- Put original or important datasets in `~/data/datasets/MARA`. `data` has a
  larger quota and backup, so it is the right place for medium-term source data.
- Treat `data` as read-only from compute jobs. Do not submit Slurm jobs from
  `data`, and do not write job outputs into `data`.
- Put the copy used by training, indexing, experiments, or Slurm jobs in
  `~/scratch/datasets/MARA` for large files or moderate file counts.
- Use `~/fastscratch/datasets/MARA` only for high-I/O small-file workloads such
  as image shards, small JSON files, token caches, or embedding shards.
- Write active experiment outputs to `~/scratch/outputs/MARA`. Copy important
  final outputs back to `data` or another backup location after the run.
- Do not use `~/scratch/projects/MARA/data`, `~/scratch/projects/MARA/datasets`,
  `~/scratch/projects/MARA/outputs`, `~/fastscratch` as the only copy,
  `~/localscratch`, `/tmp`, or home for long-lived datasets.

Recommended setup for large files or moderate file counts:

```bash
mkdir -p ~/data/datasets/MARA
mkdir -p ~/scratch/datasets/MARA
mkdir -p ~/scratch/outputs/MARA
rsync -avP ~/data/datasets/MARA/ ~/scratch/datasets/MARA/
```

Recommended Slurm paths:

```bash
DATA_DIR=$HOME/scratch/datasets/MARA
OUT_DIR=$HOME/scratch/outputs/MARA
```

If the active dataset has many small files:

```bash
mkdir -p ~/fastscratch/datasets/MARA
rsync -avP ~/data/datasets/MARA/ ~/fastscratch/datasets/MARA/
DATA_DIR=$HOME/fastscratch/datasets/MARA
```

Important original data must still have a copy in `data` or an external backup.

## IDE Source Control Scanning

`pre-commit` hook caches and some downloaded datasets contain their own `.git`
directories. They are not MARA source repositories and must not be treated as
project changes.

If the IDE workspace is opened at `~/scratch` instead of directly at
`~/scratch/projects/MARA`, configure the local workspace settings to avoid
scanning generated/cache/data repositories:

```json
{
  "git.autoRepositoryDetection": "openEditors",
  "git.ignoredRepositories": [
    "/users/tbczhang/scratch/pre-commit-cache",
    "/mnt/scratch/users/tbczhang/pre-commit-cache",
    "/users/tbczhang/scratch/datasets",
    "/mnt/scratch/users/tbczhang/datasets"
  ],
  "files.watcherExclude": {
    "**/pre-commit-cache/**": true,
    "**/datasets/**/.git/**": true
  },
  "search.exclude": {
    "**/pre-commit-cache": true,
    "**/datasets/**/.git": true
  }
}
```

For this workspace, open:

```text
~/scratch/mara-dev.code-workspace
```

That multi-root workspace exposes `scratch`, `MARA`, `fastscratch`, and `data`
in the VS Code Explorer while keeping generated hook caches and dataset
repositories out of Source Control auto-discovery.

## Required Environment Variables

Interactive shells and automation must keep these variables on `fastscratch`:

```bash
export XDG_CACHE_HOME=$HOME/fastscratch/cache
export XDG_CONFIG_HOME=$HOME/fastscratch/cache/xdg-config
export XDG_DATA_HOME=$HOME/fastscratch/cache/xdg-data
export PIP_CACHE_DIR=$HOME/fastscratch/cache/pip
export UV_CACHE_DIR=$HOME/fastscratch/cache/uv
export UV_NO_CACHE=1
export UV_PYTHON_INSTALL_DIR=$HOME/fastscratch/python
export PRE_COMMIT_HOME=$HOME/scratch/pre-commit-cache
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

`UV_NO_CACHE=1` is required on this inode-constrained host. Keep
`UV_CACHE_DIR` on `fastscratch` as the canonical compatibility path, but make
normal `uv` operations use a temporary cache that is removed when the command
finishes. This prevents dependency installs and validation worktrees from
recreating more than 150,000 shared-cache entries. `UV_PYTHON_INSTALL_DIR`
remains persistent on `fastscratch`.

Also set `no-cache = true` in the user-level `uv.toml`. Keep the default
`~/.config/uv/uv.toml` as a symlink to the file under `XDG_CONFIG_HOME`, and
keep the default `~/.cache/uv` and `~/.local/share/uv` paths as symlinks to
their canonical `fastscratch` locations. This covers non-interactive tools
that do not source `.bashrc` and prevents a second cache or tool tree under
home.

`flowsettings.py` must respect `KH_APP_DATA_DIR` so app initialization,
DocQA indexing, graph caches, uploaded files, and SQLite state stay in
`fastscratch`.

Packaged TheFlow progress storage must resolve under the platform runtime cache,
never under the source checkout as `.theflow`. Pytest must set
`THEFLOW_SETTINGS_MODULE=ktem.default_flowsettings` and a session-owned
`THEFLOW_TEMP_PATH`; the session cleanup then removes per-component progress and
cache files instead of leaking them into `scratch` or `fastscratch`.

## Preflight Check

Run this check before large development sessions, dependency installs, model
downloads, `MARA app init`, DocQA indexing, dataset syncs, Slurm jobs, or
model-serving work:

```bash
cd ~/scratch/projects/MARA
source ~/.bashrc

ls -ld .venv
readlink -f .venv
readlink -f .venv/bin/python
df -h .venv ktem_app_data

printf 'UV_CACHE_DIR=%s\n' "$UV_CACHE_DIR"
printf 'UV_NO_CACHE=%s\n' "$UV_NO_CACHE"
printf 'UV_PYTHON_INSTALL_DIR=%s\n' "$UV_PYTHON_INSTALL_DIR"
printf 'PRE_COMMIT_HOME=%s\n' "$PRE_COMMIT_HOME"
printf 'HF_HOME=%s\n' "$HF_HOME"
printf 'TIKTOKEN_CACHE_DIR=%s\n' "$TIKTOKEN_CACHE_DIR"
printf 'CODEX_HOME=%s\n' "$CODEX_HOME"
printf 'KH_APP_DATA_DIR=%s\n' "$KH_APP_DATA_DIR"

lfs quota -h -u tbczhang /mnt/fastscratch
quota -s

test ! -e data
test ! -e datasets
test ! -e outputs
test ! -e .theflow
```

The correct `.venv` result is a symlink that resolves to:

```text
/mnt/fastscratch/users/tbczhang/envs/mara
```

Stop before running `uv`, `pip`, tests, `MARA app init`, dataset syncs, Slurm
jobs, or model setup if:

- `.venv` is a real directory instead of a symlink.
- Any cache or runtime environment variable except `PRE_COMMIT_HOME` points to
  `scratch` or home.
- `UV_NO_CACHE` is not `1`; a single dependency operation can otherwise
  recreate enough shared-cache entries to exceed the `fastscratch` file soft
  quota.
- `lfs quota` shows `fastscratch` file usage above the soft quota.
- `PRE_COMMIT_HOME` is unset when running pre-commit; without it, hook
  environments can consume tens of thousands of files under `fastscratch`.
- Dataset source paths point into the Git repository.
- A Slurm job would read or write directly under `~/data`.
- Experiment outputs would be written to `data`, home, `/tmp`, or
  `~/localscratch` as their only copy.

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
data
data/
datasets
datasets/
outputs
outputs/
.mypy_cache/
.pytest_cache/
__pycache__/
```

The no-slash entries intentionally cover symlinks such as `.venv` and
`ktem_app_data`; the slash entries cover real directories if one is accidentally
created.
