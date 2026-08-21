#!/bin/bash
#SBATCH --job-name=massnet-masks
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=bigbatch
#SBATCH --time=00:10:00
#SBATCH --mem=2G
#SBATCH --output=logs/massnet-masks-%j.out
#SBATCH --error=logs/massnet-masks-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
DATA_DIR="/datasets/zsuliman/msi_data/gbm_massnet"

echo "=========================================="
echo "       CREATE MASSNET GBM MASKS"
echo "=========================================="
echo "Date: $(date)"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Input: $DATA_DIR"
echo

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate data_tools_env

echo "Environment: $CONDA_DEFAULT_ENV"
python --version
echo

cd "$PROJECT_ROOT"
python -u scripts/create_massnet_gbm_masks.py --input-dir "$DATA_DIR"

echo
echo "Created masks:"
find "$DATA_DIR/masks" -maxdepth 1 -type f -name '*_mask.npy' -printf '%f\n' | sort
