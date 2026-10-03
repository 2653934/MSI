#!/bin/bash
#SBATCH --job-name=context-info
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=02:00:00
#SBATCH --output=logs/context-info-%j.out
#SBATCH --error=logs/context-info-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2

python -m unittest discover -s src/spatial_msipl/tests -p test_spatial_context_information.py

OUTPUT_DIR="results/diagnostics/spatial_context_information"
for dataset in 160TopL 200TopL GBM22_2 GBM39_2; do
    if [[ "$dataset" == *TopL ]]; then
        input="/datasets/zsuliman/msi_data/cac_msipl/${dataset}.h5"
    else
        input="/datasets/zsuliman/msi_data/gbm_massnet/${dataset}.h5"
    fi
    metadata="results/experiments/spatial_msipl_window_pilot/${dataset}_seed1/shuffled_p3/metadata.json"
    if [[ ! -f "$input" || ! -f "$metadata" ]]; then
        echo "Missing input or shuffled-run metadata for $dataset" >&2
        exit 1
    fi
    echo "=== $dataset: real versus seeded shuffled 3x3 input ==="
    python -u scripts/audit_spatial_context_information.py \
        --input "$input" \
        --shuffled-metadata "$metadata" \
        --output-dir "$OUTPUT_DIR" \
        --per-class 64
done
