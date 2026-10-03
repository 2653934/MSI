#!/bin/bash
#SBATCH --job-name=window-topology
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:20:00
#SBATCH --output=logs/window-topology-%j.out
#SBATCH --error=logs/window-topology-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1

DATASETS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL)
INPUTS=()
for dataset in "${DATASETS[@]}"; do
    INPUTS+=("/datasets/zsuliman/msi_data/cac_msipl/${dataset}.h5")
done
DATASETS=(GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
for dataset in "${DATASETS[@]}"; do
    INPUTS+=("/datasets/zsuliman/msi_data/gbm_massnet/${dataset}.h5")
done

for input in "${INPUTS[@]}"; do
    if [ ! -f "$input" ]; then
        echo "Missing source HDF5: $input" >&2
        exit 1
    fi
done

python -m unittest discover -s src/spatial_msipl/tests -p test_window_topology_audit.py

python -u scripts/audit_spatial_window_topology.py \
    --output-dir results/diagnostics/spatial_window_topology \
    "${INPUTS[@]}"
