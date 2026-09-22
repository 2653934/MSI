#!/usr/bin/env python3
"""Aggregate the frozen eight-section CAC validation campaign."""

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
    "40TopL",
    "160TopL",
    "200TopL",
    "240TopL",
    "280TopL",
    "360TopL",
    "400TopL",
    "520TopL",
)


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def read_json(path):
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def paired_summary(rows, left, right, higher_is_better=True):
    left_values = np.asarray([row[left] for row in rows], dtype=float)
    right_values = np.asarray([row[right] for row in rows], dtype=float)
    differences = left_values - right_values
    statistic, p_value = wilcoxon(
        differences,
        alternative="two-sided",
        method="exact",
        zero_method="wilcox",
    )
    preferred = differences > 0 if higher_is_better else differences < 0
    return {
        "left": left,
        "right": right,
        "higher_is_better": higher_is_better,
        "mean_left": float(left_values.mean()),
        "mean_right": float(right_values.mean()),
        "mean_left_minus_right": float(differences.mean()),
        "median_left_minus_right": float(np.median(differences)),
        "left_wins": int(preferred.sum()),
        "right_wins": int((~preferred & (differences != 0)).sum()),
        "ties": int((differences == 0).sum()),
        "wilcoxon_statistic": float(statistic),
        "wilcoxon_two_sided_exact_p": float(p_value),
    }


def faithfulness_mean(summary, field):
    values = [record[field] for record in summary["faithfulness"]["records"]]
    return float(np.mean(values))


def collect(project_root):
    rows = []
    for dataset in DATASETS:
        experiment_root = project_root / "results" / "experiments"
        spatial_eval = read_json(
            experiment_root
            / "spatial_msipl_cac_attributed_peak_evaluation"
            / f"{dataset}_seed1"
            / "uniform_mean"
            / "summary.json"
        )
        central_eval = read_json(
            experiment_root
            / "spatial_msipl_cac_attributed_peak_evaluation"
            / f"{dataset}_seed1"
            / "central_only"
            / "summary.json"
        )
        spatial_attr = read_json(
            experiment_root
            / "spatial_msipl_cac_gmm_integrated_gradients"
            / f"{dataset}_seed1"
            / "uniform_mean"
            / "summary.json"
        )
        central_attr = read_json(
            experiment_root
            / "spatial_msipl_cac_gmm_integrated_gradients"
            / f"{dataset}_seed1"
            / "central_only"
            / "summary.json"
        )
        reconstruction = read_json(
            experiment_root
            / "spatial_msipl_cac_reconstruction"
            / f"{dataset}_seed1"
            / "evaluation"
            / "comparison.json"
        )
        spatial_training = read_json(
            experiment_root
            / "spatial_msipl_cac_neighbourhood"
            / f"{dataset}_seed1"
            / "uniform_mean"
            / "summary.json"
        )
        central_training = read_json(
            experiment_root
            / "spatial_msipl_cac_reconstruction"
            / f"{dataset}_seed1"
            / "central_only"
            / "summary.json"
        )
        matched_peak_count = spatial_eval["matched_peak_evaluation"]["count"]
        s3pl_original_root = (
            project_root
            / "results"
            / "baselines"
            / "s3pl"
            / f"{dataset}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9"
        )
        s3pl_matched_root = Path(
            f"{s3pl_original_root}_matched_{matched_peak_count}peaks"
        )
        s3pl_metrics = read_json(s3pl_matched_root / "metrics.json")
        # Matched-count evaluation reuses the original trained checkpoint, so
        # training compute belongs to the original run rather than evaluation.
        s3pl_runtime = read_json(s3pl_original_root / "runtime_metrics.json")

        spatial_methods = spatial_eval["matched_peak_evaluation"]["methods"]
        central_methods = central_eval["matched_peak_evaluation"]["methods"]
        spatial_recon = reconstruction["models"]["uniform_mean"]
        central_recon = reconstruction["models"]["central_only"]
        rows.append(
            {
                "dataset": dataset,
                "matched_peak_count": matched_peak_count,
                "s3pl_peak_count": s3pl_metrics["number_picked_peaks"],
                "spatial_ig_mscf1": spatial_methods["integrated_gradients"]["mSCF1"],
                "central_ig_mscf1": central_methods["integrated_gradients"]["mSCF1"],
                "legacy_msipl_mscf1": spatial_methods["legacy_msipl"]["mSCF1"],
                "spatial_l2_mscf1": spatial_methods["first_layer_l2"]["mSCF1"],
                "central_l2_mscf1": central_methods["first_layer_l2"]["mSCF1"],
                "s3pl_mscf1": s3pl_metrics["mSCF1"],
                "spatial_gmm_balanced_accuracy": spatial_eval["cluster_mapping"]["balanced_accuracy"],
                "central_gmm_balanced_accuracy": central_eval["cluster_mapping"]["balanced_accuracy"],
                "spatial_reconstruction_mse": spatial_recon["mean_squared_error"],
                "central_reconstruction_mse": central_recon["mean_squared_error"],
                "spatial_reconstruction_cosine": spatial_recon["cosine_similarity"],
                "central_reconstruction_cosine": central_recon["cosine_similarity"],
                "spatial_training_seconds": spatial_training["training_seconds"],
                "central_training_seconds": central_training["training_seconds"],
                "s3pl_training_seconds": s3pl_runtime["training_seconds"],
                "s3pl_total_seconds": s3pl_runtime["total_seconds"],
                "spatial_peak_gpu_memory_bytes": spatial_training["peak_gpu_memory_allocated_bytes"],
                "central_peak_gpu_memory_bytes": central_training["peak_gpu_memory_allocated_bytes"],
                "s3pl_peak_gpu_memory_bytes": s3pl_runtime["peak_gpu_memory_bytes"],
                "spatial_attribution_seconds": spatial_attr["runtime_seconds"],
                "central_attribution_seconds": central_attr["runtime_seconds"],
                "spatial_ig_faithfulness_mean_drop": faithfulness_mean(
                    spatial_attr, "integrated_gradients_mean_posterior_drop"
                ),
                "central_ig_faithfulness_mean_drop": faithfulness_mean(
                    central_attr, "integrated_gradients_mean_posterior_drop"
                ),
                "spatial_random_faithfulness_mean_drop": faithfulness_mean(
                    spatial_attr, "random_mean_posterior_drop"
                ),
                "central_random_faithfulness_mean_drop": faithfulness_mean(
                    central_attr, "random_mean_posterior_drop"
                ),
            }
        )
    return rows


def save_csv(rows, path):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save_peak_figure(rows, output):
    x = np.arange(len(rows))
    width = 0.2
    series = (
        ("legacy_msipl_mscf1", "Legacy msiPL", "#8D99AE"),
        ("central_ig_mscf1", "Centre-only IG", "#264653"),
        ("spatial_ig_mscf1", "Spatial IG", "#457B9D"),
        ("s3pl_mscf1", "S3PL reproduction*", "#E9C46A"),
    )
    fig, axis = plt.subplots(figsize=(14, 6.5))
    for index, (key, label, colour) in enumerate(series):
        axis.bar(x + (index - 1.5) * width, [row[key] for row in rows], width, label=label, color=colour)
    axis.set_xticks(x, [row["dataset"] for row in rows], rotation=25, ha="right")
    axis.set_ylim(0, 0.85)
    axis.set_ylabel("mSCF1 (higher is better)")
    axis.set_title("CAC peak-selection comparison across eight tissue sections")
    axis.legend(ncol=2)
    axis.text(
        0.01,
        -0.24,
        "*All four methods use the same section-specific peak count. S3PL was re-evaluated from "
        "its existing checkpoint; it was not retrained.",
        transform=axis.transAxes,
        fontsize=9,
    )
    fig.tight_layout()
    fig.savefig(output / "cac_peak_selection_comparison.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_context_figure(rows, output):
    x = np.arange(len(rows))
    labels = [row["dataset"] for row in rows]
    fig, axes = plt.subplots(1, 3, figsize=(19, 5.8))

    ig_delta = [row["spatial_ig_mscf1"] - row["central_ig_mscf1"] for row in rows]
    axes[0].bar(x, ig_delta, color="#457B9D")
    axes[0].axhline(0, color="black", linewidth=0.8)
    axes[0].set_title("Spatial − centre-only peak mSCF1")
    axes[0].set_ylabel("Difference (positive favours context)")

    width = 0.36
    axes[1].bar(
        x - width / 2,
        [row["central_gmm_balanced_accuracy"] for row in rows],
        width,
        label="Centre-only",
        color="#264653",
    )
    axes[1].bar(
        x + width / 2,
        [row["spatial_gmm_balanced_accuracy"] for row in rows],
        width,
        label="Spatial",
        color="#457B9D",
    )
    axes[1].set_ylim(0, 1)
    axes[1].set_title("Label-free GMM balanced accuracy")
    axes[1].legend()

    mse_delta = [
        100
        * (row["spatial_reconstruction_mse"] - row["central_reconstruction_mse"])
        / row["central_reconstruction_mse"]
        for row in rows
    ]
    axes[2].bar(x, mse_delta, color=["#E76F51" if value > 0 else "#2A9D8F" for value in mse_delta])
    axes[2].axhline(0, color="black", linewidth=0.8)
    axes[2].set_title("Spatial reconstruction MSE change")
    axes[2].set_ylabel("Percent vs centre-only (negative is better)")

    for axis in axes:
        axis.set_xticks(x, labels, rotation=35, ha="right")
        axis.set_xlabel("CAC section")
    fig.tight_layout()
    fig.savefig(output / "cac_context_effects.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_compute_figure(rows, output):
    labels = ("Centre-only\n100 epochs", "Spatial\n100 epochs", "S3PL\n10 epochs")
    training = (
        np.mean([row["central_training_seconds"] for row in rows]),
        np.mean([row["spatial_training_seconds"] for row in rows]),
        np.mean([row["s3pl_training_seconds"] for row in rows]),
    )
    memory = (
        np.mean([row["central_peak_gpu_memory_bytes"] for row in rows]) / 2**20,
        np.mean([row["spatial_peak_gpu_memory_bytes"] for row in rows]) / 2**20,
        np.mean([row["s3pl_peak_gpu_memory_bytes"] for row in rows]) / 2**20,
    )
    colours = ("#264653", "#457B9D", "#E9C46A")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].bar(labels, training, color=colours)
    axes[0].set_ylabel("Mean training seconds")
    axes[0].set_title("Observed full training time")
    axes[1].bar(labels, memory, color=colours)
    axes[1].set_ylabel("Peak allocated GPU memory (MiB)")
    axes[1].set_title("Observed GPU allocation")
    fig.tight_layout()
    fig.savefig(output / "cac_computational_comparison.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_markdown(rows, comparisons, output):
    mean = lambda key: float(np.mean([row[key] for row in rows]))
    lines = [
        "# Frozen CAC validation summary",
        "",
        "Eight CAC sections were evaluated with the frozen uniform-neighbourhood and centre-only VAEs.",
        "Peak selection used GMM Integrated Gradients with the same tuned legacy msiPL count per section.",
        "",
        "## Aggregate results",
        "",
        f"- Spatial IG mean mSCF1: {mean('spatial_ig_mscf1'):.4f}",
        f"- Centre-only IG mean mSCF1: {mean('central_ig_mscf1'):.4f}",
        f"- Legacy msiPL mean mSCF1: {mean('legacy_msipl_mscf1'):.4f}",
        f"- S3PL reproduction mean mSCF1: {mean('s3pl_mscf1'):.4f} (peak-count matched)",
        f"- Spatial GMM mean balanced accuracy: {mean('spatial_gmm_balanced_accuracy'):.4f}",
        f"- Centre-only GMM mean balanced accuracy: {mean('central_gmm_balanced_accuracy'):.4f}",
        "",
        "## Paired conclusions",
        "",
    ]
    for name, result in comparisons.items():
        lines.append(
            f"- {name}: mean difference {result['mean_left_minus_right']:+.4f}; "
            f"wins {result['left_wins']}/8; exact two-sided Wilcoxon "
            f"p={result['wilcoxon_two_sided_exact_p']:.6f}."
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Spatial context consistently improves IG peak-selection mSCF1 over the matched centre-only control,",
            "but it does not consistently improve reconstruction or GMM agreement with expert classes.",
            "Both nonlinear IG methods outperform legacy msiPL. First-layer L2 remains an inadequate peak ranking.",
            "S3PL has the highest mean mSCF1 after using the same section-specific peak counts as the other methods.",
        ]
    )
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = parse_arguments()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = collect(args.project_root)
    comparisons = {
        "spatial IG versus centre-only IG": paired_summary(rows, "spatial_ig_mscf1", "central_ig_mscf1"),
        "spatial IG versus legacy msiPL": paired_summary(rows, "spatial_ig_mscf1", "legacy_msipl_mscf1"),
        "spatial IG versus S3PL reproduction": paired_summary(rows, "spatial_ig_mscf1", "s3pl_mscf1"),
        "spatial versus centre-only GMM balanced accuracy": paired_summary(
            rows, "spatial_gmm_balanced_accuracy", "central_gmm_balanced_accuracy"
        ),
        "spatial versus centre-only reconstruction MSE": paired_summary(
            rows,
            "spatial_reconstruction_mse",
            "central_reconstruction_mse",
            higher_is_better=False,
        ),
        "spatial versus centre-only IG faithfulness": paired_summary(
            rows,
            "spatial_ig_faithfulness_mean_drop",
            "central_ig_faithfulness_mean_drop",
        ),
    }
    aggregate = {
        "status": "complete",
        "scope": "frozen eight-section CAC validation",
        "sections": list(DATASETS),
        "section_count": len(rows),
        "peak_count_note": (
            "Spatial IG, centre-only IG, first-layer L2, legacy msiPL, and S3PL use the same "
            "section-specific count. S3PL was re-evaluated without retraining."
        ),
        "method_means": {
            key: float(np.mean([row[key] for row in rows]))
            for key in (
                "spatial_ig_mscf1",
                "central_ig_mscf1",
                "legacy_msipl_mscf1",
                "spatial_l2_mscf1",
                "central_l2_mscf1",
                "s3pl_mscf1",
                "spatial_gmm_balanced_accuracy",
                "central_gmm_balanced_accuracy",
                "spatial_training_seconds",
                "central_training_seconds",
                "s3pl_training_seconds",
                "spatial_attribution_seconds",
                "central_attribution_seconds",
                "spatial_ig_faithfulness_mean_drop",
                "central_ig_faithfulness_mean_drop",
            )
        },
        "paired_comparisons": comparisons,
        "sections_data": rows,
    }
    save_csv(rows, args.output / "section_metrics.csv")
    (args.output / "comparison.json").write_text(
        json.dumps(aggregate, indent=2), encoding="utf-8"
    )
    save_peak_figure(rows, args.output)
    save_context_figure(rows, args.output)
    save_compute_figure(rows, args.output)
    save_markdown(rows, comparisons, args.output)
    print(json.dumps(aggregate, indent=2), flush=True)


if __name__ == "__main__":
    main()
