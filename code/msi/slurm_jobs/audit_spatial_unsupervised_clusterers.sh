#!/bin/bash
#SBATCH --job-name=latent-clusterers
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=logs/latent-clusterers-%j.out
#SBATCH --error=logs/latent-clusterers-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
export MKL_NUM_THREADS=2

python -m unittest discover -s src/spatial_msipl/tests -p test_spatial_unsupervised_clusterers.py

for dataset in 160TopL GBM22_2; do
    if [[ "$dataset" == *TopL ]]; then
        input="/datasets/zsuliman/msi_data/cac_msipl/${dataset}.h5"
        real="results/experiments/spatial_msipl_cac_gmm_integrated_gradients/${dataset}_seed1/uniform_mean"
    else
        input="/datasets/zsuliman/msi_data/gbm_massnet/${dataset}.h5"
        real="results/experiments/spatial_msipl_gmm_integrated_gradients/${dataset}_seed1/uniform_mean"
    fi
    shuffled="results/experiments/spatial_msipl_window_pilot/${dataset}_seed1/shuffled_p3/attribution"
    for path in "$input" "$real/latent_mean.npy" "$shuffled/latent_mean.npy"; do
        if [[ ! -f "$path" ]]; then
            echo "Missing prerequisite: $path" >&2
            exit 1
        fi
    done
    echo "=== $dataset: predeclared unsupervised clusterers ==="
    python -u scripts/audit_spatial_unsupervised_clusterers.py \
        --input "$input" \
        --real-attribution "$real" \
        --shuffled-attribution "$shuffled" \
        --output "results/diagnostics/spatial_unsupervised_clusterers/${dataset}.json"
done
