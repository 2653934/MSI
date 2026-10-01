#!/bin/bash
#SBATCH --job-name=spatial-window-all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=16:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster62,mscluster65,mscluster74,mscluster75,mscluster76,mscluster83
#SBATCH --output=logs/spatial-window-all-%A_%a.out
#SBATCH --error=logs/spatial-window-all-%A_%a.err

set -euo pipefail

# Indices 0-2 are the finished 40TopL development pilot. All other sections
# are confirmation sections; this index mapping is shared with the audit tool.
DATASETS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
          GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
ARMS=(uniform_p5 zero_p3 shuffled_p3)
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit this script as a Slurm array}"
if (( TASK_ID < 0 || TASK_ID >= ${#DATASETS[@]} * ${#ARMS[@]} )); then
    echo "Invalid array index: $TASK_ID" >&2
    exit 2
fi
DATASET="${DATASETS[TASK_ID / 3]}"
ARM="${ARMS[TASK_ID % 3]}"
echo "Array task $TASK_ID: $DATASET $ARM on ${SLURMD_NODENAME:-unknown}"
bash "$HOME/msi/slurm_jobs/run_spatial_window_pilot_training.sh" "$DATASET" "$ARM"
