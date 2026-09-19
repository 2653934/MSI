#!/bin/bash

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"

datasets=(
    GBM108_negative
    GBM12_1
    GBM12_2
    GBM22_1
    GBM22_2
    GBM39_1
    GBM39_2
)

job_ids=()
printf '%-18s %-12s\n' "DATASET" "JOB_ID"
for dataset in "${datasets[@]}"; do
    submission=$(sbatch --job-name="recon-${dataset}" \
        slurm_jobs/evaluate_spatial_gbm_reconstruction.sh "$dataset")
    job_id=${submission##* }
    job_ids+=("$job_id")
    printf '%-18s %-12s\n' "$dataset" "$job_id"
done

dependency=$(IFS=:; echo "${job_ids[*]}")
summary_submission=$(sbatch --dependency="afterok:$dependency" \
    slurm_jobs/summarise_spatial_gbm_reconstruction.sh)
summary_job_id=${summary_submission##* }

echo
echo "Submitted 7 matched reconstruction evaluations."
echo "Summary job: $summary_job_id (runs after all evaluations succeed)"
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R"'
