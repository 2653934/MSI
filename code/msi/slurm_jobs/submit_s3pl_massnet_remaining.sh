#!/bin/bash

# Submit the six remaining MassNet GBM S3PL experiments as independent jobs.
# Each job requests an exclusive node so two runs cannot contend for one GPU.

set -euo pipefail

PROJECT_ROOT="${HOME}/msi"
RUNNER="${PROJECT_ROOT}/slurm_jobs/run_s3pl_massnet_gbm.sh"
EPOCHS=10
EVALUATE=true

DATASETS=(
    GBM12_1
    GBM12_2
    GBM22_1
    GBM22_2
    GBM39_1
    GBM39_2
)

if [[ ! -f "$RUNNER" ]]; then
    echo "Runner not found: $RUNNER" >&2
    exit 1
fi

mkdir -p "${PROJECT_ROOT}/logs"
cd "$PROJECT_ROOT"

printf '%-18s %-12s %s\n' "DATASET" "JOB_ID" "NODE SHARING"

for dataset in "${DATASETS[@]}"; do
    submit_args=(
        --parsable
        --time=03:00:00
        --exclusive
    )

    submission="$(sbatch "${submit_args[@]}" "$RUNNER" "$dataset" "$EPOCHS" "$EVALUATE")"
    job_id="${submission%%;*}"

    if ! [[ "$job_id" =~ ^[0-9]+$ ]]; then
        echo "Unexpected sbatch response for ${dataset}: ${submission}" >&2
        exit 1
    fi

    printf '%-18s %-12s %s\n' "$dataset" "$job_id" "exclusive"
done

echo
echo "Submitted ${#DATASETS[@]} jobs. Monitor them with:"
echo '  squeue -u "$USER"'
echo
echo "All jobs are independently eligible to run; Slurm will queue any that cannot get a node."
