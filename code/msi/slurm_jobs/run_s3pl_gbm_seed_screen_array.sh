#!/bin/bash
#SBATCH --job-name=s3pl-gbm-seeds
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --output=logs/s3pl-gbm-seeds-%A_%a.out
#SBATCH --error=logs/s3pl-gbm-seeds-%A_%a.err

set -euo pipefail

datasets=(
    GBM108_negative
    GBM12_1
    GBM12_2
    GBM22_1
    GBM22_2
    GBM39_1
    GBM39_2
)
task_id="${SLURM_ARRAY_TASK_ID:?This script must run as a Slurm array task}"
if (( task_id < 0 || task_id >= 21 )); then
    echo "Array index must be between 0 and 20: $task_id" >&2
    exit 2
fi

dataset="${datasets[$((task_id / 3))]}"
init_seed=$((task_id % 3 + 1))
order_seed=1
project_root="$HOME/msi"
root="$project_root/reproducibility/s3pl_massnet/${dataset}_p3_rng_init${init_seed}_order${order_seed}"
training_name="${dataset}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_3"
metrics="$root/results/baselines/s3pl/$training_name/metrics.json"

if [[ -f "$metrics" ]]; then
    echo "$dataset initialization $init_seed is already complete; leaving it unchanged."
    exit 0
fi

mkdir -p "$root/provenance"
if [[ ! -f "$root/provenance/manifest.txt" ]]; then
    {
        echo "purpose=three-seed S3PL screen across remaining GBM sections"
        echo "dataset=$dataset"
        echo "initialization_seed=$init_seed"
        echo "sample_order_seed=$order_seed"
        echo "random_seed=1"
        echo "patch_size=3"
        echo "epochs=10"
        echo "normalization=reference_spatial_max"
        echo "peaks_per_spectral_patch=256"
        echo "created_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    } > "$root/provenance/manifest.txt"
fi
echo "${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}" >> "$root/provenance/slurm_job_ids.txt"

echo "Running $dataset with initialization $init_seed and fixed sample order $order_seed"
bash "$project_root/slurm_jobs/run_s3pl_massnet_gbm.sh" \
    "$dataset" 10 true 3 "$root" reference_spatial_max 1 \
    "$init_seed" "$order_seed"
