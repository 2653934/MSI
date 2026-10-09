#!/bin/bash
# Gate (a), step 1: structural audit of the predeclared P1/P3 partitions.
# CPU-only array task, one section per index. Reads only Data and mzArray.
# The Python script validates provenance before skipping and refuses stale
# outputs (exit 3); it never overwrites them. Submit via
# slurm_jobs/submit_peak_partition_audit.sh. No CUDA preflight is needed.
#SBATCH --job-name=peak-partition-audit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:00:00
#SBATCH --output=logs/peak-partition-audit-%A_%a.out
#SBATCH --error=logs/peak-partition-audit-%A_%a.err

set -euo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/fair_scoring_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_peak_partition_audit.sh}"
if (( TASK_ID < 0 || TASK_ID >= ${#FAIR_SECTIONS[@]} )); then
    echo "Invalid array index: $TASK_ID" >&2; exit 2
fi
DATASET="${FAIR_SECTIONS[TASK_ID]}"
INPUT="$(fair_input_for "$DATASET")"
OUTPUT="$PROJECT_ROOT/results/diagnostics/peak_partition_audit/$DATASET"
RESOURCES="$OUTPUT/resources_${SLURM_ARRAY_JOB_ID}_${TASK_ID}.txt"
mkdir -p "$OUTPUT"

echo "=== $DATASET partition audit on ${SLURMD_NODENAME:-unknown} (job ${SLURM_ARRAY_JOB_ID}_${TASK_ID}) ==="
[ -f "$INPUT" ] || { echo "Missing input: $INPUT" >&2; exit 1; }

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
# Record elapsed time and peak RSS of the scientific process when GNU time exists.
timed() {
    local record="$1"; shift
    if [ -x /usr/bin/time ]; then
        /usr/bin/time -v -o "$record" "$@"
    else
        echo "GNU time unavailable; use sacct Elapsed/MaxRSS" > "$record"
        "$@"
    fi
}

# Slurm MaxRSS/Elapsed are read after completion with sacct (see the submit script).
timed "$RESOURCES" \
    "$PYTHON" -u scripts/audit_peak_partitions.py \
    --input "$INPUT" --output "$OUTPUT" --chunk-size 2048
grep -E "Elapsed|Maximum resident" "$RESOURCES" || true
