#!/bin/bash
# Overnight item 2 (supervisor chat 2026-10-16 22:07): S3PL on CAC, released settings
# exactly as the seed-1 CAC runs (run_s3pl_cac.sh with config.json defaults: patch 9,
# 256 peaks per patch, d1 51, d2 1, 10 epochs, batch 16, lr 1e-2, dropout 0,
# reference_spatial_max, released RNG path), native counts (num_GT_peaks), for
# random_seed 2 and 3. No code change: --random_seed already exists in main.py.
# Array: 0-7 seed 2, 8-15 seed 3 (CAC sections in fair_scoring_sections.sh order).
# Artifacts go to reproducibility/s3pl_cac_seeds/seed<S>_released/ and never touch
# the seed-1 artifacts. Seeds are reported side by side; a seed is never selected.
#SBATCH --job-name=s3pl-cac-seeds
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --exclusive
#SBATCH --output=logs/s3pl-cac-seeds-%A_%a.out
#SBATCH --error=logs/s3pl-cac-seeds-%A_%a.err

set -eo pipefail
PROJECT_ROOT="$HOME/msi"
SECTIONS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL)
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_s3pl_cac_seeds.sh}"
if (( TASK_ID < 0 || TASK_ID > 15 )); then
    echo "Invalid array index (0-15): $TASK_ID" >&2; exit 2
fi
DATASET="${SECTIONS[TASK_ID % 8]}"
SEED=$(( TASK_ID / 8 + 2 ))
DATA_PATH="/datasets/zsuliman/msi_data/cac/${DATASET}.imzML"
ROOT="$PROJECT_ROOT/reproducibility/s3pl_cac_seeds/seed${SEED}_released"
NAME="${DATASET}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9"
RUN_LOGS="$ROOT/run_logs"
[ -f "$DATA_PATH" ] || { echo "Missing input $DATA_PATH" >&2; exit 1; }
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
echo "=== $DATASET S3PL seed $SEED on ${SLURMD_NODENAME:-unknown} (job ${SLURM_ARRAY_JOB_ID}_${TASK_ID}) ==="
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
    timed "$RUN_LOGS/${DATASET}_train_time.txt" \
        python main.py --data_dir "$DATA_PATH" --artifact_root "$ROOT" \
        --random_seed "$SEED" > "$RUN_LOGS/${DATASET}_train.log" 2>&1
    echo "Training and native-count evaluation finished"
fi
echo "=== $DATASET seed $SEED complete ==="
