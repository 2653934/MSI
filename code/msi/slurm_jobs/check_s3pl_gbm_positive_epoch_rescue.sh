#!/bin/bash
set -euo pipefail

cd "$HOME/msi"
python - "$@" <<'PY'
import csv
import json
import sys
from pathlib import Path

if sys.argv[1:] not in ([], ["--verbose"]):
    raise SystemExit("Usage: check_s3pl_gbm_positive_epoch_rescue.sh [--verbose]")
verbose = "--verbose" in sys.argv[1:]
project = Path.cwd()
details = []
results = {}

for init_seed in (1, 2):
    for epochs in (10, 25, 50):
        suffix = "" if epochs == 10 else f"_{epochs}epochs"
        root = project / "reproducibility/s3pl_massnet" / (
            f"GBM108_positive_p3_rng_init{init_seed}_order1{suffix}"
        )
        training_name = (
            "GBM108_positive_Attention3DConvAutoencoder_"
            f"{epochs}epochs_256_spectral_patch_size_3"
        )
        output = root / "results/baselines/s3pl" / training_name
        config_path = root / "logs/s3pl" / f"{training_name}.json"
        metrics_path = output / "metrics.json"
        peaks_path = output / "picked_peaks_GBM108_positive_256peaks_z_patchsize_3.csv"
        if not all(path.is_file() for path in (config_path, metrics_path, peaks_path)):
            if verbose:
                missing = [str(path) for path in (config_path, metrics_path, peaks_path) if not path.is_file()]
                details.append(f"init {init_seed}, {epochs} epochs: missing {', '.join(missing)}")
            continue
        try:
            config = json.loads(config_path.read_text())
            metrics = json.loads(metrics_path.read_text())
            if config.get("initialization_seed") != init_seed:
                raise ValueError("initialization seed differs")
            if config.get("sample_order_seed") != 1 or config.get("random_seed") != 1:
                raise ValueError("sample-order or base seed differs")
            if config.get("n_epochs") != epochs or config.get("spectral_patch_size") != 3:
                raise ValueError("epoch or patch protocol differs")
            history = config.get("train_history")
            if not isinstance(history, list) or len(history) != epochs:
                raise ValueError("training history length differs")
            with peaks_path.open(newline="") as handle:
                peaks = {row[0] for row in list(csv.reader(handle))[1:]}
            if len(peaks) != 581:
                raise ValueError("unexpected selected-peak count")
            results[init_seed, epochs] = {
                "loss": float(history[-1]),
                "score": float(metrics["mSCF1"]),
                "peaks": peaks,
            }
        except (OSError, KeyError, TypeError, ValueError) as error:
            details.append(
                f"init {init_seed}, {epochs} epochs: {type(error).__name__}: {error}"
            )

print(f'{"INIT":>4} {"EPOCHS":>6} {"LOSS":>9} {"mSCF1":>7} {"DELTA10":>8} {"PEAKS10":>8} STATUS')
for init_seed in (1, 2):
    baseline = results.get((init_seed, 10))
    for epochs in (10, 25, 50):
        item = results.get((init_seed, epochs))
        if item is None:
            print(f"{init_seed:>4} {epochs:>6} {'-':>9} {'-':>7} {'-':>8} {'-':>8} NO RESULT")
            continue
        delta = item["score"] - baseline["score"] if baseline else None
        overlap = len(item["peaks"] & baseline["peaks"]) if baseline else None
        delta_text = "-" if delta is None else f"{delta:+.3f}"
        overlap_text = "-" if overlap is None else str(overlap)
        print(
            f"{init_seed:>4} {epochs:>6} {item['loss']:>9.5f} "
            f"{item['score']:>7.3f} {delta_text:>8} {overlap_text:>8} COMPLETE"
        )

complete_new = sum((seed, epochs) in results for seed in (1, 2) for epochs in (25, 50))
print(f"Complete longer-training runs: {complete_new}/4")
if complete_new == 4:
    low_10 = results[1, 10]["score"]
    low_50 = results[1, 50]["score"]
    high_10 = results[2, 10]["score"]
    high_50 = results[2, 50]["score"]
    if low_50 > low_10 + 0.10:
        print("Interpretation: longer training substantially rescues the low initialization.")
    else:
        print("Interpretation: longer training does not substantially rescue the low initialization.")
    if abs(high_50 - high_10) <= 0.05:
        print("The strong initialization remains broadly stable through 50 epochs.")
    else:
        print("The strong initialization changes materially through 50 epochs.")
    print("Use the full trajectories and peak overlaps before making the final convergence claim.")
if verbose and details:
    print("\nDetails:")
    print("\n".join(details))
PY
