#!/bin/bash
# Start evaluation only after the 45 confirmation training checkpoints exist.
set -euo pipefail

cd "$HOME/msi"
mkdir -p logs
if squeue -h -u "$USER" -n window-eval-all | grep -q .; then
    echo "A window-eval-all campaign is already queued or running; not submitting a duplicate." >&2
    exit 1
fi

DATASETS=(160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
          GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
ARMS=(uniform_p5 zero_p3 shuffled_p3)
for dataset in "${DATASETS[@]}"; do
    case "$dataset" in
        GBM*) legacy="$HOME/msi/results/baselines/msipl/massnet/$dataset" ;;
        *) legacy="$HOME/msi/results/baselines/msipl/cac/$dataset" ;;
    esac
    if [ ! -f "$legacy/learned_peaks.csv" ] || [ ! -f "$legacy/peak_metrics.json" ]; then
        echo "Legacy matched-count reference is missing for $dataset: $legacy" >&2
        exit 1
    fi
    for arm in "${ARMS[@]}"; do
        checkpoint="/datasets/zsuliman/msi_checkpoints/spatial_msipl/window_pilot/${dataset}_seed1/$arm/checkpoint.pt"
        summary="$HOME/msi/results/experiments/spatial_msipl_window_pilot/${dataset}_seed1/$arm/summary.json"
        if [ ! -f "$checkpoint" ] || ! grep -q '"status": "complete"' "$summary" 2>/dev/null; then
            echo "Training is incomplete for $dataset $arm; require checkpoint and complete summary" >&2
            exit 1
        fi
    done
done

submission=$(sbatch --array=3-47%3 slurm_jobs/run_spatial_window_campaign_evaluation_array.sh)
echo "$submission"
echo "45 evaluation configurations, at most 3 simultaneously; completed 40TopL pilot excluded."
echo 'Audit with: bash slurm_jobs/check_spatial_window_campaign.sh'
