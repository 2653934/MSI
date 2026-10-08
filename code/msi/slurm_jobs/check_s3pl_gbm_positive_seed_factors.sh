#!/bin/bash
set -euo pipefail

cd "$HOME/msi"
python - <<'PY'
import csv
import json
from pathlib import Path

project = Path.cwd()
training_name = "GBM108_positive_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_3"
results = {}
print(f'{"WEIGHTS":>7} {"ORDER":>7} {"mSCF1":>7} {"PEAKS":>6} STATUS')
for initial_seed in (1, 2):
    for order_seed in (1, 2):
        root = project / "reproducibility/s3pl_massnet" / (
            f"GBM108_positive_p3_rng_init{initial_seed}_order{order_seed}"
        )
        output = root / "results/baselines/s3pl" / training_name
        try:
            config = json.loads((root / "logs/s3pl" / f"{training_name}.json").read_text())
            metrics = json.loads((output / "metrics.json").read_text())
            if (config.get("initialization_seed"), config.get("sample_order_seed")) != (
                initial_seed, order_seed
            ):
                raise ValueError("controlled seeds do not match this run")
            if config["random_seed"] != 1 or config["spectral_patch_size"] != 3:
                raise ValueError("base protocol differs")
            if config.get("normalization") != "reference_spatial_max":
                raise ValueError("normalization differs")
            if metrics.get("dataset") != "GBM108_positive":
                raise ValueError("dataset differs")
            if metrics.get("source_training_name") != training_name:
                raise ValueError("training source differs")
            peak_file = output / "picked_peaks_GBM108_positive_256peaks_z_patchsize_3.csv"
            with peak_file.open(newline="") as handle:
                peaks = [row[0] for row in list(csv.reader(handle))[1:]]
            if len(peaks) != metrics["number_picked_peaks"] or len(peaks) != 581:
                raise ValueError("unexpected peak count")
            if len(set(peaks)) != len(peaks):
                raise ValueError("duplicate selected peaks")
            score = float(metrics["mSCF1"])
            if not 0 <= score <= 1:
                raise ValueError("invalid mSCF1")
            results[initial_seed, order_seed] = (score, set(peaks))
            print(f"{initial_seed:>7} {order_seed:>7} {score:>7.3f} {len(peaks):>6} COMPLETE")
        except (OSError, KeyError, ValueError, TypeError) as error:
            print(f"{initial_seed:>7} {order_seed:>7} {'-':>7} {'-':>6} INCOMPLETE: {error}")

print(f"Complete controlled runs: {len(results)}/4")
if len(results) == 4:
    baseline = results[1, 1][0]
    print(f"Change order only (1,2 minus 1,1): {results[1, 2][0] - baseline:+.3f}")
    print(f"Change weights only (2,1 minus 1,1): {results[2, 1][0] - baseline:+.3f}")
    print(f"Change both (2,2 minus 1,1): {results[2, 2][0] - baseline:+.3f}")
    for left, right in (((1, 1), (1, 2)), ((1, 1), (2, 1)), ((1, 1), (2, 2))):
        overlap = len(results[left][1] & results[right][1])
        print(f"Peak overlap {left} vs {right}: {overlap}/581")
    print("Diagnostic contrasts only; these runs do not replace the released-code baseline.")
PY
