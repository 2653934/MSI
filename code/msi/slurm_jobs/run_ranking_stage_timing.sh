#!/bin/bash
# Ranking-stage timing (supervisor chat 2026-10-17 09:48, item 2; descriptive only).
# One array task per section/run, uniform_mean, seed 1, on saved artifacts; CPU only:
#   SBATCH_PARTITION=bigbatch sbatch --parsable --array=0-23%2 slurm_jobs/run_ranking_stage_timing.sh
# Index i: TEST_R_SECTIONS[i] (RCC 0-7, CAC 8-15, GBM 16-23; test_r_sections.sh order).
# time_ranking_stages.py times the GMM posterior, posterior-|PCC|, Moran's I, mean
# intensity and the oracle (median of 3 repeats) and checks every ranking against the
# saved seed-1 fair-scoring ranking. --exclusive keeps other jobs off the node while
# timing; the threads are fixed at 2, as in the fair-scoring evaluator. The CPU model
# is recorded per task, and the summariser refuses a table that mixes CPU models.
# Memory: the whole section is held in memory twice (raw and TIC-normalised float64);
# GBM22_2 (4,524 px x 85,062 bins) is about 3.1 GB per copy.
#SBATCH --job-name=ranking-timing
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=24G
#SBATCH --time=02:00:00
#SBATCH --exclusive
#SBATCH --output=logs/ranking-timing-%A_%a.out
#SBATCH --error=logs/ranking-timing-%A_%a.err

# Paths for one section: input, seed-1 uniform_mean attribution, seed-1 fair summary.
ranking_timing_paths() {
    local section="$1" results="$HOME/msi/results"
    test_r_input_for "$section"
    case "$section" in
        RCC_*)
            echo "$results/experiments/rcc_spatial_msipl/${section}_seed1/uniform_mean/attribution"
            echo "$results/diagnostics/fair_scoring_baselines/rcc/bin_level_only/${section}_seed1/uniform_mean/summary.json" ;;
        *TopL)
            echo "$results/experiments/spatial_msipl_cac_gmm_integrated_gradients/${section}_seed1/uniform_mean"
            echo "$results/diagnostics/fair_scoring_baselines/bin_level_only/${section}_seed1/uniform_mean/summary.json" ;;
        GBM*)
            echo "$results/experiments/spatial_msipl_gmm_integrated_gradients/${section}_seed1/uniform_mean"
            echo "$results/diagnostics/fair_scoring_baselines/bin_level_only/${section}_seed1/uniform_mean/summary.json" ;;
        *) return 1 ;;
    esac
}

if [ "${1:-}" = "--paths-only" ]; then   # sourced by the unit test
    source "$(dirname "${BASH_SOURCE[0]}")/test_r_sections.sh"
    return 0 2>/dev/null || exit 0
fi

set -euo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/test_r_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit as an array: --array=0-23}"
if (( TASK_ID < 0 || TASK_ID >= ${#TEST_R_SECTIONS[@]} )); then
    echo "Invalid array index: $TASK_ID" >&2; exit 2
fi
DATASET="${TEST_R_SECTIONS[TASK_ID]}"
mapfile -t PATHS < <(ranking_timing_paths "$DATASET")
INPUT="${PATHS[0]}"; ATTRIBUTION="${PATHS[1]}"; FAIR_SUMMARY="${PATHS[2]}"
OUTPUT="$PROJECT_ROOT/results/diagnostics/ranking_stage_runtime/${DATASET}_seed1/uniform_mean"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "=== $DATASET ranking-stage timing on ${SLURMD_NODENAME:-unknown} (job ${SLURM_ARRAY_JOB_ID}_${TASK_ID}) ==="

FAIR_ARGUMENTS=(--fair-summary "$FAIR_SUMMARY")
if [ ! -f "$FAIR_SUMMARY" ]; then
    # RCC_UH0505_12 uniform_mean has no seed-1 fair-scoring result (IG not done);
    # it is timed with the ranking check labelled "not available".
    echo "No seed-1 fair-scoring summary for $DATASET; ranking check not available"
    FAIR_ARGUMENTS=()
fi
mkdir -p "$(dirname "$OUTPUT")"
"$PYTHON" -u scripts/time_ranking_stages.py --input "$INPUT" --attribution-dir "$ATTRIBUTION" \
    "${FAIR_ARGUMENTS[@]}" --output "$OUTPUT" --repeats 3 --chunk-size 1024
echo "=== $DATASET complete ==="
