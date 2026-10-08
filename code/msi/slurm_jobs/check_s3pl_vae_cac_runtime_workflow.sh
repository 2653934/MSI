#!/bin/bash
set -euo pipefail

if [[ "$#" -ne 1 || ! "$1" =~ ^[0-9]+$ ]]; then
    echo "Usage: bash $0 JOB_ID" >&2
    exit 2
fi
cd "$HOME/msi"
python - "$1" <<'PY'
import csv
import json
import sys
from pathlib import Path

job_id = sys.argv[1]
root = Path.cwd() / "results/validation/s3pl_vae_cac_runtime" / job_id
stages = ("s3pl_full", "vae_train", "vae_attribution", "vae_peak_evaluation")
exits = {}
attempts = {}
stage_log = root / "stages.tsv"
if stage_log.is_file():
    with stage_log.open(newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            exits[row["stage"]] = int(row["exit_code"])
            attempts[row["stage"]] = attempts.get(row["stage"], 0) + 1
print(f"Runtime workflow job {job_id} (160TopL; native protocols)")
if attempts.get("vae_peak_evaluation", 0) > 1:
    print("Allocation note: VAE peak evaluation was repaired in a later allocation; its wall time includes fresh process/filesystem startup.")
print(f'{"STAGE":<21} {"WALL s":>9} {"CPU s":>9} {"RSS GiB":>8} {"GPU max MiB":>11} STATUS')
complete = 0
walls = {}
for stage in stages:
    resources = root / f"{stage}.resources.txt"
    if not resources.is_file():
        print(f"{stage:<21} {'-':>9} {'-':>9} {'-':>8} {'-':>11} NO RESULT")
        continue
    values = {}
    for line in resources.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = float(value)
    gpu_max = None
    samples = root / f"{stage}.gpu_samples.csv"
    if samples.is_file():
        with samples.open(newline="") as handle:
            for row in csv.reader(handle):
                if len(row) >= 3:
                    try:
                        used = float(row[2].strip())
                    except ValueError:
                        continue
                    gpu_max = used if gpu_max is None else max(gpu_max, used)
    elapsed = values.get("elapsed_seconds")
    if elapsed is not None:
        walls[stage] = elapsed
    cpu = values.get("user_cpu_seconds", 0) + values.get("system_cpu_seconds", 0)
    rss = values.get("max_rss_kib", 0) / 1024**2
    status = "COMPLETE" if exits.get(stage) == 0 else "FAILED" if stage in exits else "PARTIAL"
    if status == "COMPLETE":
        complete += 1
    print(f"{stage:<21} {elapsed if elapsed is not None else '-':>9} {cpu:>9.1f} {rss:>8.2f} {gpu_max if gpu_max is not None else '-':>11} {status}")
print(f"Stages with resource records: {complete}/4")
if complete == 4:
    vae_total = sum(walls[stage] for stage in stages[1:])
    print(f"Native workflow wall time: S3PL {walls['s3pl_full']:.1f} s; VAE {vae_total:.1f} s")
    s3pl_metrics = (
        root / "s3pl/results/baselines/s3pl/"
        "160TopL_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9/"
        "runtime_metrics.json"
    )
    if s3pl_metrics.is_file():
        metrics = json.loads(s3pl_metrics.read_text())
        print(
            "S3PL internal split: training "
            f"{metrics['training_seconds']:.1f} s; selection/scoring "
            f"{metrics['evaluation_seconds']:.1f} s"
        )
    print("Native 10-versus-100-epoch totals are not an equal-work speed comparison.")
print("GPU max is sampled whole-device memory, not model-only allocation; see saved stage files for detail.")
PY
