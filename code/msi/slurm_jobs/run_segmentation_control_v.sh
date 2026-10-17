#!/bin/bash
# Test V (protocol 18 Section 6.4; supervisor chat 2026-10-17 12:42): PCA-5 and
# PCA-20 segmentations of the VAE's centre input, ranked by posterior-|PCC| and
# scored against the saved seed-1 VAE central_only posterior-|PCC|. CPU only; no
# retraining, no IG. One array task per section/run:
#   0-7 GBM, 8-15 CAC, 16-23 RCC (rcc_sections.sh order).
# GBM/CAC read the with_approved_partitions central_only fair-scoring summaries and
# score bin level and P1; RCC reads the rcc/bin_level_only summaries and scores bin
# level only (Section 6.1 amendment). The uniform_mean summary is passed for the
# descriptive comparison where it exists (RCC_UH0505_12 has none: IG not done).
# Outputs: results/diagnostics/segmentation_control_V/<collection>/<section>_seed1/
# (submit_segmentation_control_v.sh creates the parents). Exit 3: stale result.
# Memory: the centre inputs are held as float32 (GBM22_2: 4,524 x 85,062, about
# 1.5 GB per copy). Partition at submit time (SBATCH_PARTITION=bigbatch while batch is down).
#SBATCH --job-name=test-v
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/test-v-%A_%a.out
#SBATCH --error=logs/test-v-%A_%a.err

set -euo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch}"
PROJECT_ROOT="$HOME/msi"
RESULTS="$PROJECT_ROOT/results"
source "$PROJECT_ROOT/slurm_jobs/rcc_sections.sh"
GBM_SECTIONS=(GBM108_negative GBM108_positive GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
CAC_SECTIONS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL)
TASK="${SLURM_ARRAY_TASK_ID:?Submit as an array: --array=0-23}"
if (( TASK < 0 || TASK >= 24 )); then echo "Array index out of range: $TASK" >&2; exit 2; fi
FAIR_ROOT="$RESULTS/diagnostics/fair_scoring_baselines"
case $(( TASK / 8 )) in
    0) COLLECTION=GBM; DATASET="${GBM_SECTIONS[TASK % 8]}"
       INPUT="/datasets/zsuliman/msi_data/gbm_massnet/$DATASET.h5"
       ATTRIBUTION="$RESULTS/experiments/spatial_msipl_gmm_integrated_gradients/${DATASET}_seed1/central_only" ;;
    1) COLLECTION=CAC; DATASET="${CAC_SECTIONS[TASK % 8]}"
       INPUT="/datasets/zsuliman/msi_data/cac_msipl/$DATASET.h5"
       ATTRIBUTION="$RESULTS/experiments/spatial_msipl_cac_gmm_integrated_gradients/${DATASET}_seed1/central_only" ;;
    2) COLLECTION=RCC; DATASET="${RCC_SECTIONS[TASK % 8]}"
       INPUT="$(rcc_input_for "$DATASET")"
       ATTRIBUTION="$RESULTS/experiments/rcc_spatial_msipl/${DATASET}_seed1/central_only/attribution" ;;
esac
PARTITION_ARGS=()
if [ "$COLLECTION" = RCC ]; then
    FAIR_DIR="$FAIR_ROOT/rcc/bin_level_only/${DATASET}_seed1"
else
    FAIR_DIR="$FAIR_ROOT/with_approved_partitions/${DATASET}_seed1"
    PARTITION_ARGS=(--partition-dir "$RESULTS/diagnostics/peak_partition_audit/$DATASET")
fi
FAIR="$FAIR_DIR/central_only/summary.json"
UNIFORM_ARGS=()
if [ -f "$FAIR_DIR/uniform_mean/summary.json" ]; then
    UNIFORM_ARGS=(--uniform-fair-scoring-summary "$FAIR_DIR/uniform_mean/summary.json")
elif [ "$DATASET" != RCC_UH0505_12 ]; then
    echo "Missing uniform_mean fair-scoring summary: $FAIR_DIR/uniform_mean/summary.json" >&2; exit 1
fi
[ -f "$FAIR" ] || { echo "Missing fair-scoring summary: $FAIR" >&2; exit 1; }
OUT="$RESULTS/diagnostics/segmentation_control_V/$COLLECTION/${DATASET}_seed1"
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
echo "Task $TASK: $COLLECTION $DATASET on $(hostname)"
"$PYTHON" -u scripts/evaluate_segmentation_control_v.py --input "$INPUT" \
    --attribution-dir "$ATTRIBUTION" --fair-scoring-summary "$FAIR" \
    ${UNIFORM_ARGS[@]+"${UNIFORM_ARGS[@]}"} ${PARTITION_ARGS[@]+"${PARTITION_ARGS[@]}"} \
    --output "$OUT"
