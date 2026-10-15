#!/bin/bash
# Login-node submitter for item G (centre masking, p = 0.5): file checks, mkdir
# and sbatch only.
#   bash slurm_jobs/submit_centremask_campaign.sh [--concurrency N] [--indices LIST]
# Default: pilot task 9 (160TopL, G1 attention), then the other 33 tasks
# afterok. --indices LIST resubmits only those tasks (for CUDA warm-up node
# failures; record the node in cluster_node_issues.txt first).
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
runner=slurm_jobs/run_centremask_campaign.sh
bash -n "$runner"
exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
if [[ -z "$exclude" ]]; then
    echo "CUDA quarantine list is empty; inspect before submission." >&2
    exit 1
fi
root="results/experiments/spatial_centremask_p50"
checkpoints="/datasets/zsuliman/msi_checkpoints/spatial_msipl/centremask_p50"
# Shared parent folders are created here, before any array task starts.
mkdir -p "$root/provenance" "$checkpoints" logs
source slurm_jobs/fair_scoring_sections.sh
for section in "${FAIR_SECTIONS[@]}"; do
    mkdir -p "$root/${section}_seed1" "$checkpoints/${section}_seed1"
done
if [[ ! -f "$root/provenance/manifest.txt" ]]; then
    {
        echo "purpose=item G: random centre masking during training (supervisor chat 2026-10-15 13:30)"
        echo "centre_mask_probability=0.5"
        echo "centre_mask_seed=seed + 2000003 = 2000004"
        echo "arms=G1 attention_centremask_p50 (tasks 0-15), G2 uniform_centremask_p50 (16-31), G3 shuffled_attention_centremask_p50 (32 160TopL, 33 GBM22_2)"
        echo "training=100 epochs, seed 1, Adam lr 1e-3, batch 128, cosine, sqrt_bins attention, shuffle seed 1701, cached loader"
        echo "evaluation=unmasked input; GMM K 2 (GBM) / 3 (CAC); IG 12 px/component; matched count = production K_bin"
        echo "excluded_nodes=$exclude"
        echo "created_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    } > "$root/provenance/manifest.txt"
fi
if [[ -n "$indices" ]]; then
    job="$(sbatch --parsable --exclude="$exclude" --array="${indices}%$concurrency" "$runner")"
    echo "${job%%;*} indices=$indices" | tee -a "$root/provenance/slurm_job_ids.txt"
    exit 0
fi
if compgen -G "$checkpoints/*_seed1/*/checkpoint*.pt" > /dev/null; then
    echo "Centre-mask checkpoints already exist; use --indices for the missing tasks only." >&2
    exit 1
fi
pilot="$(sbatch --parsable --exclude="$exclude" --array=9 "$runner")"
pilot_id="${pilot%%;*}"
rest="$(sbatch --parsable --exclude="$exclude" --dependency="afterok:${pilot_id}" \
    --array="0-8,10-33%$concurrency" "$runner")"
rest_id="${rest%%;*}"
echo "$pilot_id pilot 160TopL G1 (task 9)" | tee -a "$root/provenance/slurm_job_ids.txt"
echo "$rest_id remaining 33 tasks (afterok:$pilot_id)" | tee -a "$root/provenance/slurm_job_ids.txt"
