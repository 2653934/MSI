#!/usr/bin/env python3
"""Summarise peak-set and mSCF1 stability across attribution sampling seeds."""

import argparse
import csv
import itertools
import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


TOP_K = (50, 100, 530)


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def read_run(path):
    summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
    if summary.get("status") != "complete":
        raise ValueError(f"incomplete evaluation: {path}")
    csv_path = path / "ig_matched_530_bins.csv"
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    indices = [int(row["bin_index"]) for row in rows]
    if len(indices) != 530 or len(set(indices)) != 530:
        raise ValueError(f"expected 530 unique ranked bins in {csv_path}")
    return {
        "name": path.name,
        "path": str(path),
        "indices": indices,
        "mscf1": float(
            summary["matched_peak_evaluation"]["methods"]
            ["integrated_gradients"]["mSCF1"]
        ),
    }


def jaccard(left, right):
    left, right = set(left), set(right)
    return len(left & right) / len(left | right)


def save_figure(runs, matrices, output):
    names = [run["name"].replace("sampling_seed", "seed ") for run in runs]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    scores = [run["mscf1"] for run in runs]
    axes[0].bar(names, scores, color="#457B9D")
    axes[0].axhline(np.mean(scores), color="#E76F51", linestyle="--", label="mean")
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("mSCF1")
    axes[0].set_title("Peak-quality stability")
    axes[0].tick_params(axis="x", rotation=25)
    axes[0].legend()

    shown = axes[1].imshow(matrices["530"], cmap="viridis", vmin=0, vmax=1)
    axes[1].set_xticks(range(len(names)), names, rotation=25, ha="right")
    axes[1].set_yticks(range(len(names)), names)
    axes[1].set_title("Pairwise Jaccard: selected 530 bins")
    for row in range(len(names)):
        for column in range(len(names)):
            value = matrices["530"][row][column]
            axes[1].text(
                column,
                row,
                f"{value:.2f}",
                ha="center",
                va="center",
                color="white" if value < 0.65 else "black",
            )
    fig.colorbar(shown, ax=axes[1], fraction=0.046)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main():
    args = parse_arguments()
    if len(args.run) < 2:
        raise ValueError("at least two runs are required")
    args.output.mkdir(parents=True, exist_ok=True)
    runs = [read_run(path) for path in args.run]
    if len({run["name"] for run in runs}) != len(runs):
        raise ValueError("run directory names must be unique")

    matrices = {}
    pairwise = {}
    for top_k in TOP_K:
        matrix = np.eye(len(runs), dtype=float)
        records = []
        for left_index, right_index in itertools.combinations(range(len(runs)), 2):
            left = runs[left_index]["indices"][:top_k]
            right = runs[right_index]["indices"][:top_k]
            intersection = len(set(left) & set(right))
            score = jaccard(left, right)
            matrix[left_index, right_index] = score
            matrix[right_index, left_index] = score
            records.append(
                {
                    "left": runs[left_index]["name"],
                    "right": runs[right_index]["name"],
                    "intersection": intersection,
                    "jaccard": score,
                }
            )
        matrices[str(top_k)] = matrix
        pairwise[str(top_k)] = records

    frequency = Counter(
        index for run in runs for index in set(run["indices"])
    )
    with (args.output / "selection_frequency.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=("bin_index", "run_count", "fraction"))
        writer.writeheader()
        for index, count in sorted(frequency.items(), key=lambda item: (-item[1], item[0])):
            writer.writerow(
                {
                    "bin_index": index,
                    "run_count": count,
                    "fraction": count / len(runs),
                }
            )

    scores = np.asarray([run["mscf1"] for run in runs], dtype=float)
    summary = {
        "status": "complete",
        "purpose": "sensitivity to attribution-pixel sampling with model and GMM seed fixed",
        "run_count": len(runs),
        "runs": [
            {"name": run["name"], "path": run["path"], "mSCF1": run["mscf1"]}
            for run in runs
        ],
        "mSCF1": {
            "mean": float(scores.mean()),
            "sample_standard_deviation": float(scores.std(ddof=1)),
            "minimum": float(scores.min()),
            "maximum": float(scores.max()),
            "range": float(scores.max() - scores.min()),
        },
        "selection_stability": {
            "top_k_pairwise": pairwise,
            "bins_in_every_530_bin_set": sum(
                count == len(runs) for count in frequency.values()
            ),
            "bins_in_at_least_75_percent_of_530_bin_sets": sum(
                count / len(runs) >= 0.75 for count in frequency.values()
            ),
        },
        "interpretation_note": (
            "Stable mSCF1 shows conclusion-level robustness; peak-set overlap shows "
            "whether the exact selected ions are reproducible."
        ),
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    save_figure(runs, matrices, args.output / "attribution_sampling_stability.png")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
