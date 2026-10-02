#!/bin/bash
# Shell-only launcher; run with bash from ~/msi.
set -euo pipefail

cd "$HOME/msi"
mkdir -p logs
for dataset in 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL; do
    input="/datasets/zsuliman/msi_data/cac_msipl/${dataset}.h5"
    if [ ! -f "$input" ]; then
        echo "Missing CAC input: $input" >&2
        exit 1
    fi
done
for dataset in GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2; do
    input="/datasets/zsuliman/msi_data/gbm_massnet/${dataset}.h5"
    if [ ! -f "$input" ]; then
        echo "Missing GBM input: $input" >&2
        exit 1
    fi
done
if squeue -h -u "$USER" -n spatial-window-all | grep -q .; then
    echo "A spatial-window-all campaign is already queued or running; not submitting a duplicate." >&2
    exit 1
fi

DATASETS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
          GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
ARMS=(uniform_p5 zero_p3 shuffled_p3)
missing=()
for ((index=3; index<48; index++)); do
    dataset="${DATASETS[index / 3]}"
    arm="${ARMS[index % 3]}"
    checkpoint="/datasets/zsuliman/msi_checkpoints/spatial_msipl/window_pilot/${dataset}_seed1/$arm/checkpoint.pt"
    summary="$HOME/msi/results/experiments/spatial_msipl_window_pilot/${dataset}_seed1/$arm/summary.json"
    if [ ! -f "$checkpoint" ] || ! grep -q '"status": "complete"' "$summary" 2>/dev/null; then
        missing+=("$index")
    fi
done
if [ "${#missing[@]}" -eq 0 ]; then
    echo "All 45 confirmation training configurations are complete; nothing to submit."
    exit 0
fi
# Create sibling-arm directories serially before the array starts. Otherwise
# simultaneous tasks can race while Python recursively creates a new parent.
for index in "${missing[@]}"; do
    dataset="${DATASETS[index / 3]}"
    arm="${ARMS[index % 3]}"
    mkdir -p \
        "/datasets/zsuliman/msi_checkpoints/spatial_msipl/window_pilot/${dataset}_seed1/$arm" \
        "$HOME/msi/results/experiments/spatial_msipl_window_pilot/${dataset}_seed1/$arm"
done
array_indices=$(IFS=,; echo "${missing[*]}")
submission=$(sbatch --array="${array_indices}%3" slurm_jobs/run_spatial_window_campaign_array.sh)
echo "$submission"
echo "Submitted ${#missing[@]} incomplete training configurations; at most 3 simultaneously."
echo "Array indices: $array_indices"
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R"'
echo 'Audit with: bash slurm_jobs/check_spatial_window_campaign.sh'
