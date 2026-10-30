#!/bin/bash
# GMM gate v2 for IG completeness reruns that already ran on the GPU (protocol 18
# Section 6.3, "Gate correction after 78483 tasks 1/4/8"; supervisor chat 2026-10-30
# 14:46 and 14:54; decision log D33). One array task per IG_STEPS_TASKS row:
#   bash slurm_jobs/submit_ig_steps.sh gate INDICES   (each submission needs Zayd's OK)
# Writes gmm_gate_v2.json next to the existing gmm_gate.json (v1, kept) with
# check_ig_steps_gate.py. If v2 passes, IG is valid and the matched evaluation is
# missing (78483 tasks 4 and 8, stopped by the v1 identity condition), it runs the
# matched evaluation with the unchanged Test R call: RCC at the released target
# without legacy, GBM/CAC at the production K_bin with the legacy list. No GPU and no
# IG rerun. Exit codes: 3 v2 or a partial evaluation already exists (never
# overwritten); 5 gate v2 failed (stop and post). A task whose IG is not valid is
# recorded "not done at this step count" (exit 0, no evaluation).
#SBATCH --job-name=ig-steps-gate
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
# Memory: only RCC_UH0505_12 (1,462 px x 10,200 bins) needs an evaluation in this
# round; the fair-scoring evaluator peaked at 0.91 GB on the largest GBM section.
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=logs/ig-steps-gate-%A_%a.out
#SBATCH --error=logs/ig-steps-gate-%A_%a.err

set -eo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/ig_steps_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_ig_steps.sh}"
ig_steps_task "$TASK_ID"
DATASET="$TASK_SECTION"; SEED="$TASK_SEED"; ARM="$TASK_ARM"; STEPS="$TASK_STEPS"
COLLECTION="$(test_r_collection "$DATASET")"
INPUT="$(test_r_input_for "$DATASET")"
ROOT="$(ig_steps_result_root "$DATASET" "$SEED" "$ARM" "$STEPS" "$TASK_KIND")"
SAVED="$(ig_steps_saved_attribution "$DATASET" "$SEED" "$ARM")"
if [ -e "$ROOT/gmm_gate_v2.json" ]; then
    echo "Output already exists: $ROOT/gmm_gate_v2.json (never overwritten)" >&2; exit 3
fi
for required in "$ROOT/attribution/summary.json" "$ROOT/gmm_gate.json" "$SAVED/summary.json"; do
    [ -f "$required" ] || { echo "Missing input: $required" >&2; exit 1; }
done
if [ "$COLLECTION" = RCC ]; then
    EVALUATION="$ROOT/peak_evaluation_released_target"
else
    EVALUATION="$ROOT/peak_evaluation"
fi
if [ -e "$EVALUATION" ] && ! grep -q '"status": "complete"' "$EVALUATION/summary.json" 2>/dev/null; then
    echo "Partial matched evaluation exists: $EVALUATION (move it aside; never overwritten)" >&2; exit 3
fi
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "=== $DATASET $ARM seed $SEED, $STEPS steps ($TASK_KIND; task $TASK_ID) gate v2 on ${SLURMD_NODENAME:-unknown}, job ${SLURM_ARRAY_JOB_ID}_${TASK_ID} ==="

"$PYTHON" -u scripts/check_ig_steps_gate.py --new-attribution "$ROOT/attribution" \
    --saved-attribution "$SAVED" --steps "$STEPS" --output "$ROOT/gmm_gate_v2.json" \
    || { echo "GMM gate v2 failed (stop and post)" >&2; exit 5; }
if ! grep -q '"status": "valid"' "$ROOT/attribution/summary.json"; then
    echo "IG completeness fails at $STEPS steps: not done at this step count; no evaluation"
    exit 0
fi
if grep -q '"status": "complete"' "$EVALUATION/summary.json" 2>/dev/null; then
    echo "Matched evaluation already complete; gate v2 written only"
    exit 0
fi

[ -f "$INPUT" ] || { echo "Missing input: $INPUT" >&2; exit 1; }
if [ "$COLLECTION" = RCC ]; then
    BUDGET="$(test_r_rcc_budget "$DATASET")"
    grep -q '"status": "complete"' "$BUDGET" 2>/dev/null \
        || { echo "RCC released-target budget missing: $BUDGET" >&2; exit 1; }
    K_BIN="$("$PYTHON" -c 'import json,sys; print(int(json.load(open(sys.argv[1]))["K_bin"]))' "$BUDGET")"
    LEGACY_ARGUMENTS=(--no-legacy)
else
    LEGACY_DIR="$(test_r_legacy_dir "$DATASET")"
    K_BIN="$(test_r_k_bin "$DATASET")"
    "$PYTHON" - "$LEGACY_DIR/peak_metrics.json" "$K_BIN" <<'PY'
import json, sys
count = int(json.load(open(sys.argv[1]))["unique_nearest_bins"])
if count != int(sys.argv[2]):
    sys.exit(f"legacy unique_nearest_bins {count} != K_bin {sys.argv[2]}")
PY
    LEGACY_ARGUMENTS=(--legacy-peaks "$LEGACY_DIR/learned_peaks.csv"
                      --legacy-metrics "$LEGACY_DIR/peak_metrics.json")
fi
echo "K_bin = $K_BIN; running the missing matched evaluation"
"$PYTHON" -u scripts/evaluate_spatial_msipl_attributed_peaks.py \
    --input "$INPUT" --attribution-dir "$ROOT/attribution" "${LEGACY_ARGUMENTS[@]}" \
    --output "$EVALUATION" --matched-count "$K_BIN" \
    --peak-tolerance-ppm 10 --consolidated-candidates 50 \
    --ion-images 12 --chunk-size 1024 > "$EVALUATION.stdout.log"
echo "=== $DATASET $ARM seed $SEED, $STEPS steps: gate v2 passed, matched evaluation complete ==="
