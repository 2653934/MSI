#!/bin/bash
# Login-node submitter for Test N (protocol 18 Section 6.5): file checks, mkdir and
# sbatch only. Each submission needs Zayd's OK.
#   bash slurm_jobs/submit_s3pl_cac_shuffle_control.sh [--indices LIST] [--concurrency N]
# Default: all 16 tasks (0-7 seed 1, 8-15 seed 2), at most 2 running (the bigbatch
# QOS of 6 running is shared with Test R). The CUDA quarantine is passed with
# sbatch --exclude (Slurm does not read SBATCH_EXCLUDE).
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
runner=slurm_jobs/run_s3pl_cac_shuffle_control.sh
bash -n "$runner"
exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
if [[ -z "$exclude" ]]; then
    echo "CUDA quarantine list is empty; inspect before submission." >&2
    exit 1
fi
base=reproducibility/s3pl_cac_shuffle_control
# Shared folders are created here, before any array task starts (mkdir race).
for root in "$base/seed1_released" "$base/seed2_init2_order1"; do
    mkdir -p "$root/checkpoints/baselines/s3pl" "$root/logs/s3pl" \
             "$root/results/baselines/s3pl" "$root/run_logs"
done
mkdir -p "$base/provenance" logs
if [[ ! -f "$base/provenance/manifest.txt" ]]; then
    {
        echo "purpose=Test N, S3PL CAC retrained with shuffled nonlocal neighbours (protocol 18 Section 6.5; supervisor chat 2026-10-17 13:04)"
        echo "input_context_mode=shuffle_nonlocal (training and inference); neighbour map seed 1701; centre real; target = input patch"
        echo "seed1=tasks 0-7, released code path (global RNG, random_seed 1)"
        echo "seed2=tasks 8-15, initialization_seed 2, sample_order_seed 1, random_seed 1"
        echo "patch_size=9 epochs=10 batch=16 lr=1e-2 normalization=reference_spatial_max peaks_per_spectral_patch=256"
        echo "matched_counts=40TopL:315,160TopL:210,200TopL:221,240TopL:255,280TopL:245,360TopL:247,400TopL:133,520TopL:232"
        echo "excluded_nodes=$exclude"
        echo "created_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    } > "$base/provenance/manifest.txt"
fi
job="$(sbatch --parsable --exclude="$exclude" --array="${indices}%${concurrency}" "$runner")"
echo "${job%%;*} indices=$indices concurrency=$concurrency" | tee -a "$base/provenance/slurm_job_ids.txt"
