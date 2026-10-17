#!/bin/bash
# Test V reconstruction addendum (supervisor chat 2026-10-17 20:17).
# CPU only, batch partition, one task per Test V section/run:
# 0-7 GBM, 8-15 CAC, 16-23 RCC. Uses Test V's saved summary as the
# explained-variance validity gate and writes only to the new output root.
# Peak memory is dominated by the largest float32 pixels x bins PCA input and
# reconstruction plus sklearn workspace; 16 GB matches run_segmentation_control_v.sh.
#SBATCH --job-name=pca-recon-v
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/pca-recon-v-%A_%a.out
#SBATCH --error=logs/pca-recon-v-%A_%a.err

set -euo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch}"
PROJECT_ROOT="$HOME/msi"
RESULTS="$PROJECT_ROOT/results"
source "$PROJECT_ROOT/slurm_jobs/rcc_sections.sh"
GBM_SECTIONS=(GBM108_negative GBM108_positive GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
CAC_SECTIONS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL)
TASK="${SLURM_ARRAY_TASK_ID:?Submit as an array: --array=0-23}"
if (( TASK < 0 || TASK >= 24 )); then echo "Array index out of range: $TASK" >&2; exit 2; fi
case $(( TASK / 8 )) in
    0) COLLECTION=GBM; DATASET="${GBM_SECTIONS[TASK % 8]}"
       INPUT="/datasets/zsuliman/msi_data/gbm_massnet/$DATASET.h5" ;;
    1) COLLECTION=CAC; DATASET="${CAC_SECTIONS[TASK % 8]}"
       INPUT="/datasets/zsuliman/msi_data/cac_msipl/$DATASET.h5" ;;
    2) COLLECTION=RCC; DATASET="${RCC_SECTIONS[TASK % 8]}"
       INPUT="$(rcc_input_for "$DATASET")" ;;
esac
TEST_V="$RESULTS/diagnostics/segmentation_control_V/$COLLECTION/${DATASET}_seed1/summary.json"
OUT="$RESULTS/diagnostics/pca_reconstruction_V/$COLLECTION/${DATASET}_seed1"
[ -f "$TEST_V" ] || { echo "Missing saved Test V summary: $TEST_V" >&2; exit 1; }
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "Task $TASK: $COLLECTION $DATASET on $(hostname)"
"$PYTHON" -u scripts/evaluate_pca_reconstruction_v.py --input "$INPUT" \
    --test-v-summary "$TEST_V" --output "$OUT"

