#!/bin/bash
# Gate (d) BIC selection of GMM K on the saved production latents, one array
# task per section-arm (protocol 18 Section 6, "BIC run specification").
# CPU only; no GPU, no IG at any K. Each task runs select_gmm_k_bic.py, then the
# optional "BIC-K segmentation sensitivity, descriptive" (it computes nothing
# when BIC supports the production K).
#   sbatch --parsable --array=0-3%CONCURRENCY slurm_jobs/run_gate_d_bic.sh
# Task map: 0 GBM108_positive/central_only, 1 GBM108_positive/uniform_mean,
#           2 40TopL/central_only, 3 40TopL/uniform_mean.
# Create results/diagnostics/gate_d_bic/<section>_seed1/ before submitting.
# Exit 3: stale result (move aside). Memory as the gate (d) CPU evaluation.
#SBATCH --job-name=gate-d-bic
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output=logs/gate-d-bic-%A_%a.out
#SBATCH --error=logs/gate-d-bic-%A_%a.err

set -euo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch}"
: "${SLURM_ARRAY_TASK_ID:?Submit as an array: --array=0-3}"
SECTIONS=(GBM108_positive GBM108_positive 40TopL 40TopL)
ARMS=(central_only uniform_mean central_only uniform_mean)
TASK="$SLURM_ARRAY_TASK_ID"
if [ "$TASK" -lt 0 ] || [ "$TASK" -ge "${#SECTIONS[@]}" ]; then
    echo "Array index out of range: $TASK" >&2; exit 2
fi
DATASET="${SECTIONS[$TASK]}"
ARM="${ARMS[$TASK]}"
PROJECT_ROOT="$HOME/msi"
RESULTS="$PROJECT_ROOT/results"
case "$DATASET" in
    GBM108_positive)
        INPUT="/datasets/zsuliman/msi_data/gbm_massnet/$DATASET.h5"
        PRODUCTION="$RESULTS/experiments/spatial_msipl_gmm_integrated_gradients/${DATASET}_seed1/$ARM"
        PRODUCTION_K=2 ;;
    40TopL)
        INPUT="/datasets/zsuliman/msi_data/cac_msipl/$DATASET.h5"
        PRODUCTION="$RESULTS/experiments/spatial_msipl_cac_gmm_integrated_gradients/${DATASET}_seed1/$ARM"
        PRODUCTION_K=3 ;;
esac
OUT="$RESULTS/diagnostics/gate_d_bic/${DATASET}_seed1/$ARM"
FAIR="$RESULTS/diagnostics/fair_scoring_baselines/bin_level_only/${DATASET}_seed1/$ARM/summary.json"
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "Task $TASK: $DATASET / $ARM, production K=$PRODUCTION_K, node $(hostname)"

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
# Both scripts print only status lines; the outcome is read from the JSON after sync.
"$PYTHON" -u scripts/select_gmm_k_bic.py --attribution-dir "$PRODUCTION" \
    --production-k "$PRODUCTION_K" --seed 1 --n-init 20 --output "$OUT" > /dev/null
echo "BIC selection written: $OUT/bic_selection.json"
"$PYTHON" -u scripts/bic_segmentation_sensitivity.py --input "$INPUT" \
    --attribution-dir "$PRODUCTION" --bic-selection "$OUT/bic_selection.json" \
    --fair-scoring-summary "$FAIR" --output "$OUT/bic_k_sensitivity" > /dev/null
echo "Sensitivity record written: $OUT/bic_k_sensitivity/summary.json"
