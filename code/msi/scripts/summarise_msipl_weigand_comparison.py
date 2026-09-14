#!/usr/bin/env python3
"""Create a human-readable comparison of reproduced msiPL and Weigand (2026).

The JSON files remain the audit trail. This script turns them into one CSV,
one compact JSON summary, and one four-panel figure for interpretation.
Missing sections are shown explicitly rather than silently omitted.
"""

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


THRESHOLDS = ("0.3", "0.4", "0.5", "0.6")
SECTIONS = {
    "GBM": (
        "GBM12_1",
        "GBM12_2",
        "GBM22_1",
        "GBM22_2",
        "GBM39_1",
        "GBM39_2",
        "GBM108_positive",
        "GBM108_negative",
    ),
    "CAC": (
        "40TopL",
        "160TopL",
        "200TopL",
        "240TopL",
        "280TopL",
        "360TopL",
        "400TopL",
        "520TopL",
    ),
}

# Exact dataset-level msiPL values from Weigand et al. (2026), Table 3.
# Percentages in the paper are represented here as fractions.
PAPER = {
    "GBM": {
        "threshold_f1": {"0.3": 0.456, "0.4": 0.444, "0.5": 0.394, "0.6": 0.319},
        "mSCF1": 0.403,
        "mSCF1_95_ci": [0.330, 0.475],
    },
    "CAC": {
        "threshold_f1": {"0.3": 0.563, "0.4": 0.501, "0.5": 0.399, "0.6": 0.261},
        "mSCF1": 0.431,
        "mSCF1_95_ci": [0.391, 0.479],
    },
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gbm-root",
        type=Path,
        default=Path("results/baselines/msipl/massnet"),
        help="Directory containing one GBM subdirectory per tissue section.",
    )
    parser.add_argument(
        "--cac-root",
        type=Path,
        default=Path("results/baselines/msipl/cac"),
        help="Directory containing one CAC subdirectory per tissue section.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/comparisons/msipl_weigand_2026"),
    )
    return parser.parse_args()


def read_dataset(dataset, root):
    records = []
    missing = []
    for section in SECTIONS[dataset]:
        path = root / section / "peak_metrics.json"
        if not path.is_file():
            missing.append(section)
            continue

        with path.open("r", encoding="utf-8") as stream:
            metrics = json.load(stream)
        if metrics.get("status") != "complete":
            missing.append(section)
            continue

        mixed = metrics["mixed_f1"]
        records.append(
            {
                "dataset": dataset,
                "section": section,
                "mSCF1": float(metrics["mSCF1"]),
                **{"F1_" + threshold: float(mixed[threshold]) for threshold in THRESHOLDS},
            }
        )
    return records, missing


def summarise_dataset(dataset, records, missing):
    paper = PAPER[dataset]
    reproduced_mean = None
    reproduced_sd = None
    reproduced_range = None
    threshold_means = {threshold: None for threshold in THRESHOLDS}
    if records:
        section_values = np.asarray([record["mSCF1"] for record in records], dtype=float)
        reproduced_mean = float(np.mean(section_values))
        reproduced_sd = float(np.std(section_values, ddof=1)) if len(records) > 1 else None
        reproduced_range = [float(np.min(section_values)), float(np.max(section_values))]
        threshold_means = {
            threshold: float(np.mean([record["F1_" + threshold] for record in records]))
            for threshold in THRESHOLDS
        }

    paper_ci = paper["mSCF1_95_ci"]
    return {
        "expected_sections": len(SECTIONS[dataset]),
        "completed_sections": len(records),
        "missing_sections": missing,
        "complete": len(records) == len(SECTIONS[dataset]),
        "reproduced_mean_mSCF1": reproduced_mean,
        "reproduced_section_sd_mSCF1": reproduced_sd,
        "reproduced_section_range_mSCF1": reproduced_range,
        "reproduced_mean_threshold_f1": threshold_means,
        "paper_mean_mSCF1": paper["mSCF1"],
        "paper_mSCF1_95_ci": paper_ci,
        "difference_reproduced_minus_paper": (
            None if reproduced_mean is None else reproduced_mean - paper["mSCF1"]
        ),
        "reproduced_mean_within_paper_95_ci": (
            None
            if reproduced_mean is None
            else paper_ci[0] <= reproduced_mean <= paper_ci[1]
        ),
        "interpretation_guardrail": (
            "Interval membership is descriptive consistency, not proof of exact "
            "reproduction or statistical equivalence."
        ),
    }


def plot_thresholds(ax, dataset, records):
    x = np.arange(len(THRESHOLDS))
    width = 0.36
    paper_values = [PAPER[dataset]["threshold_f1"][threshold] for threshold in THRESHOLDS]
    ax.bar(x - width / 2, paper_values, width, label="Weigand Table 3", color="#5b6573")

    if records:
        reproduced = [
            np.mean([record["F1_" + threshold] for record in records])
            for threshold in THRESHOLDS
        ]
        ax.bar(x + width / 2, reproduced, width, label="Our reproduction", color="#2b7a78")
    else:
        ax.text(0.5, 0.53, "Reproduction not run yet", ha="center", transform=ax.transAxes)

    ax.set_xticks(x, ["F1 " + threshold for threshold in THRESHOLDS])
    ax.set_ylim(0, 0.7)
    ax.set_ylabel("F1 (higher is better)")
    ax.set_title("{} threshold-level comparison (n={}/8)".format(dataset, len(records)))
    ax.grid(axis="y", alpha=0.2)
    ax.legend(frameon=False, loc="upper right")


def plot_sections(ax, dataset, records):
    by_section = {record["section"]: record for record in records}
    names = SECTIONS[dataset]
    values = [by_section.get(name, {}).get("mSCF1", np.nan) for name in names]
    x = np.arange(len(names))

    ax.bar(x, values, color="#4c78a8")
    low, high = PAPER[dataset]["mSCF1_95_ci"]
    ax.axhspan(low, high, color="#f2c14e", alpha=0.22, label="Paper 95% CI")
    ax.axhline(
        PAPER[dataset]["mSCF1"], color="#c44e52", linewidth=2, label="Paper mean"
    )
    if records:
        reproduced_mean = np.mean([record["mSCF1"] for record in records])
        ax.axhline(
            reproduced_mean,
            color="#2b7a78",
            linewidth=2,
            linestyle="--",
            label="Our mean",
        )
    ax.set_xticks(x, names, rotation=35, ha="center")
    ax.set_ylim(0, 0.75)
    ax.set_ylabel("mSCF1 (higher is better)")
    ax.set_title("{} tissue sections (n={}/8)".format(dataset, len(records)))
    ax.grid(axis="y", alpha=0.2)
    ax.legend(frameon=False, loc="upper right")


def main():
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    roots = {"GBM": args.gbm_root, "CAC": args.cac_root}
    records = {}
    summaries = {}
    for dataset in ("GBM", "CAC"):
        records[dataset], missing = read_dataset(dataset, roots[dataset])
        summaries[dataset] = summarise_dataset(dataset, records[dataset], missing)

    rows = records["GBM"] + records["CAC"]
    with (args.output / "section_metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["dataset", "section", "mSCF1"]
            + ["F1_" + threshold for threshold in THRESHOLDS],
        )
        writer.writeheader()
        writer.writerows(rows)

    comparison = {
        "source": {
            "paper": "Weigand et al. (2026), Spatial self-supervised Peak Learning",
            "reported_values": "Table 3",
            "section_order": "Figure 3",
            "scale": "fractions from 0 to 1",
        },
        "method": "legacy msiPL VAE-BN plus LearnPeaks",
        "datasets": summaries,
        "status": "complete" if all(item["complete"] for item in summaries.values()) else "partial",
    }
    with (args.output / "comparison.json").open("w", encoding="utf-8") as stream:
        json.dump(comparison, stream, indent=2)
        stream.write("\n")

    fig, axes = plt.subplots(2, 2, figsize=(16, 10), constrained_layout=True)
    plot_thresholds(axes[0, 0], "GBM", records["GBM"])
    plot_thresholds(axes[0, 1], "CAC", records["CAC"])
    plot_sections(axes[1, 0], "GBM", records["GBM"])
    plot_sections(axes[1, 1], "CAC", records["CAC"])
    fig.suptitle("Legacy msiPL reproduction vs Weigand et al. (2026)", fontsize=18)
    fig.savefig(args.output / "msipl_weigand_comparison.png", dpi=180)
    plt.close(fig)

    print(json.dumps(comparison, indent=2))
    print("Saved comparison outputs to {}".format(args.output))


if __name__ == "__main__":
    main()
