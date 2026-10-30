#!/bin/bash
# Fair scoring of the IG completeness reruns (protocol 18 Section 6.3 amendment
# "30 October: IG completeness reruns"): the unchanged
# evaluate_fair_scoring_baselines.py on one IG_STEPS_TASKS row (ig_steps_sections.sh),
# with the arguments of the original scoring: RCC bin level only, without legacy,
# at the seed-1 released-target budget (as run_test_r_fair_scoring.sh); GBM/CAC
# bin level and the approved partitions, with the legacy list.
#   bash slurm_jobs/submit_ig_steps.sh fair INDICES   (each submission needs Zayd's OK)
# A task whose IG is not valid or whose matched evaluation is missing is skipped
# ("not done at this step count"). Exit 3: output already exists (never overwritten).
# CPU only. Scores go to files; the Slurm .out holds status lines only.
#SBATCH --job-name=ig-steps-fair
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
# Memory: the evaluator peaked at 0.91 GB (GBM22_2, 4,524 px x 85,062 bins).
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=logs/ig-steps-fair-%A_%a.out
#SBATCH --error=logs/ig-steps-fair-%A_%a.err

set -euo pipefail
PROJECT_ROOT="$HOME/msi"
RESULTS="$PROJECT_ROOT/results"
source "$PROJECT_ROOT/slurm_jobs/ig_steps_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_ig_steps.sh}"
ig_steps_task "$TASK_ID"
DATASET="$TASK_SECTION"; SEED="$TASK_SEED"; ARM="$TASK_ARM"; STEPS="$TASK_STEPS"
COLLECTION="$(test_r_collection "$DATASET")"
INPUT="$(test_r_input_for "$DATASET")"
ROOT="$(ig_steps_result_root "$DATASET" "$SEED" "$ARM" "$STEPS" "$TASK_KIND")"
if [ "$COLLECTION" = RCC ]; then
    SCOPES=(bin_level_only)
    SOURCE_ARGUMENTS=(--no-legacy --reference-budget "$(test_r_rcc_budget "$DATASET")")
    SAVED="$ROOT/peak_evaluation_released_target"
else
    SCOPES=(bin_level_only with_approved_partitions)
    LEGACY_DIR="$(test_r_legacy_dir "$DATASET")"
    SOURCE_ARGUMENTS=(--legacy-peaks "$LEGACY_DIR/learned_peaks.csv"
                      --legacy-metrics "$LEGACY_DIR/peak_metrics.json")
    SAVED="$ROOT/peak_evaluation"
fi
for scope in "${SCOPES[@]}"; do
    output="$(ig_steps_fair_output "$scope" "$DATASET" "$SEED" "$ARM" "$STEPS")"
    if [ -e "$output" ]; then
        echo "Output already exists: $output (move it aside; never overwritten)" >&2; exit 3
    fi
done
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "=== $DATASET $ARM seed $SEED, $STEPS steps ($TASK_KIND) fair scoring on ${SLURMD_NODENAME:-unknown} (job ${SLURM_ARRAY_JOB_ID}_${TASK_ID}) ==="

if ! grep -q '"passed": true' "$ROOT/gmm_gate.json" 2>/dev/null \
        || ! grep -q '"status": "valid"' "$ROOT/attribution/summary.json" 2>/dev/null \
        || ! grep -q '"status": "complete"' "$SAVED/summary.json" 2>/dev/null; then
    echo "not done (GMM gate, IG validity or matched evaluation missing); not scored"
    exit 0
fi
for scope in "${SCOPES[@]}"; do
    output="$(ig_steps_fair_output "$scope" "$DATASET" "$SEED" "$ARM" "$STEPS")"
    mkdir -p "$output"
    partition_args=()
    if [ "$scope" = with_approved_partitions ]; then
        partition_args=(--partition-dir "$RESULTS/diagnostics/peak_partition_audit/$DATASET"
                        --partition-approval "$RESULTS/diagnostics/peak_partition_audit/partition_approval.json")
    fi
    "$PYTHON" -u scripts/evaluate_fair_scoring_baselines.py \
        --input "$INPUT" --attribution-dir "$ROOT/attribution" --saved-evaluation-dir "$SAVED" \
        "${SOURCE_ARGUMENTS[@]}" --output "$output" --random-draws 100 --chunk-size 1024 \
        ${partition_args[@]+"${partition_args[@]}"} > "$output/evaluator_stdout.log"
    echo "$scope: $(grep -o '"status": "[a-z]*"' "$output/summary.json" | head -1)"
done
