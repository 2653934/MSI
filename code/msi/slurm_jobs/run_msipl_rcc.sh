#!/bin/bash
# Overnight item 4 (supervisor chat 2026-10-16 22:07): legacy msiPL on RCC, the same
# procedure as the CAC legacy reproduction (run_msipl_cac_section.sh): legacy VAE-BN
# fixed Beta 2.5, 100 epochs, batch 128, latent 5, intermediate 512, seed 1337; then
# LearnPeaks Beta tuned over the existing CAC grid (0.0-2.5, step 0.05) toward the
# released target num_GT_peaks with tolerance 50 (paper Section 3.2); then the
# existing evaluator. RCC paths only; the RCC exports need no adapter (the legacy
# loader orients either layout). A run outside +/-50 is recorded by the tuner as
# "closest_outside_tolerance"; the grid is never widened.
# Array: one task per run (rcc_sections.sh order). Outputs never overwrite.
#SBATCH --job-name=msipl-rcc
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --partition=bigbatch
#SBATCH --time=04:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --output=logs/msipl-rcc-%A_%a.out
#SBATCH --error=logs/msipl-rcc-%A_%a.err

set -eo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/rcc_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_msipl_rcc.sh}"
if (( TASK_ID < 0 || TASK_ID >= ${#RCC_SECTIONS[@]} )); then
    echo "Invalid array index: $TASK_ID" >&2; exit 2
fi
DATASET="${RCC_SECTIONS[TASK_ID]}"
RUN="${DATASET#RCC_}"
INPUT="$(rcc_input_for "$DATASET")"
TARGET_PEAKS="$("$HOME/miniconda3/envs/s3pl_env/bin/python" -c 'import ast,sys
tree = ast.parse(open(sys.argv[1]).read())
for node in tree.body:
    if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "num_GT_peaks" for t in node.targets):
        print(ast.literal_eval(node.value)[sys.argv[2]])' "$PROJECT_ROOT/baselines/s3pl/data_configs.py" "$RUN")"
[[ "$TARGET_PEAKS" =~ ^[0-9]+$ ]] || { echo "No released target for $RUN" >&2; exit 1; }
FIXED_OUTPUT="$PROJECT_ROOT/results/baselines/msipl/rcc_fixed_beta/$DATASET"
TUNED_OUTPUT="$PROJECT_ROOT/results/baselines/msipl/rcc/$DATASET"
CHECKPOINT_ROOT="/datasets/zsuliman/msi_checkpoints/baselines/msipl/rcc"
WEIGHTS="$CHECKPOINT_ROOT/$DATASET/msipl_weights.h5"
[ -f "$INPUT" ] || { echo "Missing input: $INPUT" >&2; exit 1; }
mkdir -p "$FIXED_OUTPUT" "$TUNED_OUTPUT" "$CHECKPOINT_ROOT"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate msipl_legacy
export OMP_NUM_THREADS=8
echo "=== $DATASET legacy msiPL (target $TARGET_PEAKS) on ${SLURMD_NODENAME:-unknown} (job ${SLURM_ARRAY_JOB_ID}_${TASK_ID}) ==="
python -m py_compile scripts/run_msipl_legacy_gbm.py scripts/tune_msipl_massnet_beta.py \
    scripts/evaluate_msipl_massnet_peaks.py

if [[ -f "$FIXED_OUTPUT/peak_metrics.json" && -f "$WEIGHTS" ]]; then
    echo "Fixed-Beta training and evaluation already exist; reusing the checkpoint."
elif [[ -f "$WEIGHTS" ]]; then
    echo "Weights exist without fixed-Beta metrics: $WEIGHTS; move aside first" >&2; exit 3
else
    python scripts/run_msipl_legacy_gbm.py --input "$INPUT" --output-dir "$FIXED_OUTPUT" \
        --checkpoint-root "$CHECKPOINT_ROOT" --epochs 100 --batch-size 128 \
        --latent-dim 5 --intermediate-dim 512 --beta 2.5 --seed 1337 \
        > "$FIXED_OUTPUT/training_stdout.log" 2>&1
    python scripts/evaluate_msipl_massnet_peaks.py --input "$INPUT" \
        --peaks "$FIXED_OUTPUT/learned_peaks.csv" --output "$FIXED_OUTPUT" \
        > "$FIXED_OUTPUT/evaluation_stdout.log" 2>&1
fi
[[ -f "$WEIGHTS" ]] || { echo "Expected trained checkpoint not found: $WEIGHTS" >&2; exit 1; }

if [[ -f "$TUNED_OUTPUT/peak_metrics.json" ]]; then
    echo "Paper-aligned metrics already exist; refusing to overwrite them."
else
    python scripts/tune_msipl_massnet_beta.py --input "$INPUT" --weights "$WEIGHTS" \
        --output "$TUNED_OUTPUT" --target-peaks "$TARGET_PEAKS" --tolerance 50 \
        --beta-min 0.0 --beta-max 2.5 --beta-step 0.05 > "$TUNED_OUTPUT/tuning_stdout.log" 2>&1
    python scripts/evaluate_msipl_massnet_peaks.py --input "$INPUT" \
        --peaks "$TUNED_OUTPUT/learned_peaks.csv" --output "$TUNED_OUTPUT" \
        > "$TUNED_OUTPUT/evaluation_stdout.log" 2>&1
fi
echo "tuning status: $(grep -o '"status": "[a-z_]*"' "$TUNED_OUTPUT/beta_selection.json" | head -1)"
echo "=== $DATASET legacy msiPL complete ==="
