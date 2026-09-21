#!/bin/bash
#SBATCH --job-name=paper-summary
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=00:20:00
#SBATCH --mem=4G
#SBATCH --output=logs/paper-summary-%j.out
#SBATCH --error=logs/paper-summary-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
mkdir -p "$PROJECT_ROOT/logs"
cd "$PROJECT_ROOT"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env

python -u scripts/summarise_publication_results.py \
    --repo-root "$PROJECT_ROOT"

