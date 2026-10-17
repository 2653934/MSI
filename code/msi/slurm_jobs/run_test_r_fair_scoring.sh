#!/bin/bash
# Test R fair scoring (protocol 18 Section 6.3): the unchanged
# evaluate_fair_scoring_baselines.py on one section's two arms at one training
# seed (2 or 3), with the same K_bin and references as seed 1:
#   sbatch --array=0-23 slurm_jobs/run_test_r_fair_scoring.sh SEED   (via submit_test_r.sh)
# GBM/CAC: bin level and the approved partitions, with the legacy list, as the
# seed-1 campaign (run_fair_scoring_extra_arm.sh). RCC: bin level only, without
# legacy, at the seed-1 released-target budget (as run_rcc_fair_scoring.sh; the
# 07:16 amendment), primary analysis only. A seed-arm whose IG is not valid or whose
# matched evaluation is missing is "not done" and is skipped.
# CPU only. Scores go to files; the Slurm .out holds status lines only.
#SBATCH --job-name=test-r-fair
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
# Memory: the evaluator peaked at 0.91 GB (GBM22_2, 4,524 px x 85,062 bins).
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=logs/test-r-fair-%A_%a.out
#SBATCH --error=logs/test-r-fair-%A_%a.err

set -euo pipefail
PROJECT_ROOT="$HOME/msi"
RESULTS="$PROJECT_ROOT/results"
source "$PROJECT_ROOT/slurm_jobs/test_r_sections.sh"
SEED="${1:?Usage: sbatch --array=0-23 $0 SEED}"
test_r_check_seed "$SEED"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_test_r.sh}"
if (( TASK_ID < 0 || TASK_ID >= ${#TEST_R_SECTIONS[@]} )); then
    echo "Invalid array index: $TASK_ID" >&2; exit 2
fi
DATASET="${TEST_R_SECTIONS[TASK_ID]}"
COLLECTION="$(test_r_collection "$DATASET")"
INPUT="$(test_r_input_for "$DATASET")"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "=== $DATASET seed $SEED Test R fair scoring on ${SLURMD_NODENAME:-unknown} (job ${SLURM_ARRAY_JOB_ID}_${TASK_ID}) ==="

if [ "$COLLECTION" = RCC ]; then
    SCOPES=(bin_level_only)
    SOURCE_ARGUMENTS=(--no-legacy --reference-budget "$(test_r_rcc_budget "$DATASET")")
    EVALUATION_NAME=peak_evaluation_released_target
else
    SCOPES=(bin_level_only with_approved_partitions)
    LEGACY_DIR="$(test_r_legacy_dir "$DATASET")"
    SOURCE_ARGUMENTS=(--legacy-peaks "$LEGACY_DIR/learned_peaks.csv"
                      --legacy-metrics "$LEGACY_DIR/peak_metrics.json")
    EVALUATION_NAME=peak_evaluation
fi
for arm in "${TEST_R_ARMS[@]}"; do
    root="$(test_r_result_root "$DATASET" "$SEED" "$arm")"
    attribution="$root/attribution"
    saved="$root/$EVALUATION_NAME"
    if ! grep -q '"status": "valid"' "$attribution/summary.json" 2>/dev/null \
            || ! grep -q '"status": "complete"' "$saved/summary.json" 2>/dev/null; then
        echo "$arm: not done (IG not valid or matched evaluation missing); not scored"
        continue
    fi
    for scope in "${SCOPES[@]}"; do
        output="$TEST_R_FAIR/$scope/${DATASET}_seed${SEED}/$arm"
        mkdir -p "$output"
        partition_args=()
        if [ "$scope" = with_approved_partitions ]; then
            partition_args=(--partition-dir "$RESULTS/diagnostics/peak_partition_audit/$DATASET"
                            --partition-approval "$RESULTS/diagnostics/peak_partition_audit/partition_approval.json")
        fi
        "$PYTHON" -u scripts/evaluate_fair_scoring_baselines.py \
            --input "$INPUT" --attribution-dir "$attribution" --saved-evaluation-dir "$saved" \
            "${SOURCE_ARGUMENTS[@]}" --output "$output" --random-draws 100 --chunk-size 1024 \
            ${partition_args[@]+"${partition_args[@]}"} > "$output/evaluator_stdout.log"
        echo "$arm $scope: $(grep -o '"status": "[a-z]*"' "$output/summary.json" | head -1)"
    done
done
