#!/bin/bash
#SBATCH --job-name=cac-ref-audit
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=01:00:00
#SBATCH --mem=8G
#SBATCH --output=logs/cac-ref-audit-%j.out
#SBATCH --error=logs/cac-ref-audit-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
OUTPUT="$PROJECT_ROOT/results/comparisons/s3pl_cac_gap_diagnostics/reference_set_audit.json"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export OMP_NUM_THREADS=2

printf 'Job: %s\nNode: %s\nStart UTC: %s\n' \
    "$SLURM_JOB_ID" "$(hostname)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python -m py_compile scripts/audit_s3pl_cac_reference_sets.py
python -u scripts/audit_s3pl_cac_reference_sets.py \
    --project-root "$PROJECT_ROOT" \
    --h5-root /datasets/zsuliman/msi_data/cac_msipl \
    --s3pl-label-root /datasets/zsuliman/msi_data/cac/labels \
    --output "$OUTPUT"
