#!/bin/bash
# Login-node submitter for item C2 (S3PL 100 epochs): file checks, mkdir and sbatch only.
#   bash slurm_jobs/submit_s3pl_e100.sh [--concurrency N] [--indices LIST]
# Default: pilot 160TopL (index 9, a few minutes), then the other 15 afterok.
set -euo pipefail
cd "$HOME/msi"
concurrency=8
indices=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --concurrency) concurrency="${2:?}"; shift 2 ;;
        --indices) indices="${2:?}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
runner=slurm_jobs/run_s3pl_e100.sh
bash -n "$runner"
exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
[[ -n "$exclude" ]] || { echo "CUDA quarantine list is empty; inspect first." >&2; exit 1; }
root="reproducibility/s3pl_e100/seed1_released"
mkdir -p "$root/checkpoints/baselines/s3pl" "$root/logs/s3pl" "$root/results/baselines/s3pl" \
         "$root/run_logs" "$root/provenance" logs
if [[ ! -f "$root/provenance/manifest.txt" ]]; then
    {
        echo "purpose=item C2: S3PL 100 epochs, seed 1, released RNG path (supervisor chat 2026-10-15)"
        echo "random_seed=1; initialization_seed and sample_order_seed unset (released path)"
        echo "patch_size=9 CAC, 3 GBM; epochs=100; checkpoints=10,25,50,100; normalization=reference_spatial_max"
        echo "evaluation=after training; default count, plus matched count on CAC"
        echo "excluded_nodes=$exclude"
        echo "created_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    } > "$root/provenance/manifest.txt"
fi
if [[ -n "$indices" ]]; then
    job="$(sbatch --parsable --exclude="$exclude" --array="${indices}%$concurrency" "$runner")"
    echo "${job%%;*} indices=$indices" | tee -a "$root/provenance/slurm_job_ids.txt"
    exit 0
fi
if compgen -G "$root/checkpoints/baselines/s3pl/*.pt" > /dev/null; then
    echo "e100 checkpoints already exist; use --indices for missing tasks only." >&2
    exit 1
fi
pilot="$(sbatch --parsable --exclude="$exclude" --array=9 "$runner")"
pilot_id="${pilot%%;*}"
rest="$(sbatch --parsable --exclude="$exclude" --dependency="afterok:${pilot_id}" \
    --array="0-8,10-15%$concurrency" "$runner")"
echo "$pilot_id pilot 160TopL (task 9)" | tee -a "$root/provenance/slurm_job_ids.txt"
echo "${rest%%;*} remaining 15 tasks (afterok:$pilot_id)" | tee -a "$root/provenance/slurm_job_ids.txt"
