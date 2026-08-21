#!/bin/bash
#SBATCH --job-name=massnet-vis
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=01:00:00
#SBATCH --mem=4G
#SBATCH --output=logs/massnet-vis-%j.out
#SBATCH --error=logs/massnet-vis-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
DATA_DIR="/datasets/zsuliman/msi_data/gbm_massnet"
OUTPUT_DIR="$PROJECT_ROOT/results/visualisations/gbm_massnet"

echo "=========================================="
echo "       MASSNET GBM VISUALISATION"
echo "=========================================="
echo "Date: $(date)"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Input: $DATA_DIR"
echo "Output: $OUTPUT_DIR"
echo

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate data_tools_env

echo "Environment: $CONDA_DEFAULT_ENV"
python --version
python -c "import h5py, matplotlib, numpy; print('h5py:', h5py.__version__); print('Matplotlib:', matplotlib.__version__); print('NumPy:', numpy.__version__)"
echo

cd "$PROJECT_ROOT"
python -u scripts/visualise_massnet_gbm.py \
    --data-dir "$DATA_DIR" \
    --output-dir "$OUTPUT_DIR" \
    --chunk-size 2048

echo
echo "Generated overview files:"
find "$OUTPUT_DIR" -maxdepth 1 -type f -printf '%f\n' | sort
