#!/bin/bash

# Complete paper-aligned post-training Beta tuning after the GBM12_1 pilot.
# These jobs reuse trained msiPL checkpoints and do not retrain the VAEs.

set -euo pipefail

PROJECT_ROOT="$HOME/msi"
RUNNER="$PROJECT_ROOT/slurm_jobs/tune_msipl_massnet_beta.sh"
DATASETS=(
    GBM12_2
    GBM22_1
    GBM22_2
    GBM39_1
    GBM39_2
    GBM108_positive
    GBM108_negative
)

if [[ ! -f "$RUNNER" ]]; then
    echo "Runner not found: $RUNNER" >&2
    exit 1
fi

# Validate all prerequisites and destinations before submitting any jobs.
for dataset in "${DATASETS[@]}"; do
    input="/datasets/zsuliman/msi_data/gbm_massnet/$dataset.h5"
    weights="/datasets/zsuliman/msi_checkpoints/baselines/msipl/massnet/$dataset/msipl_weights.h5"
    output="$PROJECT_ROOT/results/baselines/msipl/massnet_paper_aligned/$dataset/peak_metrics.json"

    if [[ ! -f "$input" ]]; then
        echo "Input dataset is missing; no jobs submitted: $input" >&2
        exit 1
    fi
    if [[ ! -f "$weights" ]]; then
        echo "Checkpoint is missing; no jobs submitted: $weights" >&2
        exit 1
    fi
    if [[ -f "$output" ]]; then
        echo "Completed tuned output exists; no jobs submitted: $output" >&2
        exit 1
    fi
done

mkdir -p "$PROJECT_ROOT/logs"
cd "$PROJECT_ROOT"

printf '%-18s %-12s %s\n' "DATASET" "JOB_ID" "MODE"
for dataset in "${DATASETS[@]}"; do
    submission="$(sbatch --parsable "$RUNNER" "$dataset")"
    job_id="${submission%%;*}"

    if ! [[ "$job_id" =~ ^[0-9]+$ ]]; then
        echo "Unexpected sbatch response for $dataset: $submission" >&2
        exit 1
    fi

    printf '%-18s %-12s %s\n' "$dataset" "$job_id" "checkpoint reuse"
done

echo
echo "Submitted ${#DATASETS[@]} remaining msiPL Beta-tuning jobs."
echo "Together with the GBM12_1 pilot, these form the tuned eight-section GBM comparison."
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.20j %.2t %.10M %.20R"'
