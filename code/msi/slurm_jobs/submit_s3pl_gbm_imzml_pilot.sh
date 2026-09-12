#!/bin/bash

# Submit the two-section gate through S3PL's original m2aia imzML loader.

set -euo pipefail

PROJECT_ROOT="$HOME/msi"
RUNNER="$PROJECT_ROOT/slurm_jobs/run_s3pl_gbm_imzml_pilot.sh"
DATASETS=(GBM108_positive GBM108_negative)

if [[ ! -f "$RUNNER" ]]; then
    echo "Runner not found: $RUNNER" >&2
    exit 1
fi

mkdir -p "$PROJECT_ROOT/logs"
cd "$PROJECT_ROOT"
printf '%-18s %-12s %s\n' "DATASET" "JOB_ID" "INPUT"

for dataset in "${DATASETS[@]}"; do
    pilot_root="$PROJECT_ROOT/reproducibility/s3pl_gbm_imzml/${dataset}_p3_seed1"
    input_root="/datasets/zsuliman/msi_data/gbm_imzml_s3pl_pilot/$dataset"
    if [[ -e "$pilot_root" ]]; then
        echo "Pilot root already exists; refusing to submit: $pilot_root" >&2
        exit 1
    fi
    if [[ -e "$input_root" ]]; then
        echo "Prepared input root already exists; refusing to submit: $input_root" >&2
        exit 1
    fi

    submission="$(sbatch --parsable --exclusive "$RUNNER" "$dataset")"
    job_id="${submission%%;*}"
    if ! [[ "$job_id" =~ ^[0-9]+$ ]]; then
        echo "Unexpected sbatch response for $dataset: $submission" >&2
        exit 1
    fi
    printf '%-18s %-12s %s\n' "$dataset" "$job_id" "official imzML"
done

echo
echo "Submitted the two-section original-imzML gate."
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.14j %.2t %.10M %.24R"'
