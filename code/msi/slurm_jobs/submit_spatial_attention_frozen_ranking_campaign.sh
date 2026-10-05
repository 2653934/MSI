#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
DATASETS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
          GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
CUDA_QUARANTINE_FILE="$PROJECT_ROOT/slurm_jobs/gpu_cuda_quarantine.txt"
if [ ! -f "$CUDA_QUARANTINE_FILE" ]; then
    echo "Missing CUDA quarantine list: $CUDA_QUARANTINE_FILE" >&2
    exit 1
fi
EXCLUDES=$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' \
    "$CUDA_QUARANTINE_FILE" | sort -u | paste -sd, -)
if [ -z "$EXCLUDES" ]; then
    echo "CUDA quarantine list is empty; review it before submitting." >&2
    exit 1
fi

active_jobs=$(squeue -u "$USER" -h -n attention-rank-all)
if [ -n "$active_jobs" ]; then
    echo "An attention-rank-all campaign is already queued or running; check it before resubmitting." >&2
    exit 1
fi

missing=()
missing_inputs=()
for index in "${!DATASETS[@]}"; do
    dataset="${DATASETS[index]}"
    result="$PROJECT_ROOT/results/diagnostics/spatial_attention_frozen_ranking_swap/$dataset"
    if ! grep -q '"status": "valid"' "$result/summary.json" 2>/dev/null ||
       [ ! -f "$result/rankings.npz" ]; then
        missing+=("$index")
        checkpoint="/datasets/zsuliman/msi_checkpoints/spatial_msipl/attention_context/${dataset}_seed1/real_attention/checkpoint.pt"
        training="$PROJECT_ROOT/results/experiments/spatial_attention_context/${dataset}_seed1/real_attention/summary.json"
        swap="$PROJECT_ROOT/results/diagnostics/spatial_attention_input_swap/$dataset/summary.json"
        if [ ! -f "$checkpoint" ] ||
           ! grep -q '"status": "complete"' "$training" 2>/dev/null ||
           ! grep -q '"status": "valid"' "$swap" 2>/dev/null; then
            missing_inputs+=("$dataset")
        fi
    fi
done
if [ "${#missing_inputs[@]}" -gt 0 ]; then
    printf 'Missing frozen training or input-swap prerequisites: %s\n' "${missing_inputs[*]}" >&2
    exit 1
fi
if [ "${#missing[@]}" -eq 0 ]; then
    echo "All 16 frozen attention ranking swaps are already valid."
    exit 0
fi
indices=$(IFS=,; echo "${missing[*]}")
sbatch --exclude="$EXCLUDES" --array="${indices}%2" \
    slurm_jobs/run_spatial_attention_frozen_ranking_campaign_array.sh
echo "Submitted ${#missing[@]} missing sections; at most two allocations run together."
echo "Array indices: $indices"
echo "Excluded nodes with directly observed CUDA failures: $EXCLUDES"
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R"'
echo "Audit with: bash slurm_jobs/check_spatial_attention_frozen_ranking_campaign.sh"
