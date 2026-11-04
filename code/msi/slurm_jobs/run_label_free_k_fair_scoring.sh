#!/bin/bash
# Label-free K (protocol 18 Section 6.10; D56), step 3: the unchanged fair-scoring
# evaluator, bin level only, all classes, at the production K_bin, on one section-arm
# (label_free_k_sections.sh, 0-47). GBM/CAC with the legacy list; RCC without legacy
# at the seed-1 released-target budget (as run_test_r_fair_scoring.sh).
#   bash slurm_jobs/submit_label_free_k.sh fair INDICES   (each submission needs Zayd's OK)
# The run scored is the first step count (64, 128, 256, 512, 1024) whose IG is valid,
# whose identity check passed and, above 64, whose gate v2 passed. A section-arm
# that is "not done" (component under 44 px, or still needs_more_ig_steps at 1024)
# is not scored. One still waiting for an escalation stops the task (exit 1).
# Exit 3: output already exists (never overwritten). CPU only; scores go to files.
#SBATCH --job-name=lfk-fair
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
# Memory: the evaluator peaked at 0.91 GB (GBM22_2, 4,524 px x 85,062 bins).
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=logs/lfk-fair-%A_%a.out
#SBATCH --error=logs/lfk-fair-%A_%a.err

set -euo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/label_free_k_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_label_free_k.sh}"
lfk_task "$TASK_ID"
DATASET="$TASK_SECTION"; ARM="$TASK_ARM"
COLLECTION="$(test_r_collection "$DATASET")"
INPUT="$(test_r_input_for "$DATASET")"
echo "=== $DATASET $ARM label-free K fair scoring on ${SLURMD_NODENAME:-unknown} (job ${SLURM_ARRAY_JOB_ID:-}_${TASK_ID}) ==="

# The decisive step count, mechanically.
STEPS=""
for candidate in "${LFK_STEPS[@]}"; do
    root="$(lfk_result_root "$DATASET" "$ARM" "$candidate")"
    if [ -f "$root/not_done.json" ]; then
        echo "not done ($(grep -o '"reason": "[^"]*"' "$root/not_done.json")); not scored"; exit 0
    fi
    [ -f "$root/attribution/summary.json" ] \
        || { echo "No run at $candidate steps yet (escalation pending): $root" >&2; exit 1; }
    if grep -q '"status": "needs_more_ig_steps"' "$root/attribution/summary.json"; then
        if [ "$candidate" = 1024 ]; then
            echo "not done (IG completeness not reached at 1024 steps); not scored"; exit 0
        fi
        continue
    fi
    grep -q '"passed": true' "$root/identity_check.json" 2>/dev/null \
        || { echo "Identity check missing or failed: $root" >&2; exit 1; }
    if [ "$candidate" != 64 ]; then
        grep -q '"passed": true' "$root/gmm_gate_v2.json" 2>/dev/null \
            || { echo "GMM gate v2 missing or failed: $root" >&2; exit 1; }
    fi
    STEPS="$candidate"; break
done
ROOT="$(lfk_result_root "$DATASET" "$ARM" "$STEPS")"
if [ "$COLLECTION" = RCC ]; then
    SOURCE_ARGUMENTS=(--no-legacy --reference-budget "$(test_r_rcc_budget "$DATASET")")
    SAVED="$ROOT/peak_evaluation_released_target"
else
    LEGACY_DIR="$(test_r_legacy_dir "$DATASET")"
    SOURCE_ARGUMENTS=(--legacy-peaks "$LEGACY_DIR/learned_peaks.csv"
                      --legacy-metrics "$LEGACY_DIR/peak_metrics.json")
    SAVED="$ROOT/peak_evaluation"
fi
grep -q '"status": "complete"' "$SAVED/summary.json" 2>/dev/null \
    || { echo "Matched evaluation missing: $SAVED" >&2; exit 1; }
OUTPUT="$(lfk_fair_output "$DATASET" "$ARM" "$STEPS")"
[ ! -e "$OUTPUT" ] || { echo "Output already exists: $OUTPUT (never overwritten)" >&2; exit 3; }
mkdir -p "$OUTPUT"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
"$PYTHON" -u scripts/evaluate_fair_scoring_baselines.py \
    --input "$INPUT" --attribution-dir "$ROOT/attribution" --saved-evaluation-dir "$SAVED" \
    "${SOURCE_ARGUMENTS[@]}" --output "$OUTPUT" --random-draws 100 --chunk-size 1024 \
    > "$OUTPUT/evaluator_stdout.log"
echo "steps $STEPS: $(grep -o '"status": "[a-z]*"' "$OUTPUT/summary.json" | head -1)"
