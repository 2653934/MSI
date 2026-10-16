#!/bin/bash
# Overnight item 6 (supervisor chat 2026-10-16 20:41 item 2, 22:07 item 6): read-only
# ion-image export for the RCC figures, 2 runs (UH0710_33, MH0204_33), uniform_mean
# arm, from the saved bin-level fair-scoring rankings. One CPU task; writes only
# under results/visualisations/rcc/. Refuses to overwrite (exit 3).
#SBATCH --job-name=rcc-ion-export
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=logs/rcc-ion-export-%j.out
#SBATCH --error=logs/rcc-ion-export-%j.err

set -euo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch}"
PROJECT_ROOT="$HOME/msi"
RESULTS="$PROJECT_ROOT/results"
source "$PROJECT_ROOT/slurm_jobs/rcc_sections.sh"
ARM=uniform_mean
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
mkdir -p "$RESULTS/visualisations/rcc"
for DATASET in RCC_UH0710_33 RCC_MH0204_33; do
    "$PYTHON" -u scripts/export_rcc_ion_images.py --input "$(rcc_input_for "$DATASET")" \
        --attribution-dir "$RESULTS/experiments/rcc_spatial_msipl/${DATASET}_seed1/$ARM/attribution" \
        --fair-scoring-dir "$RESULTS/diagnostics/fair_scoring_baselines/rcc/bin_level_only/${DATASET}_seed1/$ARM" \
        --output "$RESULTS/visualisations/rcc/${DATASET}_${ARM}_ion_images.npz"
done
