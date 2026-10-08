#!/bin/bash
set -euo pipefail

cd "$HOME/msi"
python - "$@" <<'PY'
import csv
import json
import math
import statistics
import sys
from pathlib import Path

if sys.argv[1:] not in ([], ["--verbose"]):
    raise SystemExit("Usage: check_s3pl_gbm_positive_initialization_sweep.sh [--verbose]")
verbose = "--verbose" in sys.argv[1:]
project = Path.cwd()
training_name = "GBM108_positive_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_3"
results = {}
details = []

print(f'{"INIT":>4} {"ORDER":>5} {"LOSS":>9} {"mSCF1":>7} {"VS S1":>7} {"VS S2":>7} STATUS')
for init_seed in range(1, 11):
    order_seed = 1
    root = project / "reproducibility/s3pl_massnet" / (
        f"GBM108_positive_p3_rng_init{init_seed}_order{order_seed}"
    )
    output = root / "results/baselines/s3pl" / training_name
    config_path = root / "logs/s3pl" / f"{training_name}.json"
    metrics_path = output / "metrics.json"
    peak_path = output / "picked_peaks_GBM108_positive_256peaks_z_patchsize_3.csv"
    if not all(path.is_file() for path in (config_path, metrics_path, peak_path)):
        print(f"{init_seed:>4} {order_seed:>5} {'-':>9} {'-':>7} {'-':>7} {'-':>7} NO RESULT")
        if verbose:
            missing = [str(path) for path in (config_path, metrics_path, peak_path) if not path.is_file()]
            details.append(f"seed {init_seed}: missing {', '.join(missing)}")
        continue
    try:
        config = json.loads(config_path.read_text())
        metrics = json.loads(metrics_path.read_text())
        if config.get("initialization_seed") != init_seed or config.get("sample_order_seed") != 1:
            raise ValueError("controlled seeds differ")
        if config.get("random_seed") != 1 or config.get("spectral_patch_size") != 3:
            raise ValueError("base protocol differs")
        history = config.get("train_history")
        if not isinstance(history, list) or len(history) != 10:
            raise ValueError("training history is not ten epochs")
        loss = float(history[-1])
        score = float(metrics["mSCF1"])
        with peak_path.open(newline="") as handle:
            peaks = {row[0] for row in list(csv.reader(handle))[1:]}
        if len(peaks) != 581 or not 0 <= score <= 1 or not math.isfinite(loss):
            raise ValueError("invalid score, loss, or peak set")
        results[init_seed] = {"loss": loss, "score": score, "peaks": peaks}
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(f"{init_seed:>4} {order_seed:>5} {'-':>9} {'-':>7} {'-':>7} {'-':>7} INVALID")
        details.append(f"seed {init_seed}: {type(error).__name__}: {error}")
        continue

    overlap1 = len(peaks & results[1]["peaks"]) if 1 in results else None
    overlap2 = len(peaks & results[2]["peaks"]) if 2 in results else None
    left = "-" if overlap1 is None else str(overlap1)
    right = "-" if overlap2 is None else str(overlap2)
    print(f"{init_seed:>4} {order_seed:>5} {loss:>9.5f} {score:>7.3f} {left:>7} {right:>7} COMPLETE")

print(f"Complete initialization runs: {len(results)}/10")
if len(results) >= 2:
    scores = [item["score"] for item in results.values()]
    print(
        f"mSCF1 mean {statistics.mean(scores):.3f}; sample SD "
        f"{statistics.stdev(scores):.3f}; median {statistics.median(scores):.3f}; "
        f"range {min(scores):.3f}-{max(scores):.3f}"
    )
if len(results) == 10:
    losses = [results[seed]["loss"] for seed in sorted(results)]
    scores = [results[seed]["score"] for seed in sorted(results)]
    loss_mean = statistics.mean(losses)
    score_mean = statistics.mean(scores)
    numerator = sum((loss - loss_mean) * (score - score_mean) for loss, score in zip(losses, scores))
    denominator = math.sqrt(
        sum((loss - loss_mean) ** 2 for loss in losses)
        * sum((score - score_mean) ** 2 for score in scores)
    )
    correlation = numerator / denominator if denominator else float("nan")
    print(f"Pearson correlation of final training loss with mSCF1: {correlation:+.3f}")
    print("Next decision: compare longer training for a low- and high-scoring initialization.")
if verbose and details:
    print("\nDetails:")
    print("\n".join(details))
print("Controlled diagnostic evidence only; do not select the best seed as the reported baseline.")
PY
