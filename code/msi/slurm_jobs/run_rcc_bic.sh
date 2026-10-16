#!/bin/bash
# Overnight item 5 (supervisor chat 2026-10-16 22:07): BIC check of the GMM K on RCC,
# the same procedure and settings as the GBM/CAC gate (d) BIC (run_gate_d_bic.sh):
# select_gmm_k_bic.py on the saved production latents (seed 1, n_init 20, its fixed K
# range), then the "BIC-K segmentation sensitivity, descriptive". Descriptive only:
# the BIC-selected K is reported against the class-informed K = 3. RCC paths only;
# the GBM/CAC outputs are untouched. CPU only, one task per run-arm:
# 0-7 central_only, 8-15 uniform_mean (rcc_sections.sh order). Runs after RCC
# fair scoring (it reads the bin-level fair-scoring summary). Exit 3: stale result.
#SBATCH --job-name=rcc-bic
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output=logs/rcc-bic-%A_%a.out
#SBATCH --error=logs/rcc-bic-%A_%a.err

set -euo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch}"
PROJECT_ROOT="$HOME/msi"
RESULTS="$PROJECT_ROOT/results"
source "$PROJECT_ROOT/slurm_jobs/rcc_sections.sh"
TASK="${SLURM_ARRAY_TASK_ID:?Submit as an array: --array=0-15}"
if (( TASK < 0 || TASK >= 16 )); then echo "Array index out of range: $TASK" >&2; exit 2; fi
DATASET="${RCC_SECTIONS[TASK % 8]}"
ARM="${RCC_ARMS[TASK / 8]}"
INPUT="$(rcc_input_for "$DATASET")"
PRODUCTION="$RESULTS/experiments/rcc_spatial_msipl/${DATASET}_seed1/$ARM/attribution"
FAIR="$RESULTS/diagnostics/fair_scoring_baselines/rcc/bin_level_only/${DATASET}_seed1/$ARM/summary.json"
OUT="$RESULTS/diagnostics/gate_d_bic_rcc/${DATASET}_seed1/$ARM"
grep -q '"status": "complete"' "$FAIR" 2>/dev/null \
    || { echo "RCC fair-scoring summary missing: $FAIR" >&2; exit 1; }
mkdir -p "$OUT"
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "Task $TASK: $DATASET / $ARM, production K=$RCC_GMM_COMPONENTS, node $(hostname)"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
"$PYTHON" -u scripts/select_gmm_k_bic.py --attribution-dir "$PRODUCTION" \
    --production-k "$RCC_GMM_COMPONENTS" --seed 1 --n-init 20 --output "$OUT" > /dev/null
echo "BIC selection written: $OUT/bic_selection.json"
"$PYTHON" -u scripts/bic_segmentation_sensitivity.py --input "$INPUT" \
    --attribution-dir "$PRODUCTION" --bic-selection "$OUT/bic_selection.json" \
    --fair-scoring-summary "$FAIR" --output "$OUT/bic_k_sensitivity" > /dev/null
echo "Sensitivity record written: $OUT/bic_k_sensitivity/summary.json"
