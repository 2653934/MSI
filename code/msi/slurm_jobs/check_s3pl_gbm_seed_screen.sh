#!/bin/bash
set -euo pipefail

cd "$HOME/msi"
python - "$@" <<'PY'
import csv
import itertools
import json
import statistics
import sys
from pathlib import Path

if sys.argv[1:] not in ([], ["--verbose"]):
    raise SystemExit("Usage: check_s3pl_gbm_seed_screen.sh [--verbose]")
verbose = "--verbose" in sys.argv[1:]
project = Path.cwd()
datasets = (
    "GBM108_negative",
    "GBM12_1",
    "GBM12_2",
    "GBM22_1",
    "GBM22_2",
    "GBM39_1",
    "GBM39_2",
)
details = []
results = {}

for dataset in datasets:
    for init_seed in (1, 2, 3):
        root = project / "reproducibility/s3pl_massnet" / (
            f"{dataset}_p3_rng_init{init_seed}_order1"
        )
        training_name = (
            f"{dataset}_Attention3DConvAutoencoder_"
            "10epochs_256_spectral_patch_size_3"
        )
        output = root / "results/baselines/s3pl" / training_name
        config_path = root / "logs/s3pl" / f"{training_name}.json"
        metrics_path = output / "metrics.json"
        peaks_path = output / f"picked_peaks_{dataset}_256peaks_z_patchsize_3.csv"
        if not all(path.is_file() for path in (config_path, metrics_path, peaks_path)):
            if verbose:
                missing = [str(path) for path in (config_path, metrics_path, peaks_path) if not path.is_file()]
                details.append(f"{dataset} seed {init_seed}: missing {', '.join(missing)}")
            continue
        try:
            config = json.loads(config_path.read_text())
            metrics = json.loads(metrics_path.read_text())
            if config.get("initialization_seed") != init_seed:
                raise ValueError("initialization seed differs")
            if config.get("sample_order_seed") != 1 or config.get("random_seed") != 1:
                raise ValueError("sample-order or base seed differs")
            if config.get("n_epochs") != 10 or config.get("spectral_patch_size") != 3:
                raise ValueError("training protocol differs")
            history = config.get("train_history")
            if not isinstance(history, list) or len(history) != 10:
                raise ValueError("training history length differs")
            with peaks_path.open(newline="") as handle:
                peaks = {row[0] for row in list(csv.reader(handle))[1:]}
            expected_count = int(metrics["number_picked_peaks"])
            if len(peaks) != expected_count:
                raise ValueError("selected-peak count differs from metrics")
            results[dataset, init_seed] = {
                "score": float(metrics["mSCF1"]),
                "loss": float(history[-1]),
                "peaks": peaks,
            }
        except (OSError, KeyError, TypeError, ValueError) as error:
            details.append(
                f"{dataset} seed {init_seed}: {type(error).__name__}: {error}"
            )

print(
    f'{"DATASET":<18} {"S1":>6} {"S2":>6} {"S3":>6} '
    f'{"MEAN":>6} {"SD":>6} {"RANGE":>6} {"MIN OVL":>8} STATUS'
)
complete_sections = 0
for dataset in datasets:
    items = [results.get((dataset, seed)) for seed in (1, 2, 3)]
    score_text = ["-" if item is None else f"{item['score']:.3f}" for item in items]
    available = [item for item in items if item is not None]
    if len(available) == 3:
        scores = [item["score"] for item in available]
        overlaps = [
            len(left["peaks"] & right["peaks"])
            for left, right in itertools.combinations(available, 2)
        ]
        mean = f"{statistics.mean(scores):.3f}"
        sd = f"{statistics.stdev(scores):.3f}"
        spread = f"{max(scores) - min(scores):.3f}"
        minimum_overlap = str(min(overlaps))
        status = "COMPLETE"
        complete_sections += 1
    else:
        mean = sd = spread = minimum_overlap = "-"
        status = f"{len(available)}/3"
    print(
        f"{dataset:<18} {score_text[0]:>6} {score_text[1]:>6} {score_text[2]:>6} "
        f"{mean:>6} {sd:>6} {spread:>6} {minimum_overlap:>8} {status}"
    )

print(f"Complete sections: {complete_sections}/7; complete runs: {len(results)}/21")
if complete_sections == 7:
    unstable = []
    for dataset in datasets:
        scores = [results[dataset, seed]["score"] for seed in (1, 2, 3)]
        if max(scores) - min(scores) >= 0.10:
            unstable.append(dataset)
    print(f"Sections with at least 0.10 absolute seed spread: {len(unstable)}/7")
    if unstable:
        print("Large-spread sections: " + ", ".join(unstable))
    print("This is a three-seed stability screen, not permission to select each section's best seed.")
if verbose and details:
    print("\nDetails:")
    print("\n".join(details))
PY
