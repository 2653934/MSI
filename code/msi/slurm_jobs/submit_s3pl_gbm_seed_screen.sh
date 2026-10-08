#!/bin/bash
# Submit only incomplete three-seed S3PL GBM screening configurations.
set -euo pipefail

project_root="$HOME/msi"
cd "$project_root"
worker="slurm_jobs/run_s3pl_gbm_seed_screen_array.sh"
checker="slurm_jobs/check_s3pl_gbm_seed_screen.sh"
bash -n "$worker" "$checker" slurm_jobs/submit_s3pl_gbm_seed_screen.sh

exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' \
    slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
if [[ -z "$exclude" ]]; then
    echo "CUDA quarantine list is empty; inspect before submission." >&2
    exit 1
fi

datasets=(
    GBM108_negative
    GBM12_1
    GBM12_2
    GBM22_1
    GBM22_2
    GBM39_1
    GBM39_2
)
missing=()
for task_id in {0..20}; do
    dataset="${datasets[$((task_id / 3))]}"
    init_seed=$((task_id % 3 + 1))
    root="$project_root/reproducibility/s3pl_massnet/${dataset}_p3_rng_init${init_seed}_order1"
    training_name="${dataset}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_3"
    metrics="$root/results/baselines/s3pl/$training_name/metrics.json"
    if [[ ! -f "$metrics" ]]; then
        missing+=("$task_id")
    fi
done

if (( ${#missing[@]} == 0 )); then
    echo "All 21 remaining-section seed-screen configurations are already complete."
    exit 0
fi

indices="$(IFS=,; echo "${missing[*]}")"
submission="$(sbatch --parsable --exclude="$exclude" --array="${indices}%6" "$worker")"
job_id="${submission%%;*}"
echo "Submitted seed-screen array $job_id with ${#missing[@]} incomplete configurations."
echo "At most six tasks run simultaneously; pending tasks start automatically."
echo "Array indices: $indices"
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R"'
echo "Audit with: bash $checker"
