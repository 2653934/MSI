#!/bin/bash

#SBATCH --job-name=cac-visualise
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --output=logs/cac-visualise-%j.out
#SBATCH --error=logs/cac-visualise-%j.err

echo "=== CAC VISUALISATION JOB ==="
echo "Date: $(date)"
echo "Username: $USER"
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Node: $HOSTNAME"
echo "Working Directory: $PWD"
echo "=============================="

cd "$SLURM_SUBMIT_DIR"

echo ""
echo "--- Python Environment ---"

source /home-mscluster/zsuliman/.conda/envs/msi_env/bin/activate

echo "Python: $(which python)"
python --version

echo ""
echo "--- Running CAC Visualisation ---"

python scripts/visualise_cac.py \
    --dataset 40TopL \
    --data-dir /datasets/zsuliman/msi_data/cac \
    --output-dir results/visualisations/cac

echo ""
echo "=== JOB COMPLETE ==="
echo "Results:"
echo "results/visualisations/cac/40TopL/"