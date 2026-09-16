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
variants=(uniform_mean central_only)

printf '%-18s %-14s %-12s %-16s\n' \
    "DATASET" "VARIANT" "FIRST_JOB" "CONTINUATION_JOB"
for dataset in "${datasets[@]}"; do
    for variant in "${variants[@]}"; do
        first_submission=$( \
            sbatch --job-name="${dataset}-${variant}" \
                slurm_jobs/run_spatial_msipl_gbm_validation_training.sh \
                "$dataset" "$variant" \
        )
        first_job=${first_submission##* }
        continuation_submission=$( \
            sbatch --dependency="afterany:$first_job" \
                --job-name="${dataset}-${variant}" \
                slurm_jobs/run_spatial_msipl_gbm_validation_training.sh \
                "$dataset" "$variant" \
        )
        continuation_job=${continuation_submission##* }
        printf '%-18s %-14s %-12s %-16s\n' \
            "$dataset" "$variant" "$first_job" "$continuation_job"
    done
done

echo
echo "Submitted 14 frozen validation runs plus one restart continuation each."
echo "The continuation resumes from the five-epoch checkpoint if the first 16-hour allocation times out."
echo "If the first job completes all 100 epochs, its continuation exits without overwriting it."
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.20j %.2t %.10M %.24R"'
