# Multimodal Route Runbook

This runbook is the reproducible path for multimodal route closure runs.
It keeps model serving, benchmark outputs, and logs out of the Git checkout.

## Scope

The multimodal Slurm run is meant to produce three pieces of evidence in one
artifact set:

- Page-image VLM route: `phase3_multimodal_summary.page_image`.
- Element coverage: `phase3_multimodal_summary.element`.
- Hybrid question-type analysis: `phase3_multimodal_summary.hybrid`.

It does not freeze thesis datasets or claim paper-grade external scores.

## Storage Preflight

Before submitting, run the standard MARA storage preflight from the repository:

```bash
cd /mnt/scratch/users/tbczhang/projects/MARA
ls -ld .venv
readlink -f .venv
readlink -f .venv/bin/python
df -h .venv ktem_app_data
lfs quota -h -u tbczhang /mnt/fastscratch
lfs quota -h -u tbczhang /mnt/scratch
quota -s
test ! -e data
test ! -e datasets
test ! -e outputs
```

Stop if `.venv` is not a symlink to fastscratch, if quota is above the soft
limit, or if repo-root `data/`, `datasets/`, or `outputs/` exists.

## Runtime Isolation

Every benchmark Slurm task must run with an isolated `KH_APP_DATA_DIR`. The
wrapper sources `scripts/slurm/benchmark_runtime_isolation.sh`, derives a
per-task runtime from the Slurm job and array ids, and refuses to run if the
runtime still points at the shared interactive app directory:

```text
/users/tbczhang/fastscratch/mara_runtime/ktem_app_data
```

This is a hard correctness boundary for full-system benchmark runs. Concurrent
benchmark shards must not write into the same shared Chroma collection, because
that can corrupt the local HNSW index and surface as Slurm `139:0` native
segfaults rather than Python exceptions. Text, visual, controller, hybrid, and
element rerun scripts generated for a final benchmark should either call this
wrapper or source the same helper before starting model services or invoking
`python -m benchmark run`.

The default isolated runtime shape is:

```text
/users/tbczhang/fastscratch/mara_runtime/benchmark_runs/<suite>/<slurm-task>/ktem_app_data
```

The wrapper logs `kh_app_data_dir=...` at job start. Treat a missing log line,
or a path ending exactly in `/mara_runtime/ktem_app_data`, as a failed
preflight and do not use that run for final thesis results.

## Submit Slurm Job

Create the Slurm log directory before `sbatch`; Slurm opens stdout before the
script body runs.

```bash
cd /mnt/scratch/users/tbczhang/projects/MARA
mkdir -p /mnt/scratch/users/tbczhang/outputs/MARA/slurm
sbatch scripts/slurm/multimodal_route_rerun.sbatch
```

The default run uses:

- Manifest:
  `/mnt/scratch/users/tbczhang/outputs/MARA/manifests/plan5/current-direct-fix-20260621/slidevqa-test-shard0.multimodal.routes.json`
- Output directory:
  `/mnt/scratch/users/tbczhang/outputs/MARA/multimodal_route_slurm`
- Route: `all`
- Limit: `20`
- Prompt policy: `gold_answer_v1`
- Thinking control: `--benchmark-no-think`
- Route timeout: `240` seconds
- VLM context: `MARA_VLM_MAX_MODEL_LEN=8192`

Useful overrides:

```bash
MARA_PHASE3_LIMIT=50 \
MARA_PHASE3_ROUTE_TIMEOUT_SECONDS=240 \
sbatch scripts/slurm/multimodal_route_rerun.sbatch
```

The older `MARA_PHASE3_*` variables are still accepted for compatibility. New
automation should prefer the descriptive `MARA_MULTIMODAL_*` names:

```bash
MARA_MULTIMODAL_LIMIT=50 \
MARA_MULTIMODAL_ROUTE_TIMEOUT_SECONDS=240 \
sbatch scripts/slurm/multimodal_route_rerun.sbatch
```

For sharded runs:

```bash
MARA_MULTIMODAL_LIMIT=100 \
MARA_MULTIMODAL_NUM_SHARDS=4 \
MARA_MULTIMODAL_SHARD_INDEX=0 \
sbatch scripts/slurm/multimodal_route_rerun.sbatch
```

## Backend Health

The Slurm wrapper checks these endpoints inside the allocation:

- Text LLM: `http://127.0.0.1:8000/v1/models`
- VLM: `http://127.0.0.1:8001/v1/models`
- Retrieval: `http://127.0.0.1:8002/health`
- ColVision: `http://127.0.0.1:8003/health`

If a backend is missing, the wrapper starts the local service from
`/mnt/scratch/users/tbczhang/mara-hpc`:

- GPU0: `serve_qwen3_8b.sh`
- GPU1: `serve_qwen3_vl_8b_4k.sh` with
  `MARA_VLM_MAX_MODEL_LEN=8192`
- CPU by default: `serve_retrieval.sh`
- GPU1 by default: `serve_colvision.sh` with `MARA_COLVISION_DEVICE=cuda:0`

The default 2-GPU L40S placement keeps the text LLM on GPU0 and shares VLM plus
ColVision on GPU1. The wrapper sets
`MARA_VLM_GPU_MEMORY_UTILIZATION=0.70` so the VLM server can start reliably
while ColVision is already resident on the same GPU. Override
`MARA_COLVISION_GPU`, `MARA_COLVISION_DEVICE`, and
`MARA_VLM_GPU_MEMORY_UTILIZATION` together when using a 3-GPU A100/H100
placement or a CPU-only diagnostic.

The VLM health gate must return `Qwen/Qwen3-VL-8B-Instruct` through
`/v1/models` before the benchmark starts. The wrapper sets
`MARA_VLM_MAX_MODEL_LEN=8192`; the historical `serve_qwen3_vl_8b_4k.sh` script
name is not the evidence boundary, the effective vLLM context setting is.

The productized health contract is:

```bash
python -m benchmark check-multimodal-backends \
  --output /mnt/scratch/users/tbczhang/outputs/MARA/multimodal_route_slurm/logs/manual/backend-health.json \
  --strict
```

The command writes `backend-health.json` with `schema_version`, `checked_at`,
`overall_status`, per-backend metadata, and a run-level failure taxonomy. The
taxonomy is for backend/run comparability, not answer scoring. Current failure
types include `unreachable`, `timeout`, `http_error`, `bad_json`,
`unexpected_payload`, `model_missing`, `health_not_ok`, `family_mismatch`,
`missing_device`, and `cpu_colvision`.
The Slurm wrapper saves this file under its run log directory and passes it to
`benchmark run` with `--backend-health-json`, so `summary.json` and `report.md`
record the backend state used by the rerun.
ColVision health includes the served `device` when the local ColVision server
reports it; MMDocRAG visual evidence should use `device=cuda:0`, not CPU
ColVision.

For interactive checks on the current node:

```bash
tmux new-session -d -s mara-qwen3-vl-8001 \
  'cd /mnt/scratch/users/tbczhang/mara-hpc && MARA_VLM_MAX_MODEL_LEN=8192 CUDA_VISIBLE_DEVICES=1 ./serve_qwen3_vl_8b_4k.sh'

python - <<'PY'
import json, urllib.request
with urllib.request.urlopen("http://127.0.0.1:8001/v1/models", timeout=2) as response:
    payload = json.load(response)
print([item.get("id") for item in payload.get("data", [])])
PY
```

## Evidence Review

After the job finishes, inspect the latest run directory:

```bash
run_dir=$(find /mnt/scratch/users/tbczhang/outputs/MARA/multimodal_route_slurm \
  -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)

python - "$run_dir" <<'PY'
import json
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
phase3 = summary["phase3_multimodal_summary"]
print("run_dir", run_dir)
print("num_examples", summary["num_examples"])
print("num_predictions", summary["num_predictions"])
print("num_skipped_routes", summary["num_skipped_routes"])
print("backend_health", summary.get("backend_health"))
print("backend_failure_taxonomy", summary.get("backend_failure_taxonomy"))
print("page_image", phase3["page_image"])
print("element", phase3["element"])
print("hybrid", phase3["hybrid"])
PY
```

The multimodal route workflow can only be considered closed after the artifact shows:

- `page_image.status` is `vlm_live` or an equivalent completed VLM status, with
  no skipped `page_image_rag_vlm` route.
- `element.status` is either `index_coverage_present` or a quantified coverage
  gap that can be explained in the thesis.
- `hybrid.status` is `question_type_breakdown_available` with route metrics by
  question type.
- The result comes from a larger-than-smoke sample, not only the limit-2 live
  proof.
- `backend_health.overall_status` is `ready`, or any blocked backend is recorded
  with an explicit failure taxonomy and excluded from quality claims.

Keep any residual answer duplication, route timeouts, or low-quality scores in
the final Phase3 summary instead of treating a completed job as a correctness
win.
