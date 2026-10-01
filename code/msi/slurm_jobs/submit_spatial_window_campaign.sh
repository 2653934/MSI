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

submission=$(sbatch --array=3-47%3 slurm_jobs/run_spatial_window_campaign_array.sh)
echo "$submission"
echo "45 configurations: 15 remaining sections x 3 arms; at most 3 simultaneously."
echo "The completed 40TopL pilot is excluded."
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R"'
echo 'Audit with: bash slurm_jobs/check_spatial_window_campaign.sh'
