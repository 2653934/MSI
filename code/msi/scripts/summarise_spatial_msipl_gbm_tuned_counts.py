#!/usr/bin/env python3
"""Summarise GBM rankings re-evaluated at tuned legacy msiPL peak counts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import wilcoxon


DATASETS = (
    "GBM108_positive",
    "GBM108_negative",
    "GBM12_1",
    "GBM12_2",
    "GBM22_1",
    "GBM22_2",
    "GBM39_1",
    "GBM39_2",
)
METHODS = (
    ("legacy_msipl", "Tuned legacy msiPL", "#7F7F7F"),
    ("central_ig", "Centre-only IG", "#4C78A8"),
    ("uniform_ig", "Uniform-context IG", "#F28E2B"),
    ("uniform_l2", "Uniform first-layer L2", "#E15759"),
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def load_complete(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"missing result: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("status") != "complete":
        raise ValueError(f"incomplete result: {path}")
    return value


def paired_summary(left: np.ndarray, right: np.ndarray) -> dict:
    """Return right-minus-left paired effects and an exact small-sample test."""
    delta = right - left
    if np.allclose(delta, 0.0, rtol=0.0, atol=0.0):
        statistic, p_value = 0.0, 1.0
    else:
        test = wilcoxon(right, left, alternative="two-sided", method="auto")
        statistic, p_value = float(test.statistic), float(test.pvalue)
    return {
        "mean_right_minus_left": float(delta.mean()),
        "sample_standard_deviation": float(delta.std(ddof=1)),
        "median_right_minus_left": float(np.median(delta)),
        "right_wins": int(np.count_nonzero(delta > 0)),
        "left_wins": int(np.count_nonzero(delta < 0)),
        "ties": int(np.count_nonzero(delta == 0)),
        "paired_wilcoxon_two_sided": {
            "statistic": statistic,
            "p_value": p_value,
        },
    }


def method_summary(values: np.ndarray) -> dict:
    return {
        "mean_mSCF1": float(values.mean()),
        "sample_standard_deviation": float(values.std(ddof=1)),
        "median_mSCF1": float(np.median(values)),
        "minimum_mSCF1": float(values.min()),
        "maximum_mSCF1": float(values.max()),
    }


def write_csv(path: Path, records: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def selected_bins(path: Path) -> set[int]:
    if not path.is_file():
        raise FileNotFoundError(f"missing selected-peak list: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return {int(row["bin_index"]) for row in csv.DictReader(handle)}


def save_figure(records: list[dict], output: Path) -> None:
    labels = [record["dataset"] for record in records]
    x = np.arange(len(labels))
    width = 0.19
    figure, axes = plt.subplots(2, 1, figsize=(13, 9), height_ratios=(1.3, 1))

    for index, (key, label, colour) in enumerate(METHODS):
        offset = (index - (len(METHODS) - 1) / 2) * width
        axes[0].bar(
            x + offset,
            [record[f"{key}_mSCF1"] for record in records],
            width,
            label=label,
            color=colour,
            edgecolor="black",
            linewidth=0.45,
        )
    axes[0].set_ylim(0, 0.75)
    axes[0].set_ylabel("mSCF1 (higher is better)")
    axes[0].set_title("GBM peak selection at tuned msiPL section-specific counts")
    axes[0].legend(ncol=2, fontsize=9)

    context = np.asarray(
        [record["uniform_minus_central_ig"] for record in records], dtype=float
    )
    tuned = np.asarray(
        [record["uniform_ig_minus_tuned_legacy"] for record in records], dtype=float
    )
    axes[1].axhline(0, color="black", linewidth=1)
    axes[1].bar(
        x - 0.18,
        context,
        0.36,
        label="Uniform IG - centre-only IG",
        color="#4C78A8",
    )
    axes[1].bar(
        x + 0.18,
        tuned,
        0.36,
        label="Uniform IG - tuned legacy msiPL",
        color="#F28E2B",
    )
    axes[1].set_ylabel("Paired mSCF1 difference")
    axes[1].set_title("Section-level effects after peak-count correction")
    axes[1].legend(fontsize=9)

    for axis in axes:
        axis.set_xticks(x, labels, rotation=28, ha="right")
        axis.grid(axis="y", alpha=0.22)
    figure.tight_layout()
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


def save_overlap_figure(records: list[dict], output: Path) -> None:
    labels = [record["dataset"] for record in records]
    values = [record["context_ig_jaccard"] for record in records]
    figure, axis = plt.subplots(figsize=(11, 4.8))
    bars = axis.bar(labels, values, color="#59A14F", edgecolor="black", linewidth=0.5)
    axis.set_ylim(0, 1)
    axis.set_ylabel("Jaccard overlap (0 = none, 1 = identical)")
    axis.set_title("Do centre-only and uniform-context IG select the same peaks?")
    axis.grid(axis="y", alpha=0.22)
    axis.tick_params(axis="x", rotation=28)
    for bar, record in zip(bars, records):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f'{record["context_ig_intersection"]}/{record["matched_peaks"]}',
            ha="center",
            va="bottom",
            fontsize=8,
        )
    figure.tight_layout()
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    args = parse_arguments()
    args.output.mkdir(parents=True, exist_ok=True)
    evaluation_root = (
        args.project_root
        / "results"
        / "experiments"
        / "spatial_msipl_gbm_tuned_count_evaluation"
    )
    records: list[dict] = []

    for dataset in DATASETS:
        central = load_complete(
            evaluation_root / f"{dataset}_seed1" / "central_only" / "summary.json"
        )
        uniform = load_complete(
            evaluation_root / f"{dataset}_seed1" / "uniform_mean" / "summary.json"
        )
        central_eval = central["matched_peak_evaluation"]
        uniform_eval = uniform["matched_peak_evaluation"]
        if central_eval["count"] != uniform_eval["count"]:
            raise ValueError(f"count mismatch for {dataset}")
        central_methods = central_eval["methods"]
        uniform_methods = uniform_eval["methods"]
        legacy = float(uniform_methods["legacy_msipl"]["mSCF1"])
        central_ig = float(central_methods["integrated_gradients"]["mSCF1"])
        uniform_ig = float(uniform_methods["integrated_gradients"]["mSCF1"])
        central_l2 = float(central_methods["first_layer_l2"]["mSCF1"])
        uniform_l2 = float(uniform_methods["first_layer_l2"]["mSCF1"])
        count = int(uniform_eval["count"])
        central_bins = selected_bins(
            evaluation_root
            / f"{dataset}_seed1"
            / "central_only"
            / f"ig_matched_{count}_bins.csv"
        )
        uniform_bins = selected_bins(
            evaluation_root
            / f"{dataset}_seed1"
            / "uniform_mean"
            / f"ig_matched_{count}_bins.csv"
        )
        intersection = len(central_bins & uniform_bins)
        union = len(central_bins | uniform_bins)
        records.append(
            {
                "dataset": dataset,
                "matched_peaks": count,
                "legacy_msipl_mSCF1": legacy,
                "central_ig_mSCF1": central_ig,
                "uniform_ig_mSCF1": uniform_ig,
                "central_l2_mSCF1": central_l2,
                "uniform_l2_mSCF1": uniform_l2,
                "uniform_minus_central_ig": uniform_ig - central_ig,
                "central_ig_minus_tuned_legacy": central_ig - legacy,
                "uniform_ig_minus_tuned_legacy": uniform_ig - legacy,
                "context_ig_intersection": intersection,
                "context_ig_jaccard": intersection / union,
                "context_ig_fraction_shared": intersection / count,
            }
        )

    write_csv(args.output / "per_section.csv", records)
    arrays = {
        "legacy_msipl": np.asarray(
            [record["legacy_msipl_mSCF1"] for record in records], dtype=float
        ),
        "central_ig": np.asarray(
            [record["central_ig_mSCF1"] for record in records], dtype=float
        ),
        "uniform_ig": np.asarray(
            [record["uniform_ig_mSCF1"] for record in records], dtype=float
        ),
        "central_l2": np.asarray(
            [record["central_l2_mSCF1"] for record in records], dtype=float
        ),
        "uniform_l2": np.asarray(
            [record["uniform_l2_mSCF1"] for record in records], dtype=float
        ),
    }
    summary = {
        "status": "complete",
        "scope": "GBM frozen rankings at tuned paper-aligned msiPL peak counts",
        "sections": len(records),
        "training_repeated": False,
        "attribution_repeated": False,
        "per_section": records,
        "aggregate": {
            "methods": {
                key: method_summary(values) for key, values in arrays.items()
            },
            "uniform_ig_vs_central_ig": paired_summary(
                arrays["central_ig"], arrays["uniform_ig"]
            ),
            "central_ig_vs_tuned_legacy_msipl": paired_summary(
                arrays["legacy_msipl"], arrays["central_ig"]
            ),
            "uniform_ig_vs_tuned_legacy_msipl": paired_summary(
                arrays["legacy_msipl"], arrays["uniform_ig"]
            ),
            "uniform_ig_vs_uniform_l2": paired_summary(
                arrays["uniform_l2"], arrays["uniform_ig"]
            ),
            "centre_vs_uniform_ig_peak_overlap": {
                "mean_jaccard": float(
                    np.mean([record["context_ig_jaccard"] for record in records])
                ),
                "minimum_jaccard": float(
                    np.min([record["context_ig_jaccard"] for record in records])
                ),
                "maximum_jaccard": float(
                    np.max([record["context_ig_jaccard"] for record in records])
                ),
                "meaning": "Jaccard is intersection divided by union for the two equal-budget selected-bin sets.",
            },
        },
        "interpretation": [
            "Every method uses the tuned legacy msiPL peak count for the same section.",
            "Only saved rankings were re-evaluated; no model was retrained and no attribution was recomputed.",
            "Sections are paired evaluation units and are not treated as independent patients.",
        ],
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    save_figure(records, args.output / "gbm_tuned_count_comparison.png")
    save_overlap_figure(records, args.output / "gbm_context_peak_overlap.png")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
