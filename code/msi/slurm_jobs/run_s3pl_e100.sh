#!/bin/bash
# Item C2 (supervisor chat 2026-10-15 13:00 and 15:35): S3PL for 100 epochs,
# seed 1, released RNG path (random_seed 1, no controlled seeds), patch 9 on
# CAC and 3 on GBM, as the existing 10-epoch baselines. Checkpoints at epochs
# 10/25/50/100 (logging-only flag --checkpoint_epochs), each evaluated after
# training at the default count and, on CAC, at the matched count.
# One array task per section (fair_scoring_sections.sh order). Artifacts go to
# reproducibility/s3pl_e100/seed1_released/ and never touch the 10-epoch runs.
#SBATCH --job-name=s3pl-e100
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=10:00:00
#SBATCH --exclusive
#SBATCH --output=logs/s3pl-e100-%A_%a.out
#SBATCH --error=logs/s3pl-e100-%A_%a.err

set -eo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/fair_scoring_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_s3pl_e100.sh}"
DATASET="${FAIR_SECTIONS[TASK_ID]}"
case "$DATASET" in
    GBM*) DATA_PATH="/datasets/zsuliman/msi_data/gbm_massnet/${DATASET}.h5"
          PATCH=3; CLASSES=2; MATCHED="" ;;
    *)    DATA_PATH="/datasets/zsuliman/msi_data/cac/${DATASET}.imzML"
          PATCH=9; CLASSES=3
          case "$DATASET" in
              40TopL) MATCHED=315 ;; 160TopL) MATCHED=210 ;; 200TopL) MATCHED=221 ;;
              240TopL) MATCHED=255 ;; 280TopL) MATCHED=245 ;; 360TopL) MATCHED=247 ;;
              400TopL) MATCHED=133 ;; 520TopL) MATCHED=232 ;;
          esac ;;
esac
ROOT="$PROJECT_ROOT/reproducibility/s3pl_e100/seed1_released"
NAME="${DATASET}_Attention3DConvAutoencoder_100epochs_256_spectral_patch_size_${PATCH}"
RUN_LOGS="$ROOT/run_logs"
[ -f "$DATA_PATH" ] || { echo "Missing input $DATA_PATH" >&2; exit 1; }
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
# Peak RSS and elapsed time of each step when GNU time exists (else use sacct).
timed() {
    local record="$1"; shift
    if [ -x /usr/bin/time ]; then
        /usr/bin/time -v -o "$record" "$@"
    else
        echo "GNU time unavailable; use sacct Elapsed/MaxRSS" > "$record"
        "$@"
    fi
}
echo "=== $DATASET S3PL 100 epochs on ${SLURMD_NODENAME:-unknown} (job ${SLURM_ARRAY_JOB_ID}_${TASK_ID}) ==="
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
    echo "Training already complete"
elif [ -f "$ROOT/checkpoints/baselines/s3pl/$NAME.pt" ] \
        || compgen -G "$ROOT/checkpoints/baselines/s3pl/${NAME}_epoch*.pt" > /dev/null; then
    echo "Partial training artifacts exist for $NAME; move them aside first" >&2; exit 3
else
    cd "$PROJECT_ROOT/baselines/s3pl"
    timed "$RUN_LOGS/${DATASET}_train_time.txt" \
        python main.py \
        --data_dir "$DATA_PATH" --artifact_root "$ROOT" \
        --number_classes "$CLASSES" --n_epochs 100 --spectral_patch_size "$PATCH" \
        --peaks_per_spectral_patch 256 --batch_size 16 --learning_rate 0.01 \
        --kernel_depth_d1 51 --kernel_depth_d2 1 --dropout 0 \
        --normalization reference_spatial_max --input-context-mode none \
        --random_seed 1 --eval_picking --checkpoint_epochs 10 25 50 100 \
        > "$RUN_LOGS/${DATASET}_train.log" 2>&1
    cd "$PROJECT_ROOT"
    echo "Training and 100-epoch evaluation finished"
fi

cd "$PROJECT_ROOT"
matched_args=()
[ -n "$MATCHED" ] && matched_args=(--matched-count "$MATCHED")
timed "$RUN_LOGS/${DATASET}_checkpoint_eval_time.txt" \
    python -u scripts/evaluate_s3pl_epoch_checkpoints.py \
    --log-json "$ROOT/logs/s3pl/$NAME.json" --epochs 10 25 50 100 "${matched_args[@]}" \
    > "$RUN_LOGS/${DATASET}_checkpoint_eval.log" 2>&1
echo "=== $DATASET checkpoint evaluations complete ==="
