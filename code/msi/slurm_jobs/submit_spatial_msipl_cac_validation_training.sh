#!/bin/bash

set -eo pipefail

MODE="${1:-pilot}"
case "$MODE" in
    pilot)
        datasets=(40TopL)
        ;;
    remaining)
        datasets=(160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL)
        ;;
    all)
        datasets=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL)
        ;;
    *)
        echo "Usage: bash $0 {pilot|remaining|all}" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
variants=(uniform_mean central_only)

printf '%-12s %-14s %-12s %-16s\n' \
    "DATASET" "VARIANT" "FIRST_JOB" "CONTINUATION_JOB"
for dataset in "${datasets[@]}"; do
    for variant in "${variants[@]}"; do
        first_submission=$( \
            sbatch --job-name="${dataset}-${variant}" \
                slurm_jobs/run_spatial_msipl_cac_validation_training.sh \
                "$dataset" "$variant" \
        )
        first_job=${first_submission##* }
        continuation_submission=$( \
            sbatch --dependency="afterany:$first_job" \
                --job-name="${dataset}-${variant}" \
                slurm_jobs/run_spatial_msipl_cac_validation_training.sh \
                "$dataset" "$variant" \
        )
        continuation_job=${continuation_submission##* }
        printf '%-12s %-14s %-12s %-16s\n' \
            "$dataset" "$variant" "$first_job" "$continuation_job"
    done
done

echo
echo "Submitted CAC validation mode: $MODE"
echo "Each configuration has one restart continuation."
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R"'
