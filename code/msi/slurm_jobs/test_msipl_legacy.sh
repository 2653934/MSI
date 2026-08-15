#!/bin/bash
#SBATCH --job-name=msipl-legacy-test
#SBATCH --partition=bigbatch
#SBATCH --output=logs/msipl-legacy-test-%j.out
#SBATCH --error=logs/msipl-legacy-test-%j.err
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1

set -e

echo "=========================================="
echo "      LEGACY msiPL TRAINING SMOKE TEST"
echo "=========================================="

echo "Date: $(date)"
echo "User: $USER"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Working directory: $(pwd)"
echo

# --------------------------------------------------
# Legacy environment
# --------------------------------------------------

source ~/miniconda3/etc/profile.d/conda.sh
conda activate msipl_legacy

echo "--- Python ---"
which python
python --version

echo "--- TensorFlow / Keras ---"
python -c "import tensorflow; print('TensorFlow:', tensorflow.__version__)"
python -c "import keras; print('Keras:', keras.__version__)"
echo

# --------------------------------------------------
# Project
# --------------------------------------------------

cd ~/msi/baselines/msipl

# --------------------------------------------------
# Tiny synthetic dataset test
# --------------------------------------------------

python - <<'PY'
import numpy as np

from Computational_Model_legacy import VAE_BN

np.random.seed(0)

x = np.random.rand(
    20,
    21241
).astype("float32")

print("Synthetic data shape:", x.shape)

model_builder = VAE_BN(
    nSpecFeatures=21241,
    intermediate_dim=512,
    latent_dim=5,
)

model, encoder = model_builder.get_architecture()

print()
print("Starting tiny legacy training test...")

history = model.fit(
    x,
    epochs=1,
    batch_size=4,
    shuffle=True,
    verbose=1,
)

print()
print("======================================")
print("LEGACY msiPL TRAINING OK")
print("Loss:", history.history["loss"])
print("======================================")
PY

echo
echo "=========================================="
echo "           SMOKE TEST COMPLETE"
echo "=========================================="