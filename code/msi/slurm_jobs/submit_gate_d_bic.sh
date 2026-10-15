#!/bin/bash
# Login-node submitter for the gate (d) BIC selection: file checks, mkdir and
# sbatch only. Protocol 18 Section 6 ("BIC run specification").
#   bash slurm_jobs/submit_gate_d_bic.sh [--concurrency N]
# Prints the real array job ID (sbatch --parsable).
set -euo pipefail
PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
concurrency=4
while [ "$#" -gt 0 ]; do
    case "$1" in
        --concurrency) concurrency="${2:?}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
RESULTS="$PROJECT_ROOT/results"
for pair in GBM108_positive:spatial_msipl_gmm_integrated_gradients \
            40TopL:spatial_msipl_cac_gmm_integrated_gradients; do
    dataset="${pair%%:*}"; folder="${pair#*:}"
    for arm in central_only uniform_mean; do
        for file in "$RESULTS/experiments/$folder/${dataset}_seed1/$arm/latent_mean.npy" \
                    "$RESULTS/experiments/$folder/${dataset}_seed1/$arm/coordinates_and_gmm.npz" \
                    "$RESULTS/diagnostics/fair_scoring_baselines/bin_level_only/${dataset}_seed1/$arm/summary.json"; do
            [ -f "$file" ] || { echo "Missing input: $file" >&2; exit 2; }
        done
        if [ -e "$RESULTS/diagnostics/gate_d_bic/${dataset}_seed1/$arm" ]; then
            echo "Output already exists; move it aside first: $RESULTS/diagnostics/gate_d_bic/${dataset}_seed1/$arm" >&2
            exit 3
        fi
    done
    # Shared parent folders are created here, before any array task starts.
    mkdir -p "$RESULTS/diagnostics/gate_d_bic/${dataset}_seed1"
done
mkdir -p "$PROJECT_ROOT/logs"
sbatch --parsable --array="0-3%$concurrency" slurm_jobs/run_gate_d_bic.sh
