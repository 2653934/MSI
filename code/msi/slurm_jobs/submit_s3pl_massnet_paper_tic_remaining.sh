#!/bin/bash

# Complete the eight-section paper-TIC experiment after the positive pilot.

set -euo pipefail

PROJECT_ROOT="$HOME/msi"
RUNNER="$PROJECT_ROOT/slurm_jobs/run_s3pl_massnet_gbm.sh"
DATASETS=(
    GBM108_negative
    GBM12_1
    GBM12_2
    GBM22_1
    GBM22_2
    GBM39_1
    GBM39_2
)

# Check every destination before submitting anything.
for dataset in "${DATASETS[@]}"; do
    artifact_root="$PROJECT_ROOT/reproducibility/s3pl_massnet/${dataset}_p3_paper_tic_seed1"
    if [[ -e "$artifact_root" ]]; then
        echo "Artifact root already exists; refusing partial submission: $artifact_root" >&2
        exit 1
    fi
done

printf '%-18s %-12s %s\n' "DATASET" "JOB_ID" "NORMALIZATION"
for dataset in "${DATASETS[@]}"; do
    run_name="${dataset}_p3_paper_tic_seed1"
    artifact_root="$PROJECT_ROOT/reproducibility/s3pl_massnet/$run_name"
    submission="$(
        sbatch --parsable --time=02:00:00 --exclusive \
            "$RUNNER" "$dataset" 10 true 3 "$artifact_root" paper_tic
    )"
    job_id="${submission%%;*}"

    if ! [[ "$job_id" =~ ^[0-9]+$ ]]; then
        echo "Unexpected sbatch response for $dataset: $submission" >&2
        exit 1
    fi

    mkdir -p "$artifact_root/provenance"
    {
        echo "dataset=$dataset"
        echo "patch_size=3"
        echo "epochs=10"
        echo "random_seed=1"
        echo "normalization=paper_tic"
        echo "purpose=paper-described eight-section GBM experiment"
        echo "created_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    } > "$artifact_root/provenance/manifest.txt"
    echo "$job_id" > "$artifact_root/provenance/slurm_job_id.txt"
    printf '%-18s %-12s %s\n' "$dataset" "$job_id" "paper_tic"
done

echo
echo "Submitted 7 jobs. Together with the completed GBM108_positive pilot,"
echo "this forms the consistent eight-section paper-TIC experiment."
echo 'Monitor with: squeue -u "$USER"'
