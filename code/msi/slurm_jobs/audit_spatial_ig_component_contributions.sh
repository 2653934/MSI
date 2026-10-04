#!/bin/bash
#SBATCH --job-name=ig-parts
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/ig-parts-%j.out
#SBATCH --error=logs/ig-parts-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
export MKL_NUM_THREADS=2

for dataset in 160TopL GBM22_2; do
    case "$dataset" in
        160TopL)
            input=/datasets/zsuliman/msi_data/cac_msipl/160TopL.h5
            count=210 ;;
        GBM22_2)
            input=/datasets/zsuliman/msi_data/gbm_massnet/GBM22_2.h5
            count=464 ;;
    esac
    root="results/experiments/spatial_attention_context/${dataset}_seed1"
    output="results/diagnostics/spatial_ig_component_ablation/$dataset"
    echo "=== $dataset: frozen IG ranking contributions ==="
    python -u scripts/audit_spatial_ig_component_contributions.py \
        --input "$input" \
        --real-attribution "$root/real_attention/attribution" \
        --shuffled-attribution "$root/shuffled_attention/attribution" \
        --matched-count "$count" \
        --output "$output"
done
