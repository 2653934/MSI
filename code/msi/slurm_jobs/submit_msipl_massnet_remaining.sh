#!/bin/bash

# Complete the eight-section legacy msiPL MassNet experiment after the
# GBM108_positive pilot. Each section is an independent CPU job.

set -euo pipefail

PROJECT_ROOT="$HOME/msi"
RUNNER="$PROJECT_ROOT/slurm_jobs/run_msipl_massnet_gbm.sh"
DATASETS=(
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

# Validate every input and destination before submitting any jobs. The runner
# also refuses to overwrite completed peak metrics as a second safety check.
for dataset in "${DATASETS[@]}"; do
    input="/datasets/zsuliman/msi_data/gbm_massnet/$dataset.h5"
    output="$PROJECT_ROOT/results/baselines/msipl/massnet/$dataset/peak_metrics.json"

    if [[ ! -f "$input" ]]; then
        echo "Input dataset is missing; no jobs submitted: $input" >&2
        exit 1
    fi
    if [[ -f "$output" ]]; then
        echo "Completed output already exists; no jobs submitted: $output" >&2
        exit 1
    fi
done

mkdir -p "$PROJECT_ROOT/logs"
cd "$PROJECT_ROOT"

printf '%-18s %-12s %-12s %s\n' "DATASET" "JOB_ID" "CPU CORES" "NODE SHARING"
for dataset in "${DATASETS[@]}"; do
    submission="$(sbatch --parsable "$RUNNER" "$dataset")"
    job_id="${submission%%;*}"

    if ! [[ "$job_id" =~ ^[0-9]+$ ]]; then
        echo "Unexpected sbatch response for $dataset: $submission" >&2
        exit 1
    fi

    printf '%-18s %-12s %-12s %s\n' "$dataset" "$job_id" "8" "exclusive"
done

echo
echo "Submitted ${#DATASETS[@]} legacy msiPL GBM jobs."
echo "Together with GBM108_positive, these form the eight-section comparison."
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.20j %.2t %.10M %.20R"'
echo "Slurm may leave one or more jobs pending because of your per-user job limit."
