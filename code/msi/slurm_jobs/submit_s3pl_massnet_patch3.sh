#!/bin/bash

# Submit the paper-aligned MassNet GBM S3PL configuration on all eight sections.
# The paper reports p=3 and z=256 for GBM. Each job requests an exclusive node.

set -euo pipefail

PROJECT_ROOT="${HOME}/msi"
RUNNER="${PROJECT_ROOT}/slurm_jobs/run_s3pl_massnet_gbm.sh"
EPOCHS=10
EVALUATE=true
PATCH_SIZE=3

DATASETS=(
    GBM108_positive
    GBM108_negative
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

printf '%-18s %-12s %-10s %s\n' "DATASET" "JOB_ID" "PATCH" "NODE SHARING"

for dataset in "${DATASETS[@]}"; do
    submission="$(
        sbatch \
            --parsable \
            --time=03:00:00 \
            --exclusive \
            "$RUNNER" "$dataset" "$EPOCHS" "$EVALUATE" "$PATCH_SIZE"
    )"
    job_id="${submission%%;*}"

    if ! [[ "$job_id" =~ ^[0-9]+$ ]]; then
        echo "Unexpected sbatch response for ${dataset}: ${submission}" >&2
        exit 1
    fi

    printf '%-18s %-12s %-10s %s\n' "$dataset" "$job_id" "$PATCH_SIZE" "exclusive"
done

echo
echo "Submitted ${#DATASETS[@]} paper-aligned GBM jobs with p=${PATCH_SIZE}."
echo 'Monitor them with: squeue -u "$USER"'
