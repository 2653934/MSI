#!/bin/bash
set -euo pipefail

project_root="$HOME/msi"
cd "$project_root"
runner="slurm_jobs/run_s3pl_massnet_gbm.sh"
bash -n "$runner" slurm_jobs/submit_s3pl_gbm_p3_seed_probe.sh slurm_jobs/check_s3pl_gbm_p3_seed_probe.sh
exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
if [[ -z "$exclude" ]]; then
    echo "CUDA quarantine list is empty; inspect before submission." >&2
    exit 1
fi

datasets=(GBM108_positive GBM108_negative)
seeds=(2 3)
for dataset in "${datasets[@]}"; do
    for seed in "${seeds[@]}"; do
        root="$project_root/reproducibility/s3pl_massnet/${dataset}_p3_reference_spatial_max_seed${seed}"
        if [[ -e "$root" ]]; then
            echo "Artifact root already exists; refusing to overwrite: $root" >&2
            exit 1
        fi
    done
done

printf '%-18s %-6s %-8s %s\n' DATASET SEED JOB_ID ARTIFACT_ROOT
for dataset in "${datasets[@]}"; do
    for seed in "${seeds[@]}"; do
        root="$project_root/reproducibility/s3pl_massnet/${dataset}_p3_reference_spatial_max_seed${seed}"
        mkdir -p "$root/provenance"
        {
            echo "purpose=GBM S3PL released-code seed sensitivity probe"
            echo "dataset=$dataset"
            echo "random_seed=$seed"
            echo "patch_size=3"
            echo "epochs=10"
            echo "normalization=reference_spatial_max"
            echo "peaks_per_spectral_patch=256"
            echo "created_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
        } > "$root/provenance/manifest.txt"
        submission="$(sbatch --parsable --exclude="$exclude" --exclusive --time=02:00:00 \
            "$runner" "$dataset" 10 true 3 "$root" reference_spatial_max "$seed")"
        job_id="${submission%%;*}"
        echo "$job_id" > "$root/provenance/slurm_job_id.txt"
        printf '%-18s %-6s %-8s %s\n' "$dataset" "$seed" "$job_id" "$root"
    done
done

echo "Submitted four independent p=3 released-code runs (both GBM108 sections, seeds 2 and 3)."
echo "Monitor with: squeue -u \"\$USER\" -o '%.18i %.24j %.2t %.10M %.24R'"
