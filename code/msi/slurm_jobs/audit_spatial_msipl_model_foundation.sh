#!/bin/bash
#SBATCH --job-name=spatial-model-audit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=logs/spatial-model-audit-%j.out
#SBATCH --error=logs/spatial-model-audit-%j.err

set -euo pipefail

project_root="$HOME/msi"
cd "$project_root"
export PYTHONPATH="$project_root/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2
python_bin="$HOME/miniconda3/envs/s3pl_env/bin/python"

echo "Independent loss, gradient, parameter-count and learning checks"
"$python_bin" -m unittest discover -v \
    -s src/spatial_msipl/tests -p test_model_foundation_audit.py

echo "Existing model, training and exact checkpoint/resume regression checks"
"$python_bin" -m unittest discover -v \
    -s src/spatial_msipl/tests -p test_model.py

echo "MODEL FOUNDATION AUDIT TESTS PASSED"
