#!/bin/bash
# Login-node submitter for the S3PL CAC retrained-centre control, seed 2:
# file checks, mkdir and sbatch only (supervisor chat 2026-10-15, item 2).
#   bash slurm_jobs/submit_s3pl_cac_centre_control_seed2.sh [--concurrency N] [--indices LIST]
# Default: a 160TopL pilot (tasks 1 and 9, both arms), then the other 14 tasks
# after the pilot succeeds. --indices LIST resubmits only those tasks (for
# CUDA warm-up node failures; record the node in cluster_node_issues.txt first).
set -euo pipefail
cd "$HOME/msi"
concurrency=6
indices=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --concurrency) concurrency="${2:?}"; shift 2 ;;
        --indices) indices="${2:?}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
runner=slurm_jobs/run_s3pl_cac_centre_control_seed2.sh
bash -n "$runner"
exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
if [[ -z "$exclude" ]]; then
    echo "CUDA quarantine list is empty; inspect before submission." >&2
    exit 1
fi
root="reproducibility/s3pl_cac_centre_control/seed2_init2_order1"
# Shared folders are created here, before any array task starts.
mkdir -p "$root/checkpoints/baselines/s3pl" "$root/logs/s3pl" \
         "$root/results/baselines/s3pl" "$root/run_logs" "$root/provenance" logs
if [[ ! -f "$root/provenance/manifest.txt" ]]; then
    {
        echo "purpose=S3PL CAC retrained-centre control, second seed (supervisor chat 2026-10-15 item 2)"
        echo "arms=real (tasks 0-7), tile_centre (tasks 8-15)"
        echo "initialization_seed=2"
        echo "sample_order_seed=1"
        echo "random_seed=1"
        echo "patch_size=9"
        echo "epochs=10"
        echo "normalization=reference_spatial_max"
        echo "peaks_per_spectral_patch=256"
        echo "matched_counts=40TopL:315,160TopL:210,200TopL:221,240TopL:255,280TopL:245,360TopL:247,400TopL:133,520TopL:232"
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
    echo "Seed-2 checkpoints already exist; use --indices for the missing tasks only." >&2
    exit 1
fi
pilot="$(sbatch --parsable --exclude="$exclude" --array=1,9 "$runner")"
pilot_id="${pilot%%;*}"
rest="$(sbatch --parsable --exclude="$exclude" --dependency="afterok:${pilot_id}" \
    --array="0,2-8,10-15%$concurrency" "$runner")"
rest_id="${rest%%;*}"
echo "$pilot_id pilot 160TopL (tasks 1,9)" | tee -a "$root/provenance/slurm_job_ids.txt"
echo "$rest_id remaining 14 tasks (afterok:$pilot_id)" | tee -a "$root/provenance/slurm_job_ids.txt"
