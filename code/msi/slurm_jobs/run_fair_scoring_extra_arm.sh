#!/bin/bash
# Fair scoring of one additional frozen arm (15 October round; protocol 18
# Section 6.1) with the UNCHANGED evaluate_fair_scoring_baselines.py, so the
# code hash equals the existing central_only/uniform_mean campaign.
#   sbatch --array=LIST slurm_jobs/run_fair_scoring_extra_arm.sh ARM
# ARM: attention (item A), attention_centremask_p50 / uniform_centremask_p50 /
# shuffled_attention_centremask_p50 (item G). One task per section; each runs
# bin level, then the approved partitions.
# Item A on GBM first runs A(b), the tie-aware reproduction of the saved
# old-count attention list (exit 4 on failure), then A(a), re-evaluation of the
# frozen attributions at production K_bin into peak_evaluation_tuned_count/.
# CPU only. Scores go to files; the Slurm .out holds status lines only.
#SBATCH --job-name=fair-extra-arm
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
# Memory: 8G. The unchanged evaluator peaked at 0.91 GB (GNU time, all 32 tasks of
# 66053/66114 incl. GBM22_2); A(a)/A(b) load the same correlations and do less.
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=logs/fair-extra-arm-%A_%a.out
#SBATCH --error=logs/fair-extra-arm-%A_%a.err

set -euo pipefail
PROJECT_ROOT="$HOME/msi"
RESULTS="$PROJECT_ROOT/results"
source "$PROJECT_ROOT/slurm_jobs/fair_scoring_sections.sh"
ARM="${1:?Usage: sbatch --array=LIST $0 ARM}"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_fair_scoring_extra_arm.sh}"
DATASET="${FAIR_SECTIONS[TASK_ID]}"
INPUT="$(fair_input_for "$DATASET")"
APPROVAL="$RESULTS/diagnostics/peak_partition_audit/partition_approval.json"
case "$DATASET" in
    GBM*) legacy="$RESULTS/baselines/msipl/massnet_paper_aligned/$DATASET" ;;
    *)    legacy="$RESULTS/baselines/msipl/cac/$DATASET" ;;
esac
case "$ARM" in
    attention)
        arm_root="$RESULTS/experiments/spatial_attention_context/${DATASET}_seed1/real_attention"
        attribution="$arm_root/attribution"
        case "$DATASET" in
            GBM*) saved="$arm_root/peak_evaluation_tuned_count" ;;
            *)    saved="$arm_root/peak_evaluation" ;;
        esac ;;
    attention_centremask_p50|uniform_centremask_p50|shuffled_attention_centremask_p50)
        arm_root="$RESULTS/experiments/spatial_centremask_p50/${DATASET}_seed1/$ARM"
        attribution="$arm_root/attribution"
        saved="$arm_root/peak_evaluation" ;;
    *) echo "Unknown arm: $ARM" >&2; exit 2 ;;
esac
OUTPUT_ROOT="$RESULTS/diagnostics/fair_scoring_baselines/extra_arms"

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "=== $DATASET $ARM fair scoring on ${SLURMD_NODENAME:-unknown} (job ${SLURM_ARRAY_JOB_ID}_${TASK_ID}) ==="
grep -q '"status": "valid"' "$attribution/summary.json" \
    || { echo "Attribution is not valid: $attribution" >&2; exit 1; }

if [[ "$ARM" == attention && "$DATASET" == GBM* ]]; then
    k_bin="$("$PYTHON" -c 'import json,sys; print(int(json.load(open(sys.argv[1]))["unique_nearest_bins"]))' "$legacy/peak_metrics.json")"
    # A(b): the saved old-count list must reproduce before anything else.
    "$PYTHON" -u scripts/check_saved_list_reproduction.py \
        --input "$INPUT" --attribution-dir "$attribution" \
        --saved-evaluation-dir "$arm_root/peak_evaluation" \
        --output "$arm_root/saved_list_reproduction.json"
    # A(a): unchanged evaluator, frozen attributions, production K_bin.
    if ! grep -q '"status": "complete"' "$saved/summary.json" 2>/dev/null; then
        mkdir -p "$saved"
        "$PYTHON" -u scripts/evaluate_spatial_msipl_attributed_peaks.py \
            --input "$INPUT" --attribution-dir "$attribution" \
            --legacy-peaks "$legacy/learned_peaks.csv" \
            --legacy-metrics "$legacy/peak_metrics.json" \
            --output "$saved" --matched-count "$k_bin" \
            --peak-tolerance-ppm 10 --consolidated-candidates 50 \
            --ion-images 12 --chunk-size 1024 > "$saved/evaluation_stdout.log"
    fi
    echo "A(a) re-evaluation at K_bin=$k_bin complete"
fi
grep -q '"status": "complete"' "$saved/summary.json" \
    || { echo "Saved peak evaluation is not complete: $saved" >&2; exit 1; }

for scope in bin_level_only with_approved_partitions; do
    output="$OUTPUT_ROOT/$scope/${DATASET}_seed1/$ARM"
    mkdir -p "$output"
    partition_args=()
    if [ "$scope" = with_approved_partitions ]; then
        partition_args=(--partition-dir "$RESULTS/diagnostics/peak_partition_audit/$DATASET"
                        --partition-approval "$APPROVAL")
    fi
    "$PYTHON" -u scripts/evaluate_fair_scoring_baselines.py \
        --input "$INPUT" --attribution-dir "$attribution" \
        --saved-evaluation-dir "$saved" \
        --legacy-peaks "$legacy/learned_peaks.csv" \
        --legacy-metrics "$legacy/peak_metrics.json" \
        --output "$output" --random-draws 100 --chunk-size 1024 \
        ${partition_args[@]+"${partition_args[@]}"} > "$output/evaluator_stdout.log"
    echo "$scope: $(grep -o '"status": "[a-z]*"' "$output/summary.json" | head -1)"
done
