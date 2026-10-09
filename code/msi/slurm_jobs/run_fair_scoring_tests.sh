#!/bin/bash
# Compatibility test of the fair-scoring code under the cluster's s3pl_env
# (Python 3.11). CPU-only; synthetic data only; reads no real section.
# Submit with: sbatch slurm_jobs/run_fair_scoring_tests.sh
#SBATCH --job-name=fair-scoring-tests
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=logs/fair-scoring-tests-%j.out
#SBATCH --error=logs/fair-scoring-tests-%j.err

set -euo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch; do not run tests on the login node}"

PROJECT_ROOT="$HOME/msi"
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
RECORD_DIR="$PROJECT_ROOT/results/validation/fair_scoring_env_tests"
mkdir -p "$PROJECT_ROOT/logs" "$RECORD_DIR"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg

"$PYTHON" - <<'PY' | tee "$RECORD_DIR/${SLURM_JOB_ID}_versions.json"
import json, platform, sys
import h5py, matplotlib, numpy, scipy, sklearn
print(json.dumps({
    "python": sys.version.split()[0], "platform": platform.platform(),
    "numpy": numpy.__version__, "scipy": scipy.__version__,
    "sklearn": sklearn.__version__, "h5py": h5py.__version__,
    "matplotlib": matplotlib.__version__,
}, indent=2))
PY

"$PYTHON" -m unittest -v \
    spatial_msipl.tests.test_peak_groups \
    spatial_msipl.tests.test_simple_baselines \
    spatial_msipl.tests.test_gate_d_helpers \
    spatial_msipl.tests.test_provenance \
    spatial_msipl.tests.test_peak_selection \
    spatial_msipl.tests.test_evaluation \
    spatial_msipl.tests.test_fair_scoring_pipeline \
    spatial_msipl.tests.test_fair_scoring_summary \
    2>&1 | tee "$RECORD_DIR/${SLURM_JOB_ID}_unittest.log"
echo "All fair-scoring tests passed under s3pl_env."
