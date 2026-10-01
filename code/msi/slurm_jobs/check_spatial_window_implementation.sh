#!/bin/bash
#SBATCH --job-name=window-tests
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=00:15:00
#SBATCH --mem=4G
#SBATCH --output=logs/window-tests-%j.out
#SBATCH --error=logs/window-tests-%j.err

set -eo pipefail
cd "$HOME/msi"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
echo "CPU-only window implementation checks; no dataset or production checkpoint is changed."
date -u
python -m unittest -v spatial_msipl.tests.test_preprocessing spatial_msipl.tests.test_neighbourhood spatial_msipl.tests.test_windows spatial_msipl.tests.test_attribution
echo "WINDOW IMPLEMENTATION TESTS PASSED"
