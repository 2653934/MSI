#!/bin/bash
# Gate (d) pixel-count decision table from the four evaluations (protocol 18 Section 6).
#   sbatch slurm_jobs/run_gate_d_summary.sh
#SBATCH --job-name=gate-d-summary
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:10:00
#SBATCH --output=logs/gate-d-summary-%j.out
#SBATCH --error=logs/gate-d-summary-%j.err

set -euo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch}"
PROJECT_ROOT="$HOME/msi"
ROOT="$PROJECT_ROOT/results/diagnostics/gate_d_pixel_counts"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
"$HOME/miniconda3/envs/s3pl_env/bin/python" -u scripts/summarise_gate_d_pixel_counts.py \
    --root "$ROOT" --output "$ROOT/summary_${SLURM_JOB_ID}"
