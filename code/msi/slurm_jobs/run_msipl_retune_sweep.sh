#!/bin/bash
# msiPL Beta re-tune sweep (protocol 18 Section 6.8; supervisor chat 2026-10-30 12:58
# item 2 and 17:33 ruling). One array task per MSIPL_RETUNE_SECTIONS row:
#   bash slurm_jobs/submit_msipl_retune.sh sweep INDICES   (each submission needs Zayd's OK)
# CPU only, env msipl_legacy, from the saved legacy weights (no retraining):
# retune_msipl_beta.py over Beta -2.0..2.5 step 0.01, targets round(K_bin x m).
# GBM/CAC: m = 1 is the saved list, recomputed at the saved Beta (exit 5 if it does
# not reproduce exactly: stop and post). RCC: m = 1 re-selected. Exit 3: output exists.
# Resources: provisional; set from the GBM22_2 pilot (largest section). No --exclusive.
#SBATCH --job-name=msipl-retune
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=28G
#SBATCH --time=04:00:00
#SBATCH --output=logs/msipl-retune-%A_%a.out
#SBATCH --error=logs/msipl-retune-%A_%a.err

set -eo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/msipl_retune_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_msipl_retune.sh}"
DATASET="$(msipl_retune_section "$TASK_ID")"
COLLECTION="$(test_r_collection "$DATASET")"
INPUT="$(test_r_input_for "$DATASET")"
WEIGHTS="$(msipl_retune_weights "$DATASET")"
OUTPUT="$(msipl_retune_output "$DATASET")"
if [ -e "$OUTPUT/summary.json" ] || [ -e "$OUTPUT/sweep.csv" ] || [ -e "$OUTPUT/m1_reproduction.json" ]; then
    echo "Output already exists: $OUTPUT (never overwritten)" >&2; exit 3
fi
for required in "$INPUT" "$WEIGHTS"; do
    [ -f "$required" ] || { echo "Missing input: $required" >&2; exit 1; }
done
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate msipl_legacy
cd "$PROJECT_ROOT"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 MPLBACKEND=Agg
echo "=== $DATASET ($COLLECTION) msiPL re-tune on ${SLURMD_NODENAME:-unknown}, job ${SLURM_ARRAY_JOB_ID}_${TASK_ID} ==="

SAVED_ARGUMENTS=()
if [ "$COLLECTION" = RCC ]; then
    BUDGET="$(test_r_rcc_budget "$DATASET")"
    grep -q '"status": "complete"' "$BUDGET" 2>/dev/null \
        || { echo "RCC released-target budget missing: $BUDGET" >&2; exit 1; }
    K_BIN="$(python -c 'import json,sys; print(int(json.load(open(sys.argv[1]))["K_bin"]))' "$BUDGET")"
else
    K_BIN="$(test_r_k_bin "$DATASET")"
    SAVED="$(msipl_retune_saved_dir "$DATASET")"
    for required in "$SAVED/beta_selection.json" "$SAVED/learned_peaks.csv" "$SAVED/peak_metrics.json"; do
        [ -f "$required" ] || { echo "Missing saved legacy file: $required" >&2; exit 1; }
    done
    SAVED_BETA="$(python -c 'import json,sys; print(repr(float(json.load(open(sys.argv[1]))["chosen"]["beta"])))' "$SAVED/beta_selection.json")"
    SAVED_ARGUMENTS=(--saved-beta "$SAVED_BETA" --saved-peaks "$SAVED/learned_peaks.csv")
fi
echo "K_bin = $K_BIN ${SAVED_BETA:+(saved Beta $SAVED_BETA)}"
python -m py_compile scripts/retune_msipl_beta.py
mkdir -p "$OUTPUT"
python -u scripts/retune_msipl_beta.py --input "$INPUT" --weights "$WEIGHTS" \
    --output "$OUTPUT" --k-bin "$K_BIN" --latent-dim 5 --intermediate-dim 512 \
    ${SAVED_ARGUMENTS[@]+"${SAVED_ARGUMENTS[@]}"} > "$OUTPUT/retune_stdout.log"
echo "=== $DATASET re-tune complete ==="
