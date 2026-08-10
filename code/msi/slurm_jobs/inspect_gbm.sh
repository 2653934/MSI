#!/bin/bash
#SBATCH --job-name=gbm-inspect
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=/home-mscluster/zsuliman/msi/logs/gbm-inspect-%j.out
#SBATCH --error=/home-mscluster/zsuliman/msi/logs/gbm-inspect-%j.err

echo "=== GBM DATASET INSPECTION ==="
echo "Date: "$(date)
echo "Username: "$USER
echo "Job ID: "$SLURM_JOB_ID
echo "Job Name: "$SLURM_JOB_NAME
echo "Node: "$HOSTNAME
echo "Working Directory: "$PWD
echo "=============================="
echo ""

cd /home-mscluster/zsuliman/msi

PYTHON=/home-mscluster/zsuliman/.conda/envs/msi_env/bin/python

echo "--- Python ---"
echo "Python: $PYTHON"
$PYTHON --version
echo ""

echo "--- Inspecting GBM HDF5 Files ---"
$PYTHON scripts/inspect_gbm.py

echo ""
echo "=== Inspection Complete ==="