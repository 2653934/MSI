#!/bin/bash

# Submit one deterministic repeat of job 53118 without overwriting its artifacts.

set -euo pipefail

PROJECT_ROOT="${HOME}/msi"
RUNNER="${PROJECT_ROOT}/slurm_jobs/run_s3pl_massnet_gbm.sh"
SUBMITTER="$(readlink -f "${BASH_SOURCE[0]}")"
DATASET="GBM108_positive"
EPOCHS=10
EVALUATE=true
PATCH_SIZE=3
BASELINE_JOB_ID=53118
TRAINING_NAME="${DATASET}_Attention3DConvAutoencoder_${EPOCHS}epochs_256_spectral_patch_size_${PATCH_SIZE}"
REPEAT_NAME="${DATASET}_p3_seed1_repeat1"
REPEAT_ROOT="${PROJECT_ROOT}/reproducibility/s3pl_massnet/${REPEAT_NAME}"
PROVENANCE_DIR="${REPEAT_ROOT}/provenance"
SUBMISSION_MARKER="${PROVENANCE_DIR}/submission_attempted.txt"
JOB_ID_FILE="${PROVENANCE_DIR}/slurm_job_id.txt"

if [[ ! -f "$RUNNER" ]]; then
    echo "Runner not found: $RUNNER" >&2
    exit 1
fi

if [[ -e "$REPEAT_ROOT" ]]; then
    if [[ -f "$SUBMISSION_MARKER" || -f "$JOB_ID_FILE" || \
          -d "${REPEAT_ROOT}/checkpoints" || -d "${REPEAT_ROOT}/logs" || \
          -d "${REPEAT_ROOT}/results" ]]; then
        echo "Repeat root contains a submission marker or run artifacts; refusing to submit again: $REPEAT_ROOT" >&2
        exit 1
    fi
    if [[ -d "$PROVENANCE_DIR" ]]; then
        echo "Resuming the incomplete pre-submission provenance directory: $REPEAT_ROOT"
    else
        echo "Repeat root exists in an unexpected state; refusing to use it: $REPEAT_ROOT" >&2
        exit 1
    fi
fi

BASELINE_FILES=(
    "${PROJECT_ROOT}/checkpoints/baselines/s3pl/${TRAINING_NAME}.pt"
    "${PROJECT_ROOT}/logs/s3pl/${TRAINING_NAME}.json"
    "${PROJECT_ROOT}/results/baselines/s3pl/${TRAINING_NAME}/metrics.json"
    "${PROJECT_ROOT}/results/baselines/s3pl/${TRAINING_NAME}/runtime_metrics.json"
    "${PROJECT_ROOT}/results/baselines/s3pl/${TRAINING_NAME}/peak_evaluation_${DATASET}_${EPOCHS}epochs.txt"
    "${PROJECT_ROOT}/results/baselines/s3pl/${TRAINING_NAME}/picked_peaks_${DATASET}_256peaks_z_patchsize_${PATCH_SIZE}.csv"
    "${PROJECT_ROOT}/logs/s3pl-gbm-${BASELINE_JOB_ID}.out"
    "${PROJECT_ROOT}/logs/s3pl-gbm-${BASELINE_JOB_ID}.err"
)

for path in "${BASELINE_FILES[@]}"; do
    if [[ ! -f "$path" ]]; then
        echo "Required baseline artifact is missing: $path" >&2
        exit 1
    fi
done

mkdir -p "$PROVENANCE_DIR" "${PROJECT_ROOT}/logs"
sha256sum "${BASELINE_FILES[@]}" > "${PROVENANCE_DIR}/job_${BASELINE_JOB_ID}_sha256.txt"
sha256sum "$RUNNER" "$SUBMITTER" > "${PROVENANCE_DIR}/submission_scripts_sha256.txt"
if git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    source_commit="$(git -C "$PROJECT_ROOT" rev-parse HEAD)"
    git -C "$PROJECT_ROOT" status --short > "${PROVENANCE_DIR}/git_status.txt"
    git -C "$PROJECT_ROOT" diff --binary > "${PROVENANCE_DIR}/uncommitted_changes.patch"
else
    source_commit="unavailable-cluster-copy-has-no-git-metadata"
    printf '%s\n' "$source_commit" > "${PROVENANCE_DIR}/git_status.txt"
    printf '%s\n' "$source_commit" > "${PROVENANCE_DIR}/uncommitted_changes.patch"
fi
{
    printf 'repeat_name=%s\n' "$REPEAT_NAME"
    printf 'source_job_id=%s\n' "$BASELINE_JOB_ID"
    printf 'dataset=%s\n' "$DATASET"
    printf 'epochs=%s\n' "$EPOCHS"
    printf 'evaluate=%s\n' "$EVALUATE"
    printf 'patch_size=%s\n' "$PATCH_SIZE"
    printf 'random_seed=1\n'
    printf 'submitted_from_commit=%s\n' "$source_commit"
    printf 'created_utc=%s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
} > "${PROVENANCE_DIR}/manifest.txt"

cd "$PROJECT_ROOT"
printf 'created_utc=%s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" > "$SUBMISSION_MARKER"
submission="$(
    sbatch \
        --parsable \
        --time=01:00:00 \
        --exclusive \
        "$RUNNER" "$DATASET" "$EPOCHS" "$EVALUATE" "$PATCH_SIZE" "$REPEAT_ROOT"
)"
job_id="${submission%%;*}"

if ! [[ "$job_id" =~ ^[0-9]+$ ]]; then
    echo "Unexpected sbatch response: $submission" >&2
    exit 1
fi

printf '%s\n' "$job_id" > "$JOB_ID_FILE"

printf 'Submitted %s as job %s\n' "$REPEAT_NAME" "$job_id"
printf 'Artifact root: %s\n' "$REPEAT_ROOT"
printf 'Monitor with: squeue -j %s -o "%%.18i %%.12j %%.2t %%.10M %%.20R"\n' "$job_id"
