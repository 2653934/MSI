#!/bin/bash
# Four-run diagnostic: separate the effect of initial weights from sample order.
set -euo pipefail

project_root="$HOME/msi"
cd "$project_root"
runner="slurm_jobs/run_s3pl_massnet_gbm.sh"
bash -n "$runner" slurm_jobs/submit_s3pl_gbm_positive_seed_factors.sh \
    slurm_jobs/check_s3pl_gbm_positive_seed_factors.sh

exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' \
    slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
if [[ -z "$exclude" ]]; then
    echo "CUDA quarantine list is empty; inspect before submission." >&2
    exit 1
fi

# Check all output namespaces before creating or submitting any of them.
for init_seed in 1 2; do
    for order_seed in 1 2; do
        root="$project_root/reproducibility/s3pl_massnet/GBM108_positive_p3_rng_init${init_seed}_order${order_seed}"
        if [[ -e "$root" ]]; then
            echo "Artifact root already exists; refusing to overwrite: $root" >&2
            exit 1
        fi
    done
done

printf '%-9s %-9s %-8s %s\n' INIT_SEED ORDER_SEED JOB_ID ARTIFACT_ROOT
canary_job=""
for init_seed in 1 2; do
    for order_seed in 1 2; do
        root="$project_root/reproducibility/s3pl_massnet/GBM108_positive_p3_rng_init${init_seed}_order${order_seed}"
        mkdir -p "$root/provenance"
        {
            echo "purpose=GBM108_positive S3PL two-factor seed diagnostic"
            echo "initialization_seed=$init_seed"
            echo "sample_order_seed=$order_seed"
            echo "random_seed=1"
            echo "patch_size=3"
            echo "epochs=10"
            echo "normalization=reference_spatial_max"
            echo "peaks_per_spectral_patch=256"
            echo "created_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
        } > "$root/provenance/manifest.txt"
        dependency_flags=()
        if [[ -n "$canary_job" ]]; then
            dependency_flags=(--dependency="afterok:$canary_job")
        fi
        submission="$(sbatch --parsable --exclude="$exclude" --exclusive --time=02:00:00 \
            "${dependency_flags[@]}" \
            "$runner" GBM108_positive 10 true 3 "$root" reference_spatial_max 1 \
            "$init_seed" "$order_seed")"
        job_id="${submission%%;*}"
        if [[ -z "$canary_job" ]]; then
            canary_job="$job_id"
        fi
        echo "$job_id" > "$root/provenance/slurm_job_id.txt"
        printf '%-9s %-9s %-8s %s\n' "$init_seed" "$order_seed" "$job_id" "$root"
    done
done

echo "Submitted one (1,1) canary, then three dependent two-factor diagnostic runs."
echo "If the canary fails, its dependents will not run; inspect its log before retrying."
echo "These runs do not replace the released-code seed results."
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R"'
