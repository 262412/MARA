#!/usr/bin/env bash
#SBATCH --job-name=mara-benchmark-synthesis
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00

set -euo pipefail

PROJECT_ROOT="${MARA_PROJECT_ROOT:?MARA_PROJECT_ROOT is required}"
PLAN="${MARA_EXECUTION_PLAN:?MARA_EXECUTION_PLAN is required}"
TABLE="${MARA_EXECUTION_TABLE:?MARA_EXECUTION_TABLE is required}"
OUTPUT_DIR="${MARA_SYNTHESIS_OUTPUT_DIR:?MARA_SYNTHESIS_OUTPUT_DIR is required}"
PYTHON="${MARA_PLAN_PYTHON:-python3}"

cd "$PROJECT_ROOT"
"$PYTHON" "${PROJECT_ROOT}/scripts/slurm/synthesize_benchmark_run.py" \
  --plan "$PLAN" \
  --table "$TABLE" \
  --output-dir "$OUTPUT_DIR" \
  --validator "${PROJECT_ROOT}/scripts/slurm/validate_benchmark_predictions.py" \
  --require-all-usable \
  --require-slurm-clean
