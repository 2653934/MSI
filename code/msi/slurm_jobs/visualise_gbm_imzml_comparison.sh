#!/bin/bash
#SBATCH --job-name=gbm-imzml-vis
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=01:00:00
#SBATCH --mem=4G
#SBATCH --output=logs/gbm-imzml-vis-%j.out
#SBATCH --error=logs/gbm-imzml-vis-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
H5_ROOT="/datasets/zsuliman/msi_data/gbm_massnet"
OFFICIAL_ROOT="/datasets/zsuliman/msi_data/gbm_imzml"
OUTPUT_DIR="$PROJECT_ROOT/results/visualisations/gbm_imzml_comparison"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate data_tools_env

echo "=========================================="
echo "       GBM REPRESENTATION VISUALS"
echo "=========================================="
echo "Date: $(date)"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Official input: $OFFICIAL_ROOT"
echo "HDF5 input: $H5_ROOT"
echo "Output: $OUTPUT_DIR"
echo

cd "$PROJECT_ROOT"
python -u scripts/visualise_gbm_imzml_comparison.py \
    --h5-root "$H5_ROOT" \
    --official-root "$OFFICIAL_ROOT" \
    --output-dir "$OUTPUT_DIR" \
    --chunk-size 2048

echo
echo "Generated files:"
find "$OUTPUT_DIR" -maxdepth 2 -type f -printf '%P\n' | sort

