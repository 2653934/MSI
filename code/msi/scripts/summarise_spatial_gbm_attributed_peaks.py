#!/usr/bin/env python3
"""Aggregate matched Spatial-msiPL peak evaluation over eight GBM sections."""

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
METHODS = ("legacy_msipl", "integrated_gradients", "first_layer_l2")
DISPLAY_NAMES = {
    "legacy_msipl": "Legacy msiPL",
    "integrated_gradients": "Spatial-msiPL IG",
    "first_layer_l2": "First-layer L2",
}
COLOURS = {
    "legacy_msipl": "#8D99AE",
    "integrated_gradients": "#457B9D",
    "first_layer_l2": "#E76F51",
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
    differences = np.asarray(right, dtype=float) - np.asarray(left, dtype=float)
    if np.allclose(differences, 0, rtol=0, atol=0):
        return {"statistic": 0.0, "p_value_two_sided": 1.0}
    result = wilcoxon(right, left, alternative="two-sided", method="auto")
    return {
        "statistic": float(result.statistic),
        "p_value_two_sided": float(result.pvalue),
    }


def save_figure(records, output):
    labels = [record["dataset"] for record in records]
    x = np.arange(len(records))
    width = 0.25
    figure, axes = plt.subplots(1, 3, figsize=(20, 5.8))

    for offset, method in enumerate(METHODS):
        axes[0].bar(
            x + (offset - 1) * width,
            [record[f"{method}_mSCF1"] for record in records],
            width,
            label=DISPLAY_NAMES[method],
            color=COLOURS[method],
        )
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("mSCF1 (higher is better)")
    axes[0].set_title("Matched peak quality")
    axes[0].legend(fontsize=9)

    deltas = [record["ig_minus_legacy_mSCF1"] for record in records]
    axes[1].bar(
        x,
        deltas,
        color=["#2A9D8F" if value > 0 else "#E76F51" for value in deltas],
    )
    axes[1].axhline(0, color="black", linewidth=1)
    axes[1].set_ylabel("Spatial IG minus legacy msiPL")
    axes[1].set_title("Section-level mSCF1 change")

    axes[2].bar(
        x,
        [record["gmm_balanced_accuracy"] for record in records],
        color="#6D597A",
    )
    axes[2].axhline(0.5, color="black", linewidth=1, linestyle="--")
    axes[2].set_ylim(0, 1)
    axes[2].set_ylabel("Balanced accuracy")
    axes[2].set_title("Label-free GMM vs expert mask")

    for axis in axes:
        axis.set_xticks(x, labels, rotation=35, ha="right")
        axis.grid(axis="y", alpha=0.2)
    figure.suptitle("Spatial-msiPL peak validation across MassNet GBM")
    figure.tight_layout()
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


def main():
    args = parse_arguments()
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    scores = {method: [] for method in METHODS}

    for dataset in DATASETS:
        result_path = (
            args.project_root
            / "results"
            / "experiments"
            / "spatial_msipl_attributed_peak_evaluation"
            / f"{dataset}_seed1"
            / "uniform_mean"
            / "summary.json"
        )
        result = load_complete(result_path)
        matched = result["matched_peak_evaluation"]
        methods = matched["methods"]
        for method in METHODS:
            scores[method].append(float(methods[method]["mSCF1"]))
        mapping = result["cluster_mapping"]
        records.append(
            {
                "dataset": dataset,
                "pixels": int(result["pixels"]),
                "matched_peaks": int(matched["count"]),
                "legacy_msipl_mSCF1": scores["legacy_msipl"][-1],
                "integrated_gradients_mSCF1": scores["integrated_gradients"][-1],
                "first_layer_l2_mSCF1": scores["first_layer_l2"][-1],
                "ig_minus_legacy_mSCF1": (
                    scores["integrated_gradients"][-1]
                    - scores["legacy_msipl"][-1]
                ),
                "gmm_accuracy": float(mapping["accuracy"]),
                "gmm_balanced_accuracy": float(mapping["balanced_accuracy"]),
                "gmm_adjusted_rand_index": float(mapping["adjusted_rand_index"]),
                "gmm_normalized_mutual_information": float(
                    mapping["normalized_mutual_information"]
                ),
            }
        )

    with (args.output / "per_section.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

    method_summary = {}
    for method in METHODS:
        values = np.asarray(scores[method], dtype=float)
        method_summary[method] = {
            "mean_mSCF1": float(values.mean()),
            "sample_standard_deviation": float(values.std(ddof=1)),
            "median_mSCF1": float(np.median(values)),
            "minimum_mSCF1": float(values.min()),
            "maximum_mSCF1": float(values.max()),
        }

    legacy = np.asarray(scores["legacy_msipl"], dtype=float)
    ig = np.asarray(scores["integrated_gradients"], dtype=float)
    l2 = np.asarray(scores["first_layer_l2"], dtype=float)
    delta = ig - legacy
    summary = {
        "status": "complete",
        "scope": "matched-count peak validation over all eight MassNet GBM sections",
        "sections": len(records),
        "per_section": records,
        "aggregate": {
            "methods": method_summary,
            "integrated_gradients_minus_legacy_msipl": {
                "mean_mSCF1_change": float(delta.mean()),
                "sample_standard_deviation": float(delta.std(ddof=1)),
                "median_mSCF1_change": float(np.median(delta)),
                "minimum_mSCF1_change": float(delta.min()),
                "maximum_mSCF1_change": float(delta.max()),
                "section_wins": int(np.count_nonzero(delta > 0)),
                "section_losses": int(np.count_nonzero(delta < 0)),
                "ties": int(np.count_nonzero(delta == 0)),
                "paired_wilcoxon_two_sided": paired_test(legacy, ig),
            },
            "integrated_gradients_vs_first_layer_l2": {
                "section_wins": int(np.count_nonzero(ig > l2)),
                "section_losses": int(np.count_nonzero(ig < l2)),
                "ties": int(np.count_nonzero(ig == l2)),
                "paired_wilcoxon_two_sided": paired_test(l2, ig),
            },
            "gmm_balanced_accuracy": {
                "mean": float(
                    np.mean([record["gmm_balanced_accuracy"] for record in records])
                ),
                "sample_standard_deviation": float(
                    np.std(
                        [record["gmm_balanced_accuracy"] for record in records],
                        ddof=1,
                    )
                ),
            },
        },
        "interpretation_limits": [
            "Each section uses its own legacy msiPL peak count, so methods are compared at an equal section-specific selection budget.",
            "The GMM and peak ranking are label-free; expert labels are used only for evaluation and display.",
            "There are eight paired sections, so direction consistency and effect sizes should accompany the Wilcoxon p-value.",
        ],
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    save_figure(records, args.output / "attributed_peak_validation.png")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
