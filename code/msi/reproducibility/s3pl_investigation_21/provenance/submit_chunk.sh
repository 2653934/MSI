#!/usr/bin/env bash
# Investigation 21 chunk submitter (protocol 18 Section 6.7; chat 2026-10-20 15:33).
# Piped to the login node: [DRY_RUN=1] [PROV=<provenance dir>] bash -s -- <indices> <label> [afterok-job]
# PROV defaults to the Part B/D folder; Part C uses reproducibility/s3pl_investigation_21/part_c/provenance.
# <indices> is a Slurm array list such as 32,37,38 or 60-83. Refuses to submit if any
# selected task's output subfolders are missing (the 72190 mkdir race), if a task row
# does not match its index, or if the submission would exceed the bigbatch QOS (48).
set -euo pipefail
INDICES=$1
LABEL=$2
AFTER=${3:-}
cd "$HOME/msi"
PROV=${PROV:-reproducibility/s3pl_investigation_21/provenance}
EXCLUDE='mscluster[44-45,47-51,54,57,59-70,72,74-76,78,82-83,85,88-89]'

expand() {
    local part
    for part in ${1//,/ }; do
        if [[ $part == *-* ]]; then seq "${part%-*}" "${part#*-}"; else echo "$part"; fi
    done
}

missing=0
count=0
for i in $(expand "$INDICES"); do
    count=$((count + 1))
    read -r idx coll sec seed norm root _ <<< "$(sed -n "$((i + 1))p" "$PROV/tasks.tsv")"
    if [ "$idx" != "$i" ]; then echo "REFUSE: row $((i + 1)) has index '$idx', expected $i"; exit 4; fi
    for sub in logs/s3pl results/baselines/s3pl checkpoints/baselines/s3pl; do
        if [ ! -d "$root/$sub" ]; then echo "MISSING: $i $root/$sub"; missing=1; fi
    done
done
if [ "$missing" -ne 0 ]; then echo "REFUSE: output subfolders missing; nothing submitted"; exit 4; fi

queued=$(squeue -r -u "$USER" -h | wc -l)
if [ $((queued + count)) -gt 48 ]; then echo "REFUSE: $queued queued + $count new > 48"; exit 4; fi

INNER=$(sed -n 's/^command=bash -lc '"'"'\(.*\)'"'"'$/\1/p' "$PROV/manifest.txt")
[ -n "$INNER" ] || { echo "REFUSE: no command in manifest"; exit 4; }
if [ "${DRY_RUN:-0}" = 1 ]; then echo "dry run: checks passed for $count tasks; not submitted"; exit 0; fi
DEP=()
[ -n "$AFTER" ] && DEP=(--dependency="afterok:$AFTER")
JOB=$(sbatch --parsable --job-name=s3pl-inv21 --partition=bigbatch --nodes=1 --ntasks=1 \
    --cpus-per-task=4 --mem=32G --time=02:00:00 --exclude="$EXCLUDE" --array="$INDICES%5" \
    "${DEP[@]}" --output=logs/s3pl-inv21-%A_%a.out --error=logs/s3pl-inv21-%A_%a.err \
    --wrap="bash -lc '$INNER'")
echo "$JOB indices=$INDICES%5 $LABEL${AFTER:+ dependency=afterok:$AFTER} submitted_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ) folder_check=passed($count tasks)" >> "$PROV/slurm_job_ids.txt"
echo "submitted $JOB ($count tasks)"
