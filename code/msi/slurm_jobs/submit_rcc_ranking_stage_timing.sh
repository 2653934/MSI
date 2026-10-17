#!/bin/bash
# Login-node submit option for the eight RCC ranking-timing tasks approved in
# supervisor chat 2026-10-17 20:17. CPU computation only, restricted on the
# sbatch command line to the bigbatch nodes used by job 69565. The exact full-
# ranking reproduction gate in time_ranking_stages.py is unchanged. Outputs go
# to a new root, leaving the 17 summaries from job 70034 untouched.
#
# Before running: obtain Zayd's explicit OK and check the expanded bigbatch
# running-job count (limit 6). This script performs only mkdir, bash -n, squeue,
# and sbatch; it does not inspect scientific data on the login node.
set -euo pipefail
cd "$HOME/msi"
runner=slurm_jobs/run_ranking_stage_timing.sh
output_root=results/diagnostics/ranking_stage_runtime_rcc_bigbatch
nodes=mscluster55,mscluster71,mscluster74,mscluster76,mscluster77
bash -n "$runner"
mkdir -p logs "$output_root/provenance"
running="$(squeue -r -u zsuliman -h -t RUNNING -p bigbatch | wc -l)"
if (( running >= 6 )); then
    echo "Refusing submission: $running bigbatch jobs are running (limit 6)." >&2
    exit 1
fi
job="$(sbatch --parsable --partition=bigbatch --nodelist="$nodes" --array=0-7%2 \
    "$runner" "$output_root")"
echo "${job%%;*} indices=0-7 concurrency=2 partition=bigbatch nodelist=$nodes" \
    | tee -a "$output_root/provenance/slurm_job_ids.txt"
