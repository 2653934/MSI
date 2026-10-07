#!/bin/bash
#SBATCH --job-name=spatial-score-audit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=01:00:00
#SBATCH --array=0-15
#SBATCH --output=logs/spatial-score-audit-%A_%a.out
#SBATCH --error=logs/spatial-score-audit-%A_%a.err

set -euo pipefail

project_root="$HOME/msi"
cd "$project_root"
export PYTHONPATH="$project_root/src:$project_root/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2
python_bin="$HOME/miniconda3/envs/s3pl_env/bin/python"

sections=(
    40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
    GBM108_positive GBM108_negative GBM12_1 GBM12_2
    GBM22_1 GBM22_2 GBM39_1 GBM39_2
)
index="${SLURM_ARRAY_TASK_ID:?submit as a Slurm array}"
if (( index < 0 || index >= ${#sections[@]} )); then
    echo "Unknown array index: $index" >&2
    exit 2
fi
section="${sections[$index]}"
if (( index < 8 )); then
    input="/datasets/zsuliman/msi_data/cac_msipl/${section}.h5"
    baseline="results/experiments/spatial_msipl_cac_attributed_peak_evaluation/${section}_seed1"
else
    input="/datasets/zsuliman/msi_data/gbm_massnet/${section}.h5"
    baseline="results/experiments/spatial_msipl_attributed_peak_evaluation/${section}_seed1"
fi

echo "Checking independent PCC/F1/mSCF1 scoring for $section on $(hostname)"
"$python_bin" -m unittest discover -v \
    -s src/spatial_msipl/tests -p test_window_peak_scoring_audit.py

window="results/experiments/spatial_msipl_window_pilot/${section}_seed1"
attention="results/experiments/spatial_attention_context/${section}_seed1"
evaluations=(
    "$baseline/central_only"
    "$baseline/uniform_mean"
    "$window/uniform_p5/peak_evaluation"
    "$window/zero_p3/peak_evaluation"
    "$window/shuffled_p3/peak_evaluation"
    "$attention/real_attention/peak_evaluation"
)
if [[ "$section" == "160TopL" || "$section" == "GBM22_2" ]]; then
    evaluations+=("$attention/shuffled_attention/peak_evaluation")
fi
"$python_bin" -u scripts/audit_window_peak_scoring.py \
    --input "$input" \
    --output "results/diagnostics/spatial_score_foundation/${section}.json" \
    "${evaluations[@]}"
