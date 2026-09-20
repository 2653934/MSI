#!/usr/bin/env python3
"""Compare centre-only and uniform-neighbourhood IG over eight GBM sections."""

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
    "legacy_msipl",
    "central_only_ig",
    "uniform_mean_ig",
    "uniform_mean_l2",
)
DISPLAY_NAMES = {
    "legacy_msipl": "Legacy msiPL",
    "central_only_ig": "Centre-only IG",
    "uniform_mean_ig": "Spatial IG",
    "uniform_mean_l2": "Spatial first-layer L2",
}
COLOURS = {
    "legacy_msipl": "#8D99AE",
    "central_only_ig": "#6D597A",
    "uniform_mean_ig": "#457B9D",
    "uniform_mean_l2": "#E76F51",
}


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def load_complete(path):
    if not path.is_file():
        raise FileNotFoundError(f"missing required result: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("status") != "complete":
        raise ValueError(f"result is not complete: {path}")
    return value


def paired_test(left, right):
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    if np.array_equal(left, right):
        return {"statistic": 0.0, "p_value_two_sided": 1.0}
    result = wilcoxon(right, left, alternative="two-sided", method="auto")
    return {
        "statistic": float(result.statistic),
        "p_value_two_sided": float(result.pvalue),
    }


def comparison(left, right):
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    delta = right - left
    return {
        "mean_mSCF1_change": float(delta.mean()),
        "sample_standard_deviation": float(delta.std(ddof=1)),
        "median_mSCF1_change": float(np.median(delta)),
        "minimum_mSCF1_change": float(delta.min()),
        "maximum_mSCF1_change": float(delta.max()),
        "section_wins": int(np.count_nonzero(delta > 0)),
        "section_losses": int(np.count_nonzero(delta < 0)),
        "ties": int(np.count_nonzero(delta == 0)),
        "paired_wilcoxon_two_sided": paired_test(left, right),
    }


def method_summary(values):
    values = np.asarray(values, dtype=float)
    return {
        "mean_mSCF1": float(values.mean()),
        "sample_standard_deviation": float(values.std(ddof=1)),
        "median_mSCF1": float(np.median(values)),
        "minimum_mSCF1": float(values.min()),
        "maximum_mSCF1": float(values.max()),
    }


def save_figure(records, output):
    labels = [record["dataset"] for record in records]
    x = np.arange(len(records))
    width = 0.2
    figure, axes = plt.subplots(1, 2, figsize=(16, 5.8))
    for offset, method in enumerate(METHODS):
        axes[0].bar(
            x + (offset - 1.5) * width,
            [record[f"{method}_mSCF1"] for record in records],
            width,
            label=DISPLAY_NAMES[method],
            color=COLOURS[method],
        )
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("mSCF1 (higher is better)")
    axes[0].set_title("Matched peak quality")
    axes[0].legend(fontsize=9)

    deltas = [record["spatial_minus_centre_ig_mSCF1"] for record in records]
    axes[1].bar(
        x,
        deltas,
        color=["#2A9D8F" if value > 0 else "#E76F51" for value in deltas],
    )
    axes[1].axhline(0, color="black", linewidth=1)
    axes[1].set_ylabel("Spatial IG minus centre-only IG")
    axes[1].set_title("Added value of neighbourhood context")

    for axis in axes:
        axis.set_xticks(x, labels, rotation=35, ha="right")
        axis.grid(axis="y", alpha=0.2)
    figure.suptitle("Matched centre-only control for Spatial-msiPL attribution")
    figure.tight_layout()
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


def main():
    args = parse_arguments()
    args.output.mkdir(parents=True, exist_ok=True)
    root = (
        args.project_root
        / "results"
        / "experiments"
        / "spatial_msipl_attributed_peak_evaluation"
    )
    records = []
    scores = {method: [] for method in METHODS}
    for dataset in DATASETS:
        spatial = load_complete(
            root / f"{dataset}_seed1" / "uniform_mean" / "summary.json"
        )
        centre = load_complete(
            root / f"{dataset}_seed1" / "central_only" / "summary.json"
        )
        spatial_matched = spatial["matched_peak_evaluation"]
        centre_matched = centre["matched_peak_evaluation"]
        if int(spatial_matched["count"]) != int(centre_matched["count"]):
            raise ValueError(f"matched peak budgets differ for {dataset}")
        values = {
            "legacy_msipl": float(
                spatial_matched["methods"]["legacy_msipl"]["mSCF1"]
            ),
            "central_only_ig": float(
                centre_matched["methods"]["integrated_gradients"]["mSCF1"]
            ),
            "uniform_mean_ig": float(
                spatial_matched["methods"]["integrated_gradients"]["mSCF1"]
            ),
            "uniform_mean_l2": float(
                spatial_matched["methods"]["first_layer_l2"]["mSCF1"]
            ),
        }
        for method, value in values.items():
            scores[method].append(value)
        records.append(
            {
                "dataset": dataset,
                "matched_peaks": int(spatial_matched["count"]),
                **{f"{method}_mSCF1": value for method, value in values.items()},
                "spatial_minus_centre_ig_mSCF1": (
                    values["uniform_mean_ig"] - values["central_only_ig"]
                ),
                "centre_minus_legacy_mSCF1": (
                    values["central_only_ig"] - values["legacy_msipl"]
                ),
                "spatial_gmm_balanced_accuracy": float(
                    spatial["cluster_mapping"]["balanced_accuracy"]
                ),
                "centre_gmm_balanced_accuracy": float(
                    centre["cluster_mapping"]["balanced_accuracy"]
                ),
            }
        )

    with (args.output / "per_section.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

    summary = {
        "status": "complete",
        "scope": "matched centre-only versus uniform-neighbourhood IG control over eight MassNet GBM sections",
        "sections": len(records),
        "per_section": records,
        "aggregate": {
            "methods": {
                method: method_summary(values) for method, values in scores.items()
            },
            "uniform_mean_ig_vs_central_only_ig": comparison(
                scores["central_only_ig"], scores["uniform_mean_ig"]
            ),
            "central_only_ig_vs_legacy_msipl": comparison(
                scores["legacy_msipl"], scores["central_only_ig"]
            ),
            "uniform_mean_ig_vs_legacy_msipl": comparison(
                scores["legacy_msipl"], scores["uniform_mean_ig"]
            ),
        },
        "interpretation_limits": [
            "Centre-only and uniform-mean models use the same section, seed, epochs, hidden and latent dimensions, attribution settings, GMM settings and matched peak budget.",
            "The encoder input is the intended architectural difference: centre spectrum only versus centre plus uniform-mean neighbourhood context.",
            "Expert labels are used only to map/evaluate label-free GMM components and score selected bins.",
            "Eight sections are paired experimental units and are not asserted to be eight independent patients.",
        ],
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    save_figure(records, args.output / "context_attribution_control.png")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
