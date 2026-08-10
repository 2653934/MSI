#!/bin/bash
#SBATCH --job-name=cac-masks
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=/home-mscluster/zsuliman/msi/logs/cac-masks-%j.out
#SBATCH --error=/home-mscluster/zsuliman/msi/logs/cac-masks-%j.err

echo "=== CAC MASK INSPECTION ==="
echo "Date: "$(date)
echo "Username: "$USER
echo "Job ID: "$SLURM_JOB_ID
echo "Job Name: "$SLURM_JOB_NAME
echo "Node: "$HOSTNAME
echo "Working Directory: "$PWD
echo "============================"
echo ""

cd /home-mscluster/zsuliman/msi

PYTHON=/home-mscluster/zsuliman/.conda/envs/msi_env/bin/python

echo "--- Python ---"
echo "Python: $PYTHON"
$PYTHON --version
echo ""

echo "--- Inspecting CAC Masks ---"
$PYTHON scripts/inspect_cac_masks.py

echo ""
echo "=== Inspection Complete ==="