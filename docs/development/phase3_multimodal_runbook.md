# Phase3 Multimodal Runbook

This runbook is the reproducible path for the Phase3 multimodal closure runs.
It keeps model serving, benchmark outputs, and logs out of the Git checkout.

## Scope

The Phase3 Slurm run is meant to produce three pieces of evidence in one
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

## Submit Slurm Job

Create the Slurm log directory before `sbatch`; Slurm opens stdout before the
script body runs.

```bash
cd /mnt/scratch/users/tbczhang/projects/MARA
mkdir -p /mnt/scratch/users/tbczhang/outputs/MARA/slurm
sbatch scripts/slurm/phase3_multimodal_rerun.sbatch
```

The default run uses:

- Manifest:
  `/mnt/scratch/users/tbczhang/outputs/MARA/manifests/plan5/current-direct-fix-20260621/slidevqa-test-shard0.multimodal.routes.json`
- Output directory:
  `/mnt/scratch/users/tbczhang/outputs/MARA/phase3_multimodal_slurm`
- Route: `all`
- Limit: `20`
- Prompt policy: `gold_answer_v1`
- Thinking control: `--benchmark-no-think`
- Route timeout: `180` seconds

Useful overrides:

```bash
MARA_PHASE3_LIMIT=50 \
MARA_PHASE3_ROUTE_TIMEOUT_SECONDS=240 \
sbatch scripts/slurm/phase3_multimodal_rerun.sbatch
```

For sharded runs:

```bash
MARA_PHASE3_LIMIT=100 \
MARA_PHASE3_NUM_SHARDS=4 \
MARA_PHASE3_SHARD_INDEX=0 \
sbatch scripts/slurm/phase3_multimodal_rerun.sbatch
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
- GPU1: `serve_qwen3_vl_8b.sh`
- CPU by default: `serve_retrieval.sh`
- CPU by default: `serve_colvision.sh`

The VLM health gate must return `Qwen/Qwen3-VL-8B-Instruct` through
`/v1/models` before the benchmark starts.

For interactive checks on the current node:

```bash
tmux new-session -d -s mara-qwen3-vl-8001 \
  'cd /mnt/scratch/users/tbczhang/mara-hpc && CUDA_VISIBLE_DEVICES=1 ./serve_qwen3_vl_8b.sh'

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
run_dir=$(find /mnt/scratch/users/tbczhang/outputs/MARA/phase3_multimodal_slurm \
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
print("page_image", phase3["page_image"])
print("element", phase3["element"])
print("hybrid", phase3["hybrid"])
PY
```

Phase3 can only be considered closed after the artifact shows:

- `page_image.status` is `vlm_live` or an equivalent completed VLM status, with
  no skipped `page_image_rag_vlm` route.
- `element.status` is either `index_coverage_present` or a quantified coverage
  gap that can be explained in the thesis.
- `hybrid.status` is `question_type_breakdown_available` with route metrics by
  question type.
- The result comes from a larger-than-smoke sample, not only the limit-2 live
  proof.

Keep any residual answer duplication, route timeouts, or low-quality scores in
the final Phase3 summary instead of treating a completed job as a correctness
win.
