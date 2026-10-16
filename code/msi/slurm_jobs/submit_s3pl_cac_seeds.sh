#!/bin/bash
# Login-node submitter for overnight item 2 (S3PL CAC seeds 2 and 3): file checks,
# mkdir and sbatch only.
#   bash slurm_jobs/submit_s3pl_cac_seeds.sh [--indices LIST] [--concurrency N]
# Default: all 16 tasks (0-7 seed 2, 8-15 seed 3), at most 2 running.
set -euo pipefail
cd "$HOME/msi"
concurrency=2
indices="0-15"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --concurrency) concurrency="${2:?}"; shift 2 ;;
        --indices) indices="${2:?}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
runner=slurm_jobs/run_s3pl_cac_seeds.sh
bash -n "$runner"
exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
[[ -n "$exclude" ]] || { echo "CUDA quarantine list is empty; inspect first." >&2; exit 1; }
for seed in 2 3; do
    root="reproducibility/s3pl_cac_seeds/seed${seed}_released"
    mkdir -p "$root/checkpoints/baselines/s3pl" "$root/logs/s3pl" "$root/results/baselines/s3pl" \
             "$root/run_logs" "$root/provenance"
    if [[ ! -f "$root/provenance/manifest.txt" ]]; then
        {
            echo "purpose=overnight item 2: S3PL CAC, released settings, native counts (supervisor chat 2026-10-16 22:07)"
            echo "random_seed=$seed; initialization_seed and sample_order_seed unset (released path)"
            echo "settings=config.json defaults (patch 9, 256 peaks/patch, d1 51, d2 1, 10 epochs, batch 16, lr 1e-2, reference_spatial_max)"
            echo "excluded_nodes=$exclude"
            echo "created_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
        } > "$root/provenance/manifest.txt"
    fi
done
mkdir -p logs reproducibility/s3pl_cac_seeds/provenance
job="$(sbatch --parsable --exclude="$exclude" --array="${indices}%${concurrency}" "$runner")"
echo "${job%%;*} indices=$indices" | tee -a reproducibility/s3pl_cac_seeds/provenance/slurm_job_ids.txt
