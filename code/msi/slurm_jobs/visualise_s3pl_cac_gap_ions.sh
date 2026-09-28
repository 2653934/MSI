#!/bin/bash
#SBATCH --job-name=cac-gap-ions
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --mem=8G
#SBATCH --output=logs/cac-gap-ions-%j.out
#SBATCH --error=logs/cac-gap-ions-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
H5_ROOT="/datasets/zsuliman/msi_data/cac_msipl"
OUTPUT="$PROJECT_ROOT/results/comparisons/s3pl_cac_gap_diagnostics"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export MPLBACKEND=Agg
export OMP_NUM_THREADS=2

printf 'Job: %s\nNode: %s\nStart UTC: %s\n' \
    "$SLURM_JOB_ID" "$(hostname)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python -m py_compile scripts/analyse_s3pl_cac_gap.py
python -u scripts/analyse_s3pl_cac_gap.py \
    --project-root "$PROJECT_ROOT" \
    --output "$OUTPUT" \
    --h5-root "$H5_ROOT" \
    --ion-sections 360TopL 520TopL
