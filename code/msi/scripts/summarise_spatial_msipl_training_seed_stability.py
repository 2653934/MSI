#!/usr/bin/env python3
"""Summarise matched GBM108-positive evaluations across three training seeds."""

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


DATASET = "GBM108_positive"
SEEDS = (1, 2, 3)
VARIANTS = ("central_only", "uniform_mean", "attention_sqrt_bins")
LABELS = {
    "central_only": "Centre-only",
    "uniform_mean": "Uniform mean",
    "attention_sqrt_bins": "Corrected attention",
}
COLOURS = {
    "central_only": "#264653",
    "uniform_mean": "#457B9D",
    "attention_sqrt_bins": "#E76F51",
}


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def read_json(path):
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def training_summary(project_root, seed, variant):
    experiments = project_root / "results" / "experiments"
    if seed in (2, 3):
        return read_json(
            experiments
            / "spatial_msipl_training_seed_stability"
            / f"{DATASET}_seed{seed}"
            / variant
            / "summary.json"
        )
    if variant == "central_only":
        root = experiments / "spatial_msipl_reconstruction"
    else:
        root = experiments / "spatial_msipl_neighbourhood"
    return read_json(root / f"{DATASET}_seed1" / variant / "summary.json")


def faithfulness_mean(attribution):
    return float(
        np.mean(
            [
                record["integrated_gradients_mean_posterior_drop"]
                for record in attribution["faithfulness"]["records"]
            ]
        )
    )


def collect(project_root):
    experiments = project_root / "results" / "experiments"
    rows = []
    for variant in VARIANTS:
        for seed in SEEDS:
            evaluation = read_json(
                experiments
                / "spatial_msipl_attributed_peak_evaluation"
                / f"{DATASET}_seed{seed}"
                / variant
                / "summary.json"
            )
            attribution = read_json(
                experiments
                / "spatial_msipl_gmm_integrated_gradients"
                / f"{DATASET}_seed{seed}"
                / variant
                / "summary.json"
            )
            training = training_summary(project_root, seed, variant)
            rows.append(
                {
                    "dataset": DATASET,
                    "variant": variant,
                    "training_seed": seed,
                    "evaluation_seed": 1,
                    "matched_peak_count": evaluation["matched_peak_evaluation"]["count"],
                    "mscf1": evaluation["matched_peak_evaluation"]["methods"]["integrated_gradients"]["mSCF1"],
                    "gmm_balanced_accuracy": evaluation["cluster_mapping"]["balanced_accuracy"],
                    "ig_faithfulness_mean_drop": faithfulness_mean(attribution),
                    "attribution_seconds": attribution["runtime_seconds"],
                    "training_seconds": training["training_seconds"],
                    "peak_gpu_memory_bytes": training["peak_gpu_memory_allocated_bytes"],
                    "final_total_loss": training["final_total_loss"],
                }
            )
    return rows


def metric_summary(rows, variant, key):
    values = np.asarray(
        [row[key] for row in rows if row["variant"] == variant], dtype=float
    )
    return {
        "values": [float(value) for value in values],
        "mean": float(values.mean()),
        "sample_standard_deviation": float(values.std(ddof=1)),
        "minimum": float(values.min()),
        "maximum": float(values.max()),
    }


def paired_differences(rows, left, right, key):
    by_key = {(row["variant"], row["training_seed"]): row for row in rows}
    differences = [
        by_key[(left, seed)][key] - by_key[(right, seed)][key]
        for seed in SEEDS
    ]
    values = np.asarray(differences, dtype=float)
    return {
        "left": left,
        "right": right,
        "metric": key,
        "per_seed_left_minus_right": {
            str(seed): float(value) for seed, value in zip(SEEDS, values)
        },
        "mean_left_minus_right": float(values.mean()),
        "sample_standard_deviation": float(values.std(ddof=1)),
        "left_wins": int((values > 0).sum()),
        "right_wins": int((values < 0).sum()),
        "ties": int((values == 0).sum()),
    }


def save_csv(rows, path):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save_figure(rows, output):
    metrics = (
        ("mscf1", "Matched-count mSCF1", "higher is better"),
        ("gmm_balanced_accuracy", "GMM balanced accuracy", "higher is better"),
        ("ig_faithfulness_mean_drop", "Deletion faithfulness", "higher is better"),
    )
    x = np.arange(len(VARIANTS))
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    for axis, (key, title, subtitle) in zip(axes, metrics):
        for index, variant in enumerate(VARIANTS):
            values = np.asarray(
                [row[key] for row in rows if row["variant"] == variant], dtype=float
            )
            axis.bar(
                index,
                values.mean(),
                color=COLOURS[variant],
                alpha=0.78,
                yerr=values.std(ddof=1),
                capsize=5,
            )
            jitter = np.asarray((-0.08, 0.0, 0.08))
            axis.scatter(
                np.full(3, index) + jitter,
                values,
                color="black",
                s=28,
                zorder=3,
            )
            for dx, value, seed in zip(jitter, values, SEEDS):
                axis.annotate(
                    f"s{seed}",
                    (index + dx, value),
                    xytext=(0, 6),
                    textcoords="offset points",
                    ha="center",
                    fontsize=7,
                )
        axis.set_xticks(x, [LABELS[value] for value in VARIANTS], rotation=20, ha="right")
        axis.set_title(f"{title}\n({subtitle}; bars = mean, error = sample SD)")
        axis.grid(axis="y", alpha=0.2)
    fig.suptitle("GBM108 positive: model-training seed stability", fontsize=14)
    fig.tight_layout()
    fig.savefig(output / "gbm108_positive_seed_stability.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_markdown(summary, output):
    lines = [
        "# GBM108-positive training-seed stability",
        "",
        "Three independently trained seeds were evaluated with the same GMM and attribution sampling seeds.",
        "All methods selected the same 530 peaks, so variation reflects model training rather than peak budget.",
        "",
        "## Mean ± sample SD across three seeds",
        "",
        "| Variant | mSCF1 | GMM balanced accuracy | IG deletion faithfulness | Training hours | Peak GPU GiB |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for variant in VARIANTS:
        metrics = summary["variant_metrics"][variant]
        def display(key, scale=1.0):
            record = metrics[key]
            return f"{record['mean'] / scale:.4f} ± {record['sample_standard_deviation'] / scale:.4f}"
        lines.append(
            f"| {LABELS[variant]} | {display('mscf1')} | "
            f"{display('gmm_balanced_accuracy')} | {display('ig_faithfulness_mean_drop')} | "
            f"{display('training_seconds', 3600)} | {display('peak_gpu_memory_bytes', 2**30)} |"
        )
    attention_delta = summary["paired_differences"]["attention_minus_uniform_mscf1"]
    uniform_delta = summary["paired_differences"]["uniform_minus_centre_mscf1"]
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- Corrected attention minus uniform-mean mSCF1: {attention_delta['mean_left_minus_right']:+.4f} on average; attention wins {attention_delta['left_wins']}/3 seeds.",
            f"- Uniform-mean minus centre-only mSCF1: {uniform_delta['mean_left_minus_right']:+.4f} on average; uniform wins {uniform_delta['left_wins']}/3 seeds.",
            "- With only three seeds, report the spread and per-seed values; do not treat this as a high-powered significance test.",
            "- The predeclared attention decision also requires deletion faithfulness, not mSCF1 alone.",
        ]
    )
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = arguments()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = collect(args.project_root)
    metric_names = (
        "mscf1",
        "gmm_balanced_accuracy",
        "ig_faithfulness_mean_drop",
        "attribution_seconds",
        "training_seconds",
        "peak_gpu_memory_bytes",
        "final_total_loss",
    )
    variant_metrics = {
        variant: {
            metric: metric_summary(rows, variant, metric) for metric in metric_names
        }
        for variant in VARIANTS
    }
    paired = {
        "attention_minus_uniform_mscf1": paired_differences(
            rows, "attention_sqrt_bins", "uniform_mean", "mscf1"
        ),
        "uniform_minus_centre_mscf1": paired_differences(
            rows, "uniform_mean", "central_only", "mscf1"
        ),
        "attention_minus_uniform_faithfulness": paired_differences(
            rows,
            "attention_sqrt_bins",
            "uniform_mean",
            "ig_faithfulness_mean_drop",
        ),
    }
    attention_mscf1 = paired["attention_minus_uniform_mscf1"]
    attention_faithfulness = paired["attention_minus_uniform_faithfulness"]
    summary = {
        "status": "complete",
        "dataset": DATASET,
        "training_seeds": list(SEEDS),
        "evaluation_seed": 1,
        "matched_peak_count": 530,
        "design_note": (
            "Only the training seed changes. GMM seed, attribution sampling seed, "
            "evaluation settings, and peak count are fixed."
        ),
        "variant_metrics": variant_metrics,
        "paired_differences": paired,
        "attention_gate": {
            "required_mean_mscf1_gain": 0.02,
            "requires_noninferior_mean_deletion_faithfulness": True,
            "observed_mean_mscf1_gain": attention_mscf1["mean_left_minus_right"],
            "observed_mean_faithfulness_gain": attention_faithfulness["mean_left_minus_right"],
            "passed": bool(
                attention_mscf1["mean_left_minus_right"] >= 0.02
                and attention_faithfulness["mean_left_minus_right"] >= 0.0
            ),
        },
        "runs": rows,
    }
    save_csv(rows, args.output / "seed_metrics.csv")
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    save_figure(rows, args.output)
    save_markdown(summary, args.output)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
