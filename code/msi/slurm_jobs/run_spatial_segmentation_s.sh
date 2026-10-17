#!/bin/bash
# Test S (protocol 18 Section 6.2; supervisor chat 2026-10-17 08:04): spatially
# regularised segmentation on the saved production artifacts. CPU only; no
# retraining, no IG. One array task per section/run, both arms in each task:
#   0-7 GBM, 8-15 CAC, 16-23 RCC (rcc_sections.sh order).
# GBM/CAC read the with_approved_partitions fair-scoring summaries and score bin
# level and P1; RCC reads the bin_level_only summaries and scores bin level only
# (Section 6.1 amendment). RCC uniform_mean UH0505_12 has no fair-scoring summary
# (IG not done) and is reported "not done"; any other missing input fails the task.
# Outputs: results/diagnostics/spatial_segmentation_S/<collection>/<section>_seed1/<arm>/
# (submit_spatial_segmentation_s.sh creates the parents). Exit 3: stale result.
# Partition at submit time (SBATCH_PARTITION=bigbatch while batch is down).
#SBATCH --job-name=test-s
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --output=logs/test-s-%A_%a.out
#SBATCH --error=logs/test-s-%A_%a.err

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
       INPUT="/datasets/zsuliman/msi_data/gbm_massnet/$DATASET.h5" ;;
    1) COLLECTION=CAC; DATASET="${CAC_SECTIONS[TASK % 8]}"
       INPUT="/datasets/zsuliman/msi_data/cac_msipl/$DATASET.h5" ;;
    2) COLLECTION=RCC; DATASET="${RCC_SECTIONS[TASK % 8]}"
       INPUT="$(rcc_input_for "$DATASET")" ;;
esac
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
echo "Task $TASK: $COLLECTION $DATASET on $(hostname)"
for ARM in central_only uniform_mean; do
    OUT="$RESULTS/diagnostics/spatial_segmentation_S/$COLLECTION/${DATASET}_seed1/$ARM"
    PARTITION_ARGS=()
    case "$COLLECTION" in
        GBM) ATTRIBUTION="$RESULTS/experiments/spatial_msipl_gmm_integrated_gradients/${DATASET}_seed1/$ARM" ;;
        CAC) ATTRIBUTION="$RESULTS/experiments/spatial_msipl_cac_gmm_integrated_gradients/${DATASET}_seed1/$ARM" ;;
        RCC) ATTRIBUTION="$RESULTS/experiments/rcc_spatial_msipl/${DATASET}_seed1/$ARM/attribution" ;;
    esac
    if [ "$COLLECTION" = RCC ]; then
        FAIR="$FAIR_ROOT/rcc/bin_level_only/${DATASET}_seed1/$ARM/summary.json"
    else
        FAIR="$FAIR_ROOT/with_approved_partitions/${DATASET}_seed1/$ARM/summary.json"
        PARTITION_ARGS=(--partition-dir "$RESULTS/diagnostics/peak_partition_audit/$DATASET")
    fi
    if [ ! -f "$FAIR" ]; then
        if [ "$DATASET/$ARM" = "RCC_UH0505_12/uniform_mean" ]; then
            echo "$DATASET/$ARM: not done (IG completeness failed at 64 steps); skipped by design"
            continue
        fi
        echo "Missing fair-scoring summary: $FAIR" >&2; exit 1
    fi
    "$PYTHON" -u scripts/evaluate_spatial_segmentation_s.py --input "$INPUT" \
        --attribution-dir "$ATTRIBUTION" --fair-scoring-summary "$FAIR" \
        ${PARTITION_ARGS[@]+"${PARTITION_ARGS[@]}"} --output "$OUT"
done
