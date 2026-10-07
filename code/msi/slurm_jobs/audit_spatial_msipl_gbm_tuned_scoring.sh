#!/bin/bash
#SBATCH --job-name=gbm-tuned-score-audit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=01:00:00
#SBATCH --array=0-7
#SBATCH --output=logs/gbm-tuned-score-audit-%A_%a.out
#SBATCH --error=logs/gbm-tuned-score-audit-%A_%a.err

set -euo pipefail

project_root="$HOME/msi"
cd "$project_root"
export PYTHONPATH="$project_root/src:$project_root/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2
python_bin="$HOME/miniconda3/envs/s3pl_env/bin/python"

sections=(
    GBM108_positive GBM108_negative GBM12_1 GBM12_2
    GBM22_1 GBM22_2 GBM39_1 GBM39_2
)
index="${SLURM_ARRAY_TASK_ID:?submit as a Slurm array}"
if (( index < 0 || index >= ${#sections[@]} )); then
    echo "Unknown array index: $index" >&2
    exit 2
fi
section="${sections[$index]}"
input="/datasets/zsuliman/msi_data/gbm_massnet/${section}.h5"
evaluation_root="results/experiments/spatial_msipl_gbm_tuned_count_evaluation/${section}_seed1"
output="results/diagnostics/spatial_gbm_tuned_score_foundation/${section}.json"

echo "Independent raw-spectrum tuned-count audit: $section on $(hostname)"
"$python_bin" -m unittest discover -v \
    -s src/spatial_msipl/tests -p test_window_peak_scoring_audit.py
"$python_bin" -u scripts/audit_window_peak_scoring.py \
    --input "$input" \
    --output "$output" \
    "$evaluation_root/central_only" \
    "$evaluation_root/uniform_mean"
