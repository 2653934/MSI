#!/bin/bash
#SBATCH --job-name=massnet-inspect
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=bigbatch
#SBATCH --time=00:15:00
#SBATCH --mem=4G
#SBATCH --output=logs/massnet-inspect-%j.out
#SBATCH --error=logs/massnet-inspect-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
DATA_DIR="/datasets/zsuliman/msi_data/gbm_massnet"

echo "=========================================="
echo "       MASSNET GBM INSPECTION"
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
python -c "import h5py, numpy; print('h5py:', h5py.__version__); print('NumPy:', numpy.__version__)"
echo

cd "$PROJECT_ROOT"
python scripts/inspect_massnet_gbm.py --input-dir "$DATA_DIR"
