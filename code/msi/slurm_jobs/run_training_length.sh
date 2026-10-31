#!/bin/bash
# Item 3, C3 training length (supervisor chat 2026-10-30 12:58 item 3, 13:20 approval,
# 20:16 request 4). Code and tests only so far: no submission without a protocol
# section, a checklist and Zayd's OK.
#   bash slurm_jobs/submit_training_length.sh INDICES
# One array task per section-arm: 0 GBM108_positive central_only, 1 GBM108_positive
# uniform_mean, 2 40TopL central_only, 3 40TopL uniform_mean (development sections,
# seed 1, as the production runs).
# Training is the production recipe (3x3, 100 epochs, batch 128, hidden 512, latent 5,
# lr 1e-3, spatial_lambda 0, seed 1, cached loader) plus the opt-in
# --snapshot-epochs 10 25 50. For each of epochs 10, 25, 50 and 100: the production
# GMM + IG call (with --expected-epochs E), the matched evaluation at the production
# K_bin with the legacy list, and the unchanged fair evaluator at bin level (IG and
# posterior-|PCC| at K_bin). The per-epoch training loss is training_history.json.
# Epoch 100 is checked against production by summarise_training_length.py.
# A GMM component below 44 px or an IG status other than valid makes that epoch
# "not done" (recorded; the other epochs continue). New roots only; no overwrite.
#SBATCH --job-name=training-length
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=logs/training-length-%A_%a.out
#SBATCH --error=logs/training-length-%A_%a.err

set -eo pipefail
PROJECT_ROOT="$HOME/msi"
RESULTS="$PROJECT_ROOT/results"
source "$PROJECT_ROOT/slurm_jobs/training_length_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_training_length.sh}"
if (( TASK_ID < 0 || TASK_ID >= 2 * ${#TRAINING_LENGTH_SECTIONS[@]} )); then
    echo "Invalid array index: $TASK_ID" >&2; exit 2
fi
DATASET="${TRAINING_LENGTH_SECTIONS[TASK_ID / 2]}"
ARM="${TRAINING_LENGTH_ARMS[TASK_ID % 2]}"
INPUT="$(test_r_input_for "$DATASET")"
GMM_COMPONENTS="$(test_r_gmm_components "$DATASET")"
K_BIN="$(test_r_k_bin "$DATASET")"
LEGACY_DIR="$(test_r_legacy_dir "$DATASET")"
RESULT_ROOT="$(training_length_result_root "$DATASET" "$ARM")"
CHECKPOINT_DIR="$(training_length_checkpoint_dir "$DATASET" "$ARM")"
for required in "$INPUT" "$LEGACY_DIR/peak_metrics.json" "$LEGACY_DIR/learned_peaks.csv"; do
    [ -f "$required" ] || { echo "Missing input: $required" >&2; exit 1; }
done
mkdir -p "$RESULT_ROOT" "$CHECKPOINT_DIR"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "=== $DATASET $ARM training length (task $TASK_ID) on ${SLURMD_NODENAME:-unknown}, job ${SLURM_ARRAY_JOB_ID}_${TASK_ID} ==="

# Real CUDA warm-up before any model or data load.
"$PYTHON" - <<'PY'
import sys
import torch
if not torch.cuda.is_available():
    sys.exit("CUDA unavailable; stopped before model or data load")
probe = torch.ones((32, 32), device="cuda:0")
torch.cuda.synchronize()
print(f"CUDA warm-up passed on {torch.cuda.get_device_name(0)}: {float(probe.sum())}", flush=True)
PY

CHECKPOINT="$CHECKPOINT_DIR/checkpoint.pt"
if [ -f "$CHECKPOINT" ] && grep -q '"status": "complete"' "$RESULT_ROOT/summary.json" 2>/dev/null; then
    echo "Training already complete"
elif [ -f "$CHECKPOINT" ]; then
    echo "Final checkpoint exists without a complete summary: $CHECKPOINT" >&2; exit 1
else
    RESUME_ARGUMENTS=()
    [ -f "$CHECKPOINT_DIR/checkpoint_latest.pt" ] \
        && RESUME_ARGUMENTS=(--resume-checkpoint "$CHECKPOINT_DIR/checkpoint_latest.pt")
    "$PYTHON" -u scripts/train_spatial_msipl_production.py \
        --input "$INPUT" --output "$RESULT_ROOT" --checkpoint-output "$CHECKPOINT_DIR" \
        --variant "$ARM" --epochs 100 --batch-size 128 --hidden-dim 512 --latent-dim 5 \
        --learning-rate 0.001 --spatial-lambda 0 --seed 1 --checkpoint-interval 5 \
        --snapshot-epochs $TRAINING_LENGTH_SNAPSHOTS \
        --cache-spectra "${RESUME_ARGUMENTS[@]}" >> "$RESULT_ROOT/training_stdout.log"
    echo "Training finished"
fi

for epoch in $TRAINING_LENGTH_SNAPSHOTS 100; do
    if [ "$epoch" = 100 ]; then
        model="$CHECKPOINT"
    else
        model="$CHECKPOINT_DIR/$(printf 'snapshot_epoch%03d.pt' "$epoch")"
    fi
    [ -f "$model" ] || { echo "Missing epoch-$epoch model: $model" >&2; exit 1; }
    root="$RESULT_ROOT/epoch$epoch"
    mkdir -p "$root"
    if ! grep -q '"status": "valid"' "$root/attribution/summary.json" 2>/dev/null; then
        if ! "$PYTHON" -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
                --input "$INPUT" --checkpoint "$model" --expected-epochs "$epoch" \
                --output "$root/attribution" --variant "$ARM" \
                --batch-size 64 --gmm-components "$GMM_COMPONENTS" --gmm-n-init 20 \
                --attribution-per-cluster 12 --faithfulness-per-cluster 32 \
                --ig-steps 64 --ig-internal-batch-size 8 \
                --deletion-budgets 32 128 512 --random-repeats 10 \
                --top-candidates 50 --seed 1 --sampling-seed 1 > "$root/attribution_stdout.log"; then
            echo "epoch $epoch: IG stopped (not done; see attribution_stdout.log)"
            continue
        fi
    fi
    if ! grep -q '"status": "valid"' "$root/attribution/summary.json"; then
        echo "epoch $epoch: IG status is not valid (not done)"
        continue
    fi
    if ! grep -q '"status": "complete"' "$root/peak_evaluation/summary.json" 2>/dev/null; then
        "$PYTHON" -u scripts/evaluate_spatial_msipl_attributed_peaks.py \
            --input "$INPUT" --attribution-dir "$root/attribution" \
            --legacy-peaks "$LEGACY_DIR/learned_peaks.csv" \
            --legacy-metrics "$LEGACY_DIR/peak_metrics.json" \
            --output "$root/peak_evaluation" --matched-count "$K_BIN" \
            --peak-tolerance-ppm 10 --consolidated-candidates 50 \
            --ion-images 12 --chunk-size 1024 > "$root/peak_evaluation.stdout.log"
    fi
    fair="$(training_length_fair_root "$DATASET" "$ARM")/epoch$epoch"
    if ! grep -q '"status": "complete"' "$fair/summary.json" 2>/dev/null; then
        mkdir -p "$fair"
        "$PYTHON" -u scripts/evaluate_fair_scoring_baselines.py \
            --input "$INPUT" --attribution-dir "$root/attribution" \
            --saved-evaluation-dir "$root/peak_evaluation" \
            --legacy-peaks "$LEGACY_DIR/learned_peaks.csv" \
            --legacy-metrics "$LEGACY_DIR/peak_metrics.json" \
            --output "$fair" --random-draws 100 --chunk-size 1024 > "$fair/evaluator_stdout.log"
    fi
    echo "epoch $epoch: $(grep -o '"status": "[a-z]*"' "$fair/summary.json" | head -1)"
done
echo "=== $DATASET $ARM training length complete ==="
