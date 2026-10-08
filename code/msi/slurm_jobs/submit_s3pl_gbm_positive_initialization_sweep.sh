#!/bin/bash
# Extend the controlled GBM108-positive initialization diagnostic to 10 seeds.
set -euo pipefail

project_root="$HOME/msi"
cd "$project_root"
runner="slurm_jobs/run_s3pl_massnet_gbm.sh"
bash -n "$runner" slurm_jobs/submit_s3pl_gbm_positive_initialization_sweep.sh \
    slurm_jobs/check_s3pl_gbm_positive_initialization_sweep.sh

exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' \
    slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
if [[ -z "$exclude" ]]; then
    echo "CUDA quarantine list is empty; inspect before submission." >&2
    exit 1
fi

training_name="GBM108_positive_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_3"
printf '%-10s %-10s %-8s %s\n' INIT_SEED ORDER_SEED JOB_ID STATUS
submitted=0
for init_seed in {3..10}; do
    order_seed=1
    root="$project_root/reproducibility/s3pl_massnet/GBM108_positive_p3_rng_init${init_seed}_order${order_seed}"
    metrics="$root/results/baselines/s3pl/$training_name/metrics.json"
    if [[ -f "$metrics" ]]; then
        printf '%-10s %-10s %-8s %s\n' "$init_seed" "$order_seed" - COMPLETE
        continue
    fi

    mkdir -p "$root/provenance"
    if [[ ! -f "$root/provenance/manifest.txt" ]]; then
        {
            echo "purpose=GBM108_positive S3PL initialization-seed sweep"
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

    submission="$(sbatch --parsable --exclude="$exclude" --exclusive --time=02:00:00 \
        --job-name="s3pl-init-${init_seed}" \
        "$runner" GBM108_positive 10 true 3 "$root" reference_spatial_max 1 \
        "$init_seed" "$order_seed")"
    job_id="${submission%%;*}"
    echo "$job_id" >> "$root/provenance/slurm_job_ids.txt"
    printf '%-10s %-10s %-8s %s\n' "$init_seed" "$order_seed" "$job_id" SUBMITTED
    submitted=$((submitted + 1))
done

echo "Submitted $submitted incomplete initialization runs; Slurm applies the account's concurrency limit."
echo "Seeds 1 and 2 reuse the completed two-factor diagnostic."
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R"'
echo "Audit with: bash slurm_jobs/check_s3pl_gbm_positive_initialization_sweep.sh"
