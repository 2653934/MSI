#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
MAX_CONCURRENT="${1:-4}"
if [ "$#" -gt 1 ] || ! [[ "$MAX_CONCURRENT" =~ ^[1-6]$ ]]; then
    echo "Usage: bash $0 [MAX_CONCURRENT: 1-6, default 4]" >&2
    exit 2
fi
DATASETS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
          GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
MATCHED_COUNTS=(315 210 221 255 245 247 133 232 530 458 453 478 589 464 686 523)

if [ -n "$(squeue -u "$USER" -h -n attention-peak-all)" ]; then
    echo "A changed-peak audit array is already queued or running." >&2
    exit 1
fi

missing=()
for index in "${!DATASETS[@]}"; do
    dataset="${DATASETS[index]}"
    output="$PROJECT_ROOT/results/diagnostics/spatial_attention_changed_peaks/$dataset"
    if grep -q '"status": "valid"' "$output/summary.json" 2>/dev/null &&
       [ -f "$output/changed_bins.csv" ] &&
       [ -f "$output/changed_bin_pcc.png" ] &&
       [ -f "$output/changed_ion_images.png" ]; then
        continue
    fi
    ranking="$PROJECT_ROOT/results/diagnostics/spatial_attention_frozen_ranking_swap/$dataset"
    original="$PROJECT_ROOT/results/experiments/spatial_attention_context/${dataset}_seed1/real_attention/peak_evaluation/ig_matched_${MATCHED_COUNTS[index]}_bins.csv"
    if ! grep -q '"status": "valid"' "$ranking/summary.json" 2>/dev/null ||
       [ ! -f "$ranking/rankings.npz" ] || [ ! -f "$original" ]; then
        echo "Missing valid frozen ranking or original peak list for $dataset" >&2
        exit 1
    fi
    missing+=("$index")
done
if [ "${#missing[@]}" -eq 0 ]; then
    echo "All 16 changed-peak audits are already valid."
    exit 0
fi
indices=$(IFS=,; echo "${missing[*]}")
sbatch --array="${indices}%${MAX_CONCURRENT}" \
    slurm_jobs/run_spatial_attention_changed_peaks_campaign_array.sh
echo "Submitted ${#missing[@]} incomplete CPU-only audits; at most $MAX_CONCURRENT run together."
echo "Array indices: $indices"
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R"'
echo "Audit with: bash slurm_jobs/check_spatial_attention_changed_peaks_campaign.sh"
