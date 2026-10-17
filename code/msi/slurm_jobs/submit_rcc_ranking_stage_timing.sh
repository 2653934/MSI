#!/bin/bash
# Login-node submit option for the eight RCC ranking-timing tasks approved in
# supervisor chat 2026-10-17 20:17. CPU computation only, restricted on the
# sbatch command line to the exact bigbatch node used by the corresponding task
# of job 69565. The exact full-ranking reproduction gate in
# time_ranking_stages.py is unchanged. Outputs go to a new root, leaving the 17
# summaries from job 70034 untouched.
#
# Before running: obtain Zayd's explicit OK and check the expanded bigbatch
# running-job count (limit 6). This script performs only mkdir, bash -n, squeue,
# and sbatch; it does not inspect scientific data on the login node.
set -euo pipefail
cd "$HOME/msi"
runner=slurm_jobs/run_ranking_stage_timing.sh
output_root=results/diagnostics/ranking_stage_runtime_rcc_bigbatch
# sacct -j 69565 --format=JobIDRaw,JobID,NodeList -n -P (17 October 2026).
# Array order is test_r_sections.sh RCC order, indices 0-7.
task_nodes=(mscluster71 mscluster74 mscluster76 mscluster77 \
            mscluster55 mscluster74 mscluster71 mscluster76)
bash -n "$runner"
mkdir -p logs "$output_root/provenance"
running="$(squeue -r -u zsuliman -h -t RUNNING -p bigbatch | wc -l)"
if (( running >= 6 )); then
    echo "Refusing submission: $running bigbatch jobs are running (limit 6)." >&2
    exit 1
fi
map_file="$output_root/provenance/task_node_map.txt"
map_content="$({
    echo "source_job=69565"
    for index in "${!task_nodes[@]}"; do
        echo "$index ${task_nodes[index]}"
    done
})"
if [ -e "$map_file" ]; then
    [ "$(cat "$map_file")" = "$map_content" ] || {
        echo "Refusing submission: existing provenance map differs: $map_file" >&2
        exit 1
    }
    echo "Existing task-to-node provenance map matches: $map_file"
else
    printf '%s\n' "$map_content" | tee "$map_file"
fi
for index in "${!task_nodes[@]}"; do
    node="${task_nodes[index]}"
    job="$(sbatch --parsable --partition=bigbatch --nodelist="$node" --array="$index" \
        "$runner" "$output_root")"
    echo "${job%%;*} index=$index partition=bigbatch nodelist=$node source_job=69565" \
        | tee -a "$output_root/provenance/slurm_job_ids.txt"
done
