#!/bin/bash
#SBATCH --job-name=attention-check
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=00:45:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster45,mscluster50,mscluster51,mscluster65,mscluster83
#SBATCH --output=logs/attention-check-%j.out
#SBATCH --error=logs/attention-check-%j.err

set -eo pipefail
PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4
echo "Attention scaling diagnostic: job $SLURM_JOB_ID on $(hostname)"
python -m unittest discover -s src/spatial_msipl/tests -p test_attention_scaling.py -v
python -u scripts/check_spatial_attention_scaling.py \
    --input /datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5 \
    --checkpoint /datasets/zsuliman/msi_checkpoints/spatial_msipl/production/GBM108_positive_seed1/attention/checkpoint.pt \
    --output "$PROJECT_ROOT/results/validation/attention_scaling/job_$SLURM_JOB_ID" \
    --samples 32 --batch-size 16 --steps 20
