#!/bin/bash
# Login-node submitter for the gate (d) pixel-count IG runs: file checks and
# sbatch only. Protocol 18 Section 6 ("Pixel-count run specification").
#
#   bash slurm_jobs/submit_gate_d_pixel_counts.sh pilot|gbm \
#        [--partition P] [--mem M] [--time-12 T] [--time-48 T] [--time-192 T] \
#        [--counts 12|48,192|12,48,192] [--arms central_only,uniform_mean]
#
# --counts/--arms stage the runs (supervisor review, 9 October): stage 1 is
# --counts 12; stage 2 is --counts 48,192 for each arm whose n=12 reproduced.
# A count above 12 is refused unless <arm>/n12_reproduction/summary.json
# (run_gate_d_evaluation.sh SECTION ARM n12-only) has status "passed".
#
#   pilot : 40TopL, both arms, n = 12, 48, 192 (production CAC IG took ~10 s per arm)
#   gbm   : GBM108_positive, both arms, n = 12, 48, 192
#
# Defaults (protocol 18 Section 6, decided 9 October): partition batch, exclusive
# (set in the job script), 8G for 40TopL and 24G for GBM108_positive. Move to
# bigbatch only if sacct MaxRSS or an out-of-memory failure shows it is needed.
# IG time grows with the pixel count, so each count has its own limit. Run the
# pilot first and read sacct before submitting gbm.
set -euo pipefail
PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"

selection="${1:?Usage: $0 pilot|gbm [--partition P] [--mem M] [--time-12 T] [--time-48 T] [--time-192 T] [--counts LIST] [--arms LIST]}"
shift
case "$selection" in
    pilot) dataset=40TopL; mem=8G; declare -A limit=([12]=00:30:00 [48]=00:30:00 [192]=01:00:00) ;;
    gbm) dataset=GBM108_positive; mem=24G; declare -A limit=([12]=04:00:00 [48]=04:00:00 [192]=08:00:00) ;;
    *) echo "Selection must be pilot or gbm" >&2; exit 2 ;;
esac
partition=batch
counts="12 48 192"
arms="central_only uniform_mean"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --partition) partition="${2:?}"; shift 2 ;;
        --mem) mem="${2:?}"; shift 2 ;;
        --time-12) limit[12]="${2:?}"; shift 2 ;;
        --time-48) limit[48]="${2:?}"; shift 2 ;;
        --time-192) limit[192]="${2:?}"; shift 2 ;;
        --counts) counts="${2//,/ }"; shift 2 ;;
        --arms) arms="${2//,/ }"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

for total in $counts; do
    case "$total" in 12|48|192) ;; *) echo "Unknown count: $total" >&2; exit 2 ;; esac
done
for arm in $arms; do
    case "$arm" in central_only|uniform_mean) ;; *) echo "Unknown arm: $arm" >&2; exit 2 ;; esac
done

quarantine="slurm_jobs/gpu_cuda_quarantine.txt"
[ -f "$quarantine" ] || { echo "Missing CUDA quarantine file: $quarantine" >&2; exit 1; }
excludes=$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' "$quarantine" | sort -u | paste -sd, -)
[ -n "$excludes" ] || { echo "CUDA quarantine file lists no nodes" >&2; exit 1; }

# Refuse up front if any output already exists, so a run is never half-submitted.
outputs="results/diagnostics/gate_d_pixel_counts/${dataset}_seed1"
for arm in $arms; do
    for total in $counts; do
        if [ -e "$outputs/$arm/n$total" ]; then
            echo "Output already exists: $outputs/$arm/n$total (move it aside first)" >&2
            exit 3
        fi
        if [ "$total" != 12 ] && ! grep -q '"status": "passed"' \
                "$outputs/$arm/n12_reproduction/summary.json" 2>/dev/null; then
            echo "n=$total refused for $arm: no passed n=12 reproduction record" >&2
            exit 4
        fi
    done
done

# Create the shared parent folders here: concurrent tasks creating them caused
# the 66114 race ("mkdir: Already exists").
mkdir -p "$outputs/central_only" "$outputs/uniform_mean" logs

printf '%-16s %-13s %-5s %-10s %s\n' DATASET ARM N TIME JOB
for arm in $arms; do
    for total in $counts; do
        job=$(sbatch --parsable \
            --partition="$partition" --mem="$mem" --time="${limit[$total]}" \
            --exclude="$excludes" \
            --export="ALL,GATE_D_MEM=$mem,GATE_D_TIME=${limit[$total]}" \
            --job-name="gate-d-ig-${dataset}-${arm}-n${total}" \
            slurm_jobs/run_gate_d_pixel_count_ig.sh "$dataset" "$arm" "$total")
        printf '%-16s %-13s %-5s %-10s %s\n' "$dataset" "$arm" "$total" "${limit[$total]}" "${job%%;*}"
    done
done
echo "Partition $partition, memory $mem; CUDA quarantine: $excludes"
echo "Resources: sacct -j <id> --format=JobID,State,Elapsed,MaxRSS,ReqMem,NodeList,ExitCode"
echo "A CUDA warm-up failure submits a replacement job; check squeue -u \"\$USER\" for its ID."
