#!/usr/bin/env python3
"""Build a publication-facing summary from completed GBM and CAC aggregates.

This script keeps S3PL in a separate CAC benchmark because its architecture and
10-epoch training protocol differ, although its evaluation peak counts are now
matched section by section to Spatial-msiPL.
It reads existing aggregate artifacts only; it does not recalculate or alter any
model result.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


METHODS = (
    ("legacy_msipl", "Legacy msiPL", "#7f7f7f"),
    ("central_ig", "Centre-only IG", "#4c78a8"),
    ("spatial_ig", "Uniform-context IG", "#f28e2b"),
)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalise_records(gbm: dict, cac: dict) -> list[dict]:
    records: list[dict] = []
    for row in gbm["per_section"]:
        records.append(
            {
                "collection": "GBM",
                "section": row["dataset"],
                "matched_peaks": row["matched_peaks"],
                "legacy_msipl": row["legacy_msipl_mSCF1"],
                "central_ig": row["central_only_ig_mSCF1"],
                "spatial_ig": row["uniform_mean_ig_mSCF1"],
                "spatial_l2": row["uniform_mean_l2_mSCF1"],
                "context_delta": row["spatial_minus_centre_ig_mSCF1"],
                "s3pl": None,
                "s3pl_peaks": None,
            }
        )
    for row in cac["sections_data"]:
        records.append(
            {
                "collection": "CAC",
                "section": row["dataset"],
                "matched_peaks": row["matched_peak_count"],
                "legacy_msipl": row["legacy_msipl_mscf1"],
                "central_ig": row["central_ig_mscf1"],
                "spatial_ig": row["spatial_ig_mscf1"],
                "spatial_l2": row["spatial_l2_mscf1"],
                "context_delta": row["spatial_ig_mscf1"]
                - row["central_ig_mscf1"],
                "s3pl": row["s3pl_mscf1"],
                "s3pl_peaks": row["s3pl_peak_count"],
            }
        )
    return records


def method_summary(records: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for collection in ("GBM", "CAC"):
        subset = [row for row in records if row["collection"] == collection]
        for key, label, _ in METHODS:
            values = np.asarray([row[key] for row in subset], dtype=float)
            rows.append(
                {
                    "collection": collection,
                    "method": label,
                    "sections": len(values),
                    "mean_mSCF1": float(values.mean()),
                    "section_sd": float(values.std(ddof=1)),
                    "median_mSCF1": float(np.median(values)),
                    "minimum_mSCF1": float(values.min()),
                    "maximum_mSCF1": float(values.max()),
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_primary(records: list[dict], output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True)
    rng = np.random.default_rng(20260921)
    for axis, collection in zip(axes, ("GBM", "CAC"), strict=True):
        subset = [row for row in records if row["collection"] == collection]
        for index, (key, label, colour) in enumerate(METHODS):
            values = np.asarray([row[key] for row in subset], dtype=float)
            axis.bar(
                index,
                values.mean(),
                width=0.62,
                color=colour,
                alpha=0.82,
                edgecolor="black",
                linewidth=0.6,
                label=label,
            )
            jitter = rng.uniform(-0.10, 0.10, size=len(values))
            axis.scatter(
                np.full(len(values), index) + jitter,
                values,
                s=27,
                color="white",
                edgecolor="black",
                linewidth=0.65,
                zorder=3,
            )
            axis.errorbar(
                index,
                values.mean(),
                yerr=values.std(ddof=1),
                color="black",
                capsize=4,
                linewidth=1,
                zorder=4,
            )
        axis.set_title(f"{collection}: matched peak budget")
        axis.set_xticks(range(len(METHODS)), [label for _, label, _ in METHODS])
        axis.tick_params(axis="x", rotation=18)
        axis.grid(axis="y", alpha=0.25)
        axis.set_ylim(0, 0.75)
    axes[0].set_ylabel("mSCF1 (higher is better)")
    fig.suptitle("Primary peak-selection results (bars = mean; error bars = section SD)")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_context_effect(records: list[dict], output: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11, 7.2), sharey=True)
    colours = {"GBM": "#4c78a8", "CAC": "#f28e2b"}
    for axis, collection in zip(axes, ("GBM", "CAC"), strict=True):
        subset = [row for row in records if row["collection"] == collection]
        values = np.asarray([row["context_delta"] for row in subset], dtype=float)
        x = np.arange(len(subset))
        axis.axhline(0, color="black", linewidth=1)
        axis.bar(x, values, color=colours[collection], alpha=0.85)
        axis.set_xticks(x, [row["section"] for row in subset], rotation=28, ha="right")
        axis.set_title(
            f"{collection}: uniform-context IG minus centre-only IG "
            f"(wins {(values > 0).sum()}/{len(values)})"
        )
        axis.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("Δ mSCF1")
    axes[1].set_ylabel("Δ mSCF1")
    fig.suptitle("The contribution of uniform-mean neighbourhood context is dataset-dependent")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_explanation_ablation(records: list[dict], output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6), sharey=True)
    labels = ("First-layer L2", "Legacy msiPL", "Uniform-context IG")
    keys = ("spatial_l2", "legacy_msipl", "spatial_ig")
    colours = ("#e15759", "#7f7f7f", "#f28e2b")
    for axis, collection in zip(axes, ("GBM", "CAC"), strict=True):
        subset = [row for row in records if row["collection"] == collection]
        means = [np.mean([row[key] for row in subset]) for key in keys]
        axis.bar(np.arange(3), means, color=colours, edgecolor="black", linewidth=0.6)
        axis.set_xticks(np.arange(3), labels, rotation=20, ha="right")
        axis.set_title(collection)
        axis.grid(axis="y", alpha=0.25)
        axis.set_ylim(0, 0.62)
    axes[0].set_ylabel("Mean mSCF1")
    fig.suptitle("Explanation-method ablation")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_s3pl_context(records: list[dict], output: Path) -> None:
    subset = [row for row in records if row["collection"] == "CAC"]
    x = np.arange(len(subset))
    fig, axis = plt.subplots(figsize=(10.5, 4.7))
    axis.plot(x, [row["spatial_ig"] for row in subset], "o-", label="Uniform-context IG")
    axis.plot(x, [row["s3pl"] for row in subset], "s--", label="S3PL reproduction")
    axis.set_xticks(x, [row["section"] for row in subset], rotation=28, ha="right")
    axis.set_ylabel("mSCF1")
    axis.set_title("CAC benchmark with section-specific matched peak counts")
    axis.grid(alpha=0.25)
    axis.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def markdown_table(rows: list[dict], collection: str) -> list[str]:
    subset = [row for row in rows if row["collection"] == collection]
    lines = [
        "| Method | Mean mSCF1 | Section SD | Median |",
        "|---|---:|---:|---:|",
    ]
    for row in subset:
        lines.append(
            f"| {row['method']} | {row['mean_mSCF1']:.4f} | "
            f"{row['section_sd']:.4f} | {row['median_mSCF1']:.4f} |"
        )
    return lines


def write_report(path: Path, summaries: list[dict], gbm: dict, cac: dict, seeds: dict) -> None:
    gbm_cmp = gbm["aggregate"]
    cac_cmp = cac["paired_comparisons"]
    lines = [
        "# Current publication results",
        "",
        "This package summarizes the completed seed-1 model campaign. Section-level",
        "variation is shown explicitly; targeted training-seed stability is reported in a",
        "separate artifact. All primary method comparisons below use matched section-specific peak",
        "budgets.",
        "",
        "## Primary result",
        "",
        "Nonlinear Integrated Gradients improves peak selection over legacy msiPL across",
        "both collections. Uniform-mean context has a dataset-dependent contribution: it",
        "does not consistently improve GBM mSCF1, but improves all eight CAC sections.",
        "",
        "### GBM",
        "",
        *markdown_table(summaries, "GBM"),
        "",
        "- Uniform-context IG versus centre-only IG: mean change "
        f"{gbm_cmp['uniform_mean_ig_vs_central_only_ig']['mean_mSCF1_change']:+.4f}; "
        f"wins {gbm_cmp['uniform_mean_ig_vs_central_only_ig']['section_wins']}/8; "
        f"paired exact Wilcoxon p={gbm_cmp['uniform_mean_ig_vs_central_only_ig']['paired_wilcoxon_two_sided']['p_value_two_sided']:.6f}.",
        "- Uniform-context IG versus legacy msiPL: mean change "
        f"{gbm_cmp['uniform_mean_ig_vs_legacy_msipl']['mean_mSCF1_change']:+.4f}; "
        f"wins {gbm_cmp['uniform_mean_ig_vs_legacy_msipl']['section_wins']}/8; "
        f"p={gbm_cmp['uniform_mean_ig_vs_legacy_msipl']['paired_wilcoxon_two_sided']['p_value_two_sided']:.6f}.",
        "",
        "### CAC",
        "",
        *markdown_table(summaries, "CAC"),
        "",
        "- Uniform-context IG versus centre-only IG: mean change "
        f"{cac_cmp['spatial IG versus centre-only IG']['mean_left_minus_right']:+.4f}; "
        f"wins {cac_cmp['spatial IG versus centre-only IG']['left_wins']}/8; "
        f"p={cac_cmp['spatial IG versus centre-only IG']['wilcoxon_two_sided_exact_p']:.6f}.",
        "- Uniform-context IG versus legacy msiPL: mean change "
        f"{cac_cmp['spatial IG versus legacy msiPL']['mean_left_minus_right']:+.4f}; "
        f"wins {cac_cmp['spatial IG versus legacy msiPL']['left_wins']}/8; "
        f"p={cac_cmp['spatial IG versus legacy msiPL']['wilcoxon_two_sided_exact_p']:.6f}.",
        "",
        "## S3PL placement",
        "",
        "S3PL is retained as a separate CAC architecture benchmark. Its existing checkpoints",
        "were re-evaluated with the same section-specific peak counts as the primary methods;",
        "its training protocol remains the reproduced 10-epoch S3PL protocol.",
        f"Its mean CAC mSCF1 was {cac['method_means']['s3pl_mscf1']:.4f}, versus "
        f"{cac['method_means']['spatial_ig_mscf1']:.4f} for uniform-context IG.",
        "",
        "## Targeted training-seed stability",
        "",
        "On GBM108-positive, centre-only, uniform-mean and corrected-attention models",
        "were independently trained with seeds 1, 2 and 3. Evaluation randomness and the",
        "530-peak budget were fixed. Mean mSCF1 values were "
        f"{seeds['variant_metrics']['central_only']['mscf1']['mean']:.4f} for centre-only, "
        f"{seeds['variant_metrics']['uniform_mean']['mscf1']['mean']:.4f} for uniform mean "
        f"and {seeds['variant_metrics']['attention_sqrt_bins']['mscf1']['mean']:.4f} for "
        "corrected attention.",
        "",
        "Corrected attention beat uniform mean in all three seeds and improved mSCF1 by "
        f"{seeds['paired_differences']['attention_minus_uniform_mscf1']['mean_left_minus_right']:+.4f} "
        "on average. It nevertheless failed the combined predeclared gate because mean "
        "deletion faithfulness changed by "
        f"{seeds['paired_differences']['attention_minus_uniform_faithfulness']['mean_left_minus_right']:+.4f}. "
        "The result supports a small peak-quality benefit on this development section, not "
        "a claim of more faithful explanations or whole-dataset multi-seed superiority.",
        "",
        "## Interpretation boundaries",
        "",
        "- The neighbourhood conclusion currently concerns uniform-mean context, not all",
        "  possible learned neighbourhood aggregators.",
        "- First-layer L2 is an intentionally simple weight-magnitude comparator, not a",
        "  reimplementation of legacy LearnPeaks.",
        "- Full GBM and CAC section-wide validation uses seed 1. The three-seed analysis is",
        "  deliberately restricted to the GBM108-positive development section.",
        "- The eight sections within a collection are paired section-level units and are not",
        "  asserted to be eight independent patients.",
        "",
        "## Figures",
        "",
        "1. `figure_1_primary_peak_quality.png` — matched primary comparison.",
        "2. `figure_2_context_effect_by_section.png` — section-level context contribution.",
        "3. `figure_3_explanation_ablation.png` — L2, legacy msiPL, and nonlinear IG.",
        "4. `figure_s1_s3pl_contextual_cac.png` — matched-count S3PL architecture comparison.",
        "5. `figure_4_seed_stability.png` — targeted model-training seed stability.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.repo_root.resolve()
    gbm_path = root / "results/experiments/spatial_msipl_gbm_validation/context_attribution_control/summary.json"
    cac_path = root / "results/comparisons/spatial_msipl_cac_validation/comparison.json"
    seed_path = root / "results/experiments/spatial_msipl_training_seed_stability_summary/summary.json"
    output = root / "results/publication/current_evidence"
    output.mkdir(parents=True, exist_ok=True)

    gbm = load_json(gbm_path)
    cac = load_json(cac_path)
    seeds = load_json(seed_path)
    if any(item.get("status") != "complete" for item in (gbm, cac, seeds)):
        raise RuntimeError("GBM, CAC, and training-seed aggregate inputs must be complete")

    records = normalise_records(gbm, cac)
    summaries = method_summary(records)
    write_csv(output / "section_level_results.csv", records)
    write_csv(output / "aggregate_method_results.csv", summaries)
    plot_primary(records, output / "figure_1_primary_peak_quality.png")
    plot_context_effect(records, output / "figure_2_context_effect_by_section.png")
    plot_explanation_ablation(records, output / "figure_3_explanation_ablation.png")
    plot_s3pl_context(records, output / "figure_s1_s3pl_contextual_cac.png")
    shutil.copyfile(
        root
        / "results/experiments/spatial_msipl_training_seed_stability_summary"
        / "gbm108_positive_seed_stability.png",
        output / "figure_4_seed_stability.png",
    )
    write_report(output / "README.md", summaries, gbm, cac, seeds)
    print(f"Saved publication summary to {output}")


if __name__ == "__main__":
    main()
