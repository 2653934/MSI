#!/bin/bash
set -euo pipefail

cd "$HOME/msi"
python - "$@" <<'PY'
import json
import sys
from pathlib import Path

if sys.argv[1:] not in ([], ["--verbose"]):
    raise SystemExit("Usage: check_s3pl_gbm_p3_seed_probe.sh [--verbose]")
verbose = "--verbose" in sys.argv[1:]
project = Path.cwd()
details = []
finished = 0
print(f'{"DATASET":<18} {"SEED":>4} {"mSCF1":>7} {"PEAKS":>6} STATUS')
for dataset in ("GBM108_positive", "GBM108_negative"):
    name = f"{dataset}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_3"
    for seed in (1, 2, 3):
        root = (
            project if seed == 1 else
            project / "reproducibility/s3pl_massnet" / f"{dataset}_p3_reference_spatial_max_seed{seed}"
        )
        metrics_path = root / "results/baselines/s3pl" / name / "metrics.json"
        config_path = root / "logs/s3pl" / f"{name}.json"
        checkpoint = root / "checkpoints/baselines/s3pl" / f"{name}.pt"
        if not metrics_path.is_file():
            print(f"{dataset:<18} {seed:>4} {'-':>7} {'-':>6} NO RESULT")
            details.append(f"{dataset} seed {seed}: missing metrics: {metrics_path}")
            continue
        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            config = json.loads(config_path.read_text(encoding="utf-8"))
            if checkpoint.stat().st_size <= 0:
                raise ValueError("checkpoint is empty")
            if config["random_seed"] != seed or config["spectral_patch_size"] != 3:
                raise ValueError("seed or patch size does not match the predeclared protocol")
            if config.get("normalization", "reference_spatial_max") != "reference_spatial_max":
                raise ValueError("normalization does not match the released-code baseline")
            if metrics.get("source_training_name", name if seed == 1 else None) != name or metrics["dataset"] != dataset:
                raise ValueError("result metadata does not match the expected section")
            if metrics.get("normalization", "reference_spatial_max" if seed == 1 else None) != "reference_spatial_max":
                raise ValueError("result normalization differs from training protocol")
            peaks = int(metrics["number_picked_peaks"])
            score = float(metrics["mSCF1"])
            if not 0 <= score <= 1 or peaks <= 0:
                raise ValueError("invalid score or peak count")
            print(f"{dataset:<18} {seed:>4} {score:>7.3f} {peaks:>6} COMPLETE")
            if seed != 1:
                finished += 1
        except (OSError, KeyError, ValueError, TypeError) as exc:
            print(f"{dataset:<18} {seed:>4} {'-':>7} {'-':>6} INCOMPLETE")
            details.append(f"{dataset} seed {seed}: {type(exc).__name__}: {exc}")
print(f"New runs verified: {finished}/4")
if verbose and details:
    print("\nDetails:")
    print("\n".join(details))
PY
