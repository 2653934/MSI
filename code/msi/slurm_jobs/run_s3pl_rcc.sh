#!/bin/bash
# Overnight item 3, step 2 (supervisor chat 2026-10-16 22:07): S3PL on RCC with the
# paper's settings (Section 3.3): p = 5, z = 1024, d1 51, d2 1, 10 epochs, batch 16,
# lr 1e-2, dropout 0, reference_spatial_max, released RNG path, n = released
# num_GT_peaks (number_peaks unset), 3 classes (cancer, normal, unannotated).
# Model and evaluator unchanged; input is the staged GBM-layout folder rcc_s3pl/.
# Array: 0-7 seed 1, 8-15 seed 2, 16-23 seed 3 (rcc_sections.sh order).
# Refuses to run unless the adapter gate passed. Outputs in
# reproducibility/s3pl_rcc/seed<S>_released/; a seed is never selected.
#SBATCH --job-name=s3pl-rcc
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --exclusive
#SBATCH --output=logs/s3pl-rcc-%A_%a.out
#SBATCH --error=logs/s3pl-rcc-%A_%a.err

set -eo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/rcc_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_s3pl_rcc.sh}"
if (( TASK_ID < 0 || TASK_ID > 23 )); then
    echo "Invalid array index (0-23): $TASK_ID" >&2; exit 2
fi
SECTION="${RCC_SECTIONS[TASK_ID % 8]}"
RUN="${SECTION#RCC_}"
SEED=$(( TASK_ID / 8 + 1 ))
DATA_PATH="/datasets/zsuliman/msi_data/rcc_s3pl/${RUN}.h5"
GATE="$PROJECT_ROOT/results/validation/s3pl_rcc_adapter_gate/gate.json"
ROOT="$PROJECT_ROOT/reproducibility/s3pl_rcc/seed${SEED}_released"
NAME="${RUN}_Attention3DConvAutoencoder_10epochs_1024_spectral_patch_size_5"
RUN_LOGS="$ROOT/run_logs"
grep -q '"status": "passed"' "$GATE" 2>/dev/null \
    || { echo "S3PL RCC adapter gate has not passed ($GATE); training refused" >&2; exit 1; }
[ -f "$DATA_PATH" ] || { echo "Missing staged input $DATA_PATH" >&2; exit 1; }
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
timed() {
    local record="$1"; shift
    if [ -x /usr/bin/time ]; then
        /usr/bin/time -v -o "$record" "$@"
    else
        echo "GNU time unavailable; use sacct Elapsed/MaxRSS" > "$record"
        "$@"
    fi
}
echo "=== $RUN S3PL RCC seed $SEED on ${SLURMD_NODENAME:-unknown} (job ${SLURM_ARRAY_JOB_ID}_${TASK_ID}) ==="
python - <<'PY'
import sys
import torch
if not torch.cuda.is_available():
    sys.exit("CUDA unavailable; stopped before data load")
probe = torch.ones((32, 32), device="cuda:0")
torch.cuda.synchronize()
print(f"CUDA warm-up passed on {torch.cuda.get_device_name(0)}: {float(probe.sum())}", flush=True)
PY

if [ -f "$ROOT/logs/s3pl/$NAME.json" ]; then
    echo "Training and evaluation already complete"
elif [ -f "$ROOT/checkpoints/baselines/s3pl/$NAME.pt" ]; then
    echo "Partial training artifacts exist for $NAME; move them aside first" >&2; exit 3
else
    cd "$PROJECT_ROOT/baselines/s3pl"
    timed "$RUN_LOGS/${RUN}_train_time.txt" \
        python main.py --data_dir "$DATA_PATH" --artifact_root "$ROOT" \
        --number_classes 3 --spectral_patch_size 5 --peaks_per_spectral_patch 1024 \
        --kernel_depth_d1 51 --kernel_depth_d2 1 --n_epochs 10 --batch_size 16 \
        --learning_rate 0.01 --dropout 0 --normalization reference_spatial_max \
        --random_seed "$SEED" --eval_picking > "$RUN_LOGS/${RUN}_train.log" 2>&1
    echo "Training and native-count evaluation finished"
fi
echo "=== $RUN seed $SEED complete ==="
