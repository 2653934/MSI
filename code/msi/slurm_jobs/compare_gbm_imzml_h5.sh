#!/bin/bash
#SBATCH --job-name=gbm-format-check
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --mem=8G
#SBATCH --output=logs/gbm-format-check-%j.out
#SBATCH --error=logs/gbm-format-check-%j.err

# Conda's MKL activation hook reads variables that may be unset. Keep strict
# error and pipeline handling, but do not enable Bash nounset for this job.
set -eo pipefail

PROJECT_ROOT="$HOME/msi"
IMZML_ROOT="/datasets/zsuliman/msi_data/gbm_imzml"
H5_ROOT="/datasets/zsuliman/msi_data/gbm_massnet"
OUTPUT="$PROJECT_ROOT/results/validation/gbm_imzml_h5/comparison.json"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env

echo "=========================================="
echo "       GBM IMZML/HDF5 COMPARISON"
echo "=========================================="
echo "Date: $(date)"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "imzML: $IMZML_ROOT"
echo "HDF5: $H5_ROOT"
echo

cd "$PROJECT_ROOT"
python scripts/compare_gbm_imzml_h5.py \
    --imzml-root "$IMZML_ROOT" \
    --h5-root "$H5_ROOT" \
    --output "$OUTPUT"
