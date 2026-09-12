#!/bin/bash

# Submit one protected pilot using the TIC normalization described in the paper.

set -euo pipefail

PROJECT_ROOT="$HOME/msi"
RUNNER="$PROJECT_ROOT/slurm_jobs/run_s3pl_massnet_gbm.sh"
RUN_NAME="GBM108_positive_p3_paper_tic_seed1"
ARTIFACT_ROOT="$PROJECT_ROOT/reproducibility/s3pl_massnet/$RUN_NAME"

if [[ -e "$ARTIFACT_ROOT" ]]; then
    echo "Pilot artifact root already exists; refusing to overwrite: $ARTIFACT_ROOT" >&2
    exit 1
fi

submission="$(
    sbatch --parsable --time=01:30:00 --exclusive \
        "$RUNNER" \
        GBM108_positive \
        10 \
        true \
        3 \
        "$ARTIFACT_ROOT" \
        paper_tic
)"
job_id="${submission%%;*}"

if ! [[ "$job_id" =~ ^[0-9]+$ ]]; then
    echo "Unexpected sbatch response: $submission" >&2
    exit 1
fi

mkdir -p "$ARTIFACT_ROOT/provenance" "$PROJECT_ROOT/logs"
{
    echo "dataset=GBM108_positive"
    echo "patch_size=3"
    echo "epochs=10"
    echo "random_seed=1"
    echo "normalization=paper_tic"
    echo "purpose=controlled paper-aligned normalization pilot"
    echo "created_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
} > "$ARTIFACT_ROOT/provenance/manifest.txt"
echo "$job_id" > "$ARTIFACT_ROOT/provenance/slurm_job_id.txt"
echo "Submitted $RUN_NAME as job $job_id"
echo "Artifacts: $ARTIFACT_ROOT"
echo "Monitor: squeue -j $job_id -o '%.18i %.12j %.2t %.10M %.20R'"
