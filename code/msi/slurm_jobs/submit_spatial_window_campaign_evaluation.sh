#!/bin/bash
# Evaluate completed training arms without waiting for unrelated sections.
set -euo pipefail

cd "$HOME/msi"
mkdir -p logs
if squeue -h -u "$USER" -n window-eval-all | grep -q .; then
    echo "A window-eval-all campaign is already queued or running; not submitting a duplicate." >&2
    exit 1
fi

DATASETS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
          GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
ARMS=(uniform_p5 zero_p3 shuffled_p3)
eligible=()
for ((index=3; index<48; index++)); do
    dataset="${DATASETS[index / 3]}"
    arm="${ARMS[index % 3]}"
    checkpoint="/datasets/zsuliman/msi_checkpoints/spatial_msipl/window_pilot/${dataset}_seed1/$arm/checkpoint.pt"
    result_root="$HOME/msi/results/experiments/spatial_msipl_window_pilot/${dataset}_seed1/$arm"
    if [ ! -f "$checkpoint" ] || ! grep -q '"status": "complete"' "$result_root/summary.json" 2>/dev/null; then
        continue
    fi
    if grep -q '"status": "complete"' "$result_root/peak_evaluation/summary.json" 2>/dev/null && \
       grep -q '"status": "valid"' "$result_root/attribution/summary.json" 2>/dev/null && \
       [ -f "$result_root/reconstruction/reconstruction.json" ]; then
        continue
    fi
    case "$dataset" in
        GBM*) legacy="$HOME/msi/results/baselines/msipl/massnet/$dataset" ;;
        *) legacy="$HOME/msi/results/baselines/msipl/cac/$dataset" ;;
    esac
    if [ ! -f "$legacy/learned_peaks.csv" ] || [ ! -f "$legacy/peak_metrics.json" ]; then
        echo "Legacy matched-count reference is missing for $dataset: $legacy" >&2
        exit 1
    fi
    eligible+=("$index")
done
if [ "${#eligible[@]}" -eq 0 ]; then
    echo "No trained, unevaluated configurations are ready; nothing to submit."
    exit 0
fi

array_indices=$(IFS=,; echo "${eligible[*]}")
submission=$(sbatch --array="${array_indices}%3" slurm_jobs/run_spatial_window_campaign_evaluation_array.sh)
echo "$submission"
echo "Submitted ${#eligible[@]} trained, unevaluated configurations; at most 3 simultaneously."
echo "Array indices: $array_indices"
echo 'Audit with: bash slurm_jobs/check_spatial_window_campaign.sh'
