#!/bin/bash
# Overnight item 3, step 1 (supervisor chat 2026-10-16 22:07): stage the 8 RCC exports
# for S3PL (byte-checked copies <run>.h5 and masks/<run>_mask.npy in
# /datasets/zsuliman/msi_data/rcc_s3pl/, the GBM folder layout) and run the adapter
# gate: S3PL's own create_pearson_labels must reproduce our |R@0.5| for all 8 runs.
# CPU only, one task. No training. Exit 4 if the gate fails.
#SBATCH --job-name=s3pl-rcc-gate
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=logs/s3pl-rcc-gate-%j.out
#SBATCH --error=logs/s3pl-rcc-gate-%j.err

set -euo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/rcc_sections.sh"
RUNS=()
for section in "${RCC_SECTIONS[@]}"; do RUNS+=("${section#RCC_}"); done
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "=== S3PL RCC adapter gate on ${SLURMD_NODENAME:-unknown} (job ${SLURM_JOB_ID}) ==="
"$PYTHON" -u scripts/check_s3pl_rcc_labels.py \
    --source-dir "$RCC_DATA_DIR" --staging-dir /datasets/zsuliman/msi_data/rcc_s3pl \
    --budget-root "$PROJECT_ROOT/results/experiments/rcc_spatial_msipl" \
    --runs "${RUNS[@]}" --stage \
    --output "$PROJECT_ROOT/results/validation/s3pl_rcc_adapter_gate/gate.json" \
    > "$PROJECT_ROOT/logs/s3pl-rcc-gate-${SLURM_JOB_ID}.detail.log"
tail -1 "$PROJECT_ROOT/logs/s3pl-rcc-gate-${SLURM_JOB_ID}.detail.log"
