#!/bin/bash
# Gates (a)+(b): one array task per section, scoring both IG arms
# (central_only, uniform_mean) as an independently auditable unit.
# CPU-only; no retraining or attribution. No CUDA preflight is needed.
# The Python script validates provenance before skipping, refuses stale
# results (exit 3) and writes summary.json atomically. Submit via
# slurm_jobs/submit_fair_scoring.sh; PARTITION_APPROVAL is exported by it.
# Resources set from the 9 Oct partition-audit pilot: max RSS 215 MB, I/O bound (~21% CPU).
#SBATCH --job-name=fair-scoring
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output=logs/fair-scoring-%A_%a.out
#SBATCH --error=logs/fair-scoring-%A_%a.err

set -euo pipefail
PROJECT_ROOT="$HOME/msi"
RESULTS="$PROJECT_ROOT/results"
source "$PROJECT_ROOT/slurm_jobs/fair_scoring_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_fair_scoring.sh}"
if (( TASK_ID < 0 || TASK_ID >= ${#FAIR_SECTIONS[@]} )); then
    echo "Invalid array index: $TASK_ID" >&2; exit 2
fi
DATASET="${FAIR_SECTIONS[TASK_ID]}"
INPUT="$(fair_input_for "$DATASET")"
APPROVAL="${PARTITION_APPROVAL:-}"
if [ -n "$APPROVAL" ]; then
    OUTPUT_ROOT="$RESULTS/diagnostics/fair_scoring_baselines/with_approved_partitions"
else
    OUTPUT_ROOT="$RESULTS/diagnostics/fair_scoring_baselines/bin_level_only"
fi

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
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
echo "=== $DATASET fair scoring on ${SLURMD_NODENAME:-unknown} (job ${SLURM_ARRAY_JOB_ID}_${TASK_ID}) ==="

for arm in "${FAIR_ARMS[@]}"; do
    case "$DATASET" in
        GBM*)
            attribution="$RESULTS/experiments/spatial_msipl_gmm_integrated_gradients/${DATASET}_seed1/$arm"
            saved="$RESULTS/experiments/spatial_msipl_gbm_tuned_count_evaluation/${DATASET}_seed1/$arm"
            legacy="$RESULTS/baselines/msipl/massnet_paper_aligned/$DATASET" ;;
        *)
            attribution="$RESULTS/experiments/spatial_msipl_cac_gmm_integrated_gradients/${DATASET}_seed1/$arm"
            saved="$RESULTS/experiments/spatial_msipl_cac_attributed_peak_evaluation/${DATASET}_seed1/$arm"
            legacy="$RESULTS/baselines/msipl/cac/$DATASET" ;;
    esac
    output="$OUTPUT_ROOT/${DATASET}_seed1/$arm"
    mkdir -p "$output"
    partition_args=()
    if [ -n "$APPROVAL" ]; then
        partition_args=(--partition-dir "$RESULTS/diagnostics/peak_partition_audit/$DATASET"
                        --partition-approval "$APPROVAL")
    fi
    timed "$output/resources_${SLURM_ARRAY_JOB_ID}_${TASK_ID}.txt" \
        "$PYTHON" -u scripts/evaluate_fair_scoring_baselines.py \
        --input "$INPUT" --attribution-dir "$attribution" \
        --saved-evaluation-dir "$saved" \
        --legacy-peaks "$legacy/learned_peaks.csv" \
        --legacy-metrics "$legacy/peak_metrics.json" \
        --output "$output" --random-draws 100 --chunk-size 1024 \
        ${partition_args[@]+"${partition_args[@]}"}
done
