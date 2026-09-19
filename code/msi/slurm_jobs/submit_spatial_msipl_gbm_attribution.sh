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
counts=(458 453 478 589 464 686 523)

job_ids=()
printf '%-18s %-14s %-12s\n' "DATASET" "MATCHED_PEAKS" "JOB_ID"
for index in "${!datasets[@]}"; do
    dataset="${datasets[$index]}"
    count="${counts[$index]}"
    submission=$(sbatch --job-name="ig-${dataset}" \
        slurm_jobs/run_spatial_msipl_gbm_attribution.sh "$dataset" "$count")
    job_id=${submission##* }
    job_ids+=("$job_id")
    printf '%-18s %-14s %-12s\n' "$dataset" "$count" "$job_id"
done

dependency=$(IFS=:; echo "${job_ids[*]}")
summary_submission=$(sbatch --dependency="afterok:$dependency" \
    slurm_jobs/summarise_spatial_msipl_gbm_attribution.sh)
summary_job_id=${summary_submission##* }

echo
echo "Submitted 7 matched whole-GBM attribution evaluations."
echo "GBM108_positive reuses the completed frozen evaluation."
echo "Summary job: $summary_job_id (runs after all 7 evaluations succeed)"
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R"'
