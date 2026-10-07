#!/bin/bash
#SBATCH --job-name=spatial-data-audit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --array=0-3%2
#SBATCH --output=logs/spatial-data-audit-%A_%a.out
#SBATCH --error=logs/spatial-data-audit-%A_%a.err

set -euo pipefail

project_root="$HOME/msi"
cd "$project_root"
export PYTHONPATH="$project_root/src:$project_root/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2
python_bin="$HOME/miniconda3/envs/s3pl_env/bin/python"

case "${SLURM_ARRAY_TASK_ID:?submit as a Slurm array}" in
    0)
        section=40TopL
        collection=cac
        input="/datasets/zsuliman/msi_data/cac_msipl/${section}.h5"
        mask="/datasets/zsuliman/msi_data/cac/masks/${section}_mask.npy"
        source="/datasets/zsuliman/msi_data/cac/${section}.imzML"
        ;;
    1)
        section=280TopL
        collection=cac
        input="/datasets/zsuliman/msi_data/cac_msipl/${section}.h5"
        mask="/datasets/zsuliman/msi_data/cac/masks/${section}_mask.npy"
        source="/datasets/zsuliman/msi_data/cac/${section}.imzML"
        ;;
    2)
        section=GBM108_positive
        collection=gbm
        input="/datasets/zsuliman/msi_data/gbm_massnet/${section}.h5"
        mask="/datasets/zsuliman/msi_data/gbm_massnet/masks/${section}_mask.npy"
        source=
        ;;
    3)
        section=GBM22_2
        collection=gbm
        input="/datasets/zsuliman/msi_data/gbm_massnet/${section}.h5"
        mask="/datasets/zsuliman/msi_data/gbm_massnet/masks/${section}_mask.npy"
        source=
        ;;
    *)
        echo "Unknown array index: $SLURM_ARRAY_TASK_ID" >&2
        exit 2
        ;;
esac

echo "Auditing $section on $(hostname) (input files are read-only)"
"$python_bin" -m unittest discover -s src/spatial_msipl/tests -p test_data_contract_audit.py

arguments=(
    --h5 "$input"
    --mask "$mask"
    --collection "$collection"
    --output "results/diagnostics/spatial_msipl_data_contract/$section"
)
if [[ -n "$source" ]]; then
    arguments+=(--source-imzml "$source")
fi
"$python_bin" -u scripts/audit_spatial_msipl_data_contract.py "${arguments[@]}"
