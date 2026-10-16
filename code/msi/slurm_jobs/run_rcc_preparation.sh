#!/bin/bash
# RCC step 1 (protocol 18 Section 6.1, item D step 2): per run, the budget
# K_bin = |R@0.4| over all three classes, then the unchanged P1/P3 structural
# audit. CPU only, one array task per run (0-7). No training, no method scores.
# Both scripts check provenance before skipping and refuse stale outputs (exit 3).
#   sbatch --array=0-7 slurm_jobs/run_rcc_preparation.sh   (via submit_rcc.sh prep)
# Resources: the GBM/CAC partition audit peaked at 215 MB; the budget loads one
# PCC vector per class (3 x 10,200 floats). RCC runs are 972-3,564 px x 10,200 bins.
#SBATCH --job-name=rcc-prep
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=logs/rcc-prep-%A_%a.out
#SBATCH --error=logs/rcc-prep-%A_%a.err

set -euo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/rcc_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_rcc.sh}"
if (( TASK_ID < 0 || TASK_ID >= ${#RCC_SECTIONS[@]} )); then
    echo "Invalid array index: $TASK_ID" >&2; exit 2
fi
DATASET="${RCC_SECTIONS[TASK_ID]}"
INPUT="$(rcc_input_for "$DATASET")"
BUDGET="$PROJECT_ROOT/results/experiments/rcc_spatial_msipl/${DATASET}_seed1/reference_budget.json"
AUDIT="$PROJECT_ROOT/results/diagnostics/peak_partition_audit_rcc/$DATASET"
[ -f "$INPUT" ] || { echo "Missing input: $INPUT" >&2; exit 1; }
mkdir -p "$(dirname "$BUDGET")" "$AUDIT"

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "=== $DATASET RCC preparation on ${SLURMD_NODENAME:-unknown} (job ${SLURM_ARRAY_JOB_ID}_${TASK_ID}) ==="

# shellcheck disable=SC2086
"$PYTHON" -u scripts/compute_reference_budget.py --input "$INPUT" --output "$BUDGET" \
    --descriptive-class-subset $RCC_SENSITIVITY_CLASSES --chunk-size 1024 \
    > "$(dirname "$BUDGET")/reference_budget_stdout.log"
echo "budget: $(grep -o '"status": "[a-z]*"' "$BUDGET" | head -1)"
"$PYTHON" -u scripts/audit_peak_partitions.py --input "$INPUT" --output "$AUDIT" \
    --chunk-size 2048 > "$AUDIT/audit_stdout.log"
echo "partition audit: $(grep -o '"status": "[a-z]*"' "$AUDIT/summary.json" | head -1)"
