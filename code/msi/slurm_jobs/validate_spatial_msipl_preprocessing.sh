#!/bin/bash
#SBATCH --job-name=spatial-prep
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=00:20:00
#SBATCH --mem=4G
#SBATCH --output=logs/spatial-prep-%j.out
#SBATCH --error=logs/spatial-prep-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
OUTPUT="$PROJECT_ROOT/results/validation/spatial_msipl_preprocessing/GBM108_positive.json"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate data_tools_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

cd "$PROJECT_ROOT"
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/validate_spatial_msipl_preprocessing.py \
    --input "$INPUT" \
    --output "$OUTPUT"
