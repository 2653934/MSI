#!/bin/bash
# Gate (d) CPU evaluation of the three pixel-count IG runs for one development
# section and arm (protocol 18 Section 6). No GPU and no CUDA.
#   sbatch slurm_jobs/run_gate_d_evaluation.sh GBM108_positive|40TopL central_only|uniform_mean
# Exit 3: stale result (move aside). Exit 4: the n=12 reproduction gate failed.
# Resources as the fair-scoring task, which peaked at ~0.86 GB on the largest GBM section.
#SBATCH --job-name=gate-d-eval
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output=logs/gate-d-eval-%j.out
#SBATCH --error=logs/gate-d-eval-%j.err

set -euo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch}"
DATASET="${1:?Usage: sbatch $0 SECTION ARM}"
ARM="${2:?Usage: sbatch $0 SECTION ARM}"
case "$ARM" in central_only|uniform_mean) ;; *) echo "Unknown arm: $ARM" >&2; exit 2 ;; esac
PROJECT_ROOT="$HOME/msi"
RESULTS="$PROJECT_ROOT/results"
case "$DATASET" in
    GBM108_positive)
        INPUT="/datasets/zsuliman/msi_data/gbm_massnet/$DATASET.h5"
        PRODUCTION="$RESULTS/experiments/spatial_msipl_gmm_integrated_gradients/${DATASET}_seed1/$ARM"
        SAVED="$RESULTS/experiments/spatial_msipl_gbm_tuned_count_evaluation/${DATASET}_seed1/$ARM" ;;
    40TopL)
        INPUT="/datasets/zsuliman/msi_data/cac_msipl/$DATASET.h5"
        PRODUCTION="$RESULTS/experiments/spatial_msipl_cac_gmm_integrated_gradients/${DATASET}_seed1/$ARM"
        SAVED="$RESULTS/experiments/spatial_msipl_cac_attributed_peak_evaluation/${DATASET}_seed1/$ARM" ;;
    *) echo "Gate (d) sections are GBM108_positive and 40TopL only: $DATASET" >&2; exit 2 ;;
esac
RUN_ROOT="$RESULTS/diagnostics/gate_d_pixel_counts/${DATASET}_seed1/$ARM"
FAIR="$RESULTS/diagnostics/fair_scoring_baselines/bin_level_only/${DATASET}_seed1/$ARM/summary.json"

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
"$HOME/miniconda3/envs/s3pl_env/bin/python" -u scripts/evaluate_gate_d_pixel_counts.py \
    --input "$INPUT" --run-root "$RUN_ROOT" \
    --production-attribution-dir "$PRODUCTION" --saved-evaluation-dir "$SAVED" \
    --fair-scoring-summary "$FAIR" --output "$RUN_ROOT/evaluation"
