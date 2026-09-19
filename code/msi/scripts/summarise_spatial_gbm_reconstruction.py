#!/usr/bin/env python3
"""Aggregate centre-only versus uniform-mean reconstruction over eight GBM sections."""

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
ERROR_METRICS = (
    "scaled_categorical_cross_entropy",
    "mean_squared_error",
    "mean_absolute_error",
)


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def load_json(path):
    if not path.is_file():
        raise FileNotFoundError(f"missing required result: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("status") != "complete":
        raise ValueError(f"result is not complete: {path}")
    return value


def paired_test(central, uniform):
    central = np.asarray(central, dtype=float)
    uniform = np.asarray(uniform, dtype=float)
    differences = uniform - central
    if np.allclose(differences, 0, rtol=0, atol=0):
        return {"statistic": 0.0, "p_value_two_sided": 1.0}
    result = wilcoxon(uniform, central, alternative="two-sided", method="auto")
    return {
        "statistic": float(result.statistic),
        "p_value_two_sided": float(result.pvalue),
    }


def save_figure(records, output):
    labels = [record["dataset"] for record in records]
    x = np.arange(len(records))
    mse_change = [record["mse_relative_change_percent"] for record in records]
    cosine_change = [record["cosine_absolute_change"] for record in records]
    runtime_ratio = [record["training_runtime_ratio"] for record in records]

    figure, axes = plt.subplots(1, 3, figsize=(19, 5.5))
    colours = ["#2A9D8F" if value < 0 else "#E76F51" for value in mse_change]
    axes[0].bar(x, mse_change, color=colours)
    axes[0].axhline(0, color="black", linewidth=1)
    axes[0].set_title("Uniform-mean MSE change")
    axes[0].set_ylabel("Relative to centre-only (%)\nnegative = uniform better")

    colours = ["#2A9D8F" if value > 0 else "#E76F51" for value in cosine_change]
    axes[1].bar(x, cosine_change, color=colours)
    axes[1].axhline(0, color="black", linewidth=1)
    axes[1].set_title("Uniform-mean cosine change")
    axes[1].set_ylabel("Absolute change\npositive = uniform better")

    axes[2].bar(x, runtime_ratio, color="#457B9D")
    axes[2].axhline(1, color="black", linewidth=1, linestyle="--")
    axes[2].set_title("Training-runtime ratio")
    axes[2].set_ylabel("Uniform / centre-only")

    for axis in axes:
        axis.set_xticks(x, labels, rotation=35, ha="right")
        axis.grid(axis="y", alpha=0.2)
    figure.suptitle("Frozen Spatial-msiPL reconstruction validation across MassNet GBM")
    figure.tight_layout()
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


def main():
    args = parse_arguments()
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    metric_values = {
        metric: {"central_only": [], "uniform_mean": []}
        for metric in (*ERROR_METRICS, "cosine_similarity")
    }

    for dataset in DATASETS:
        comparison_path = (
            args.project_root
            / "results"
            / "experiments"
            / "spatial_msipl_reconstruction"
            / f"{dataset}_seed1"
            / "evaluation"
            / "comparison.json"
        )
        comparison = load_json(comparison_path)
        models = comparison["models"]
        if not {"central_only", "uniform_mean"}.issubset(models):
            raise ValueError(f"missing matched models in {comparison_path}")
        central = models["central_only"]
        uniform = models["uniform_mean"]

        uniform_training = load_json(
            args.project_root
            / "results"
            / "experiments"
            / "spatial_msipl_neighbourhood"
            / f"{dataset}_seed1"
            / "uniform_mean"
            / "summary.json"
        )
        central_training = load_json(
            args.project_root
            / "results"
            / "experiments"
            / "spatial_msipl_reconstruction"
            / f"{dataset}_seed1"
            / "central_only"
            / "summary.json"
        )

        for metric in metric_values:
            metric_values[metric]["central_only"].append(float(central[metric]))
            metric_values[metric]["uniform_mean"].append(float(uniform[metric]))

        records.append(
            {
                "dataset": dataset,
                "pixels": int(central["pixels"]),
                "central_mse": float(central["mean_squared_error"]),
                "uniform_mse": float(uniform["mean_squared_error"]),
                "mse_relative_change_percent": 100.0
                * (uniform["mean_squared_error"] - central["mean_squared_error"])
                / central["mean_squared_error"],
                "central_cosine": float(central["cosine_similarity"]),
                "uniform_cosine": float(uniform["cosine_similarity"]),
                "cosine_absolute_change": float(
                    uniform["cosine_similarity"] - central["cosine_similarity"]
                ),
                "central_parameters": int(central["parameters"]),
                "uniform_parameters": int(uniform["parameters"]),
                "central_training_seconds": float(
                    central_training["training_seconds"]
                ),
                "uniform_training_seconds": float(
                    uniform_training["training_seconds"]
                ),
                "training_runtime_ratio": float(
                    uniform_training["training_seconds"]
                    / central_training["training_seconds"]
                ),
                "central_peak_gpu_memory_bytes": int(
                    central_training["peak_gpu_memory_allocated_bytes"]
                ),
                "uniform_peak_gpu_memory_bytes": int(
                    uniform_training["peak_gpu_memory_allocated_bytes"]
                ),
            }
        )

    with (args.output / "per_section.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

    tests = {}
    wins = {}
    for metric, values in metric_values.items():
        central = np.asarray(values["central_only"], dtype=float)
        uniform = np.asarray(values["uniform_mean"], dtype=float)
        tests[metric] = paired_test(central, uniform)
        if metric in ERROR_METRICS:
            uniform_wins = int(np.count_nonzero(uniform < central))
            central_wins = int(np.count_nonzero(central < uniform))
        else:
            uniform_wins = int(np.count_nonzero(uniform > central))
            central_wins = int(np.count_nonzero(central > uniform))
        wins[metric] = {
            "uniform_mean": uniform_wins,
            "central_only": central_wins,
            "ties": len(DATASETS) - uniform_wins - central_wins,
        }

    mse_changes = np.asarray(
        [record["mse_relative_change_percent"] for record in records]
    )
    cosine_changes = np.asarray(
        [record["cosine_absolute_change"] for record in records]
    )
    runtime_ratios = np.asarray(
        [record["training_runtime_ratio"] for record in records]
    )
    summary = {
        "status": "complete",
        "scope": "paired deterministic in-sample reconstruction over all eight MassNet GBM sections",
        "models": ["central_only", "uniform_mean"],
        "sections": len(records),
        "per_section": records,
        "aggregate": {
            "mse_relative_change_percent_uniform_vs_central": {
                "mean": float(mse_changes.mean()),
                "sample_standard_deviation": float(mse_changes.std(ddof=1)),
                "median": float(np.median(mse_changes)),
                "minimum": float(mse_changes.min()),
                "maximum": float(mse_changes.max()),
            },
            "cosine_absolute_change_uniform_minus_central": {
                "mean": float(cosine_changes.mean()),
                "sample_standard_deviation": float(cosine_changes.std(ddof=1)),
            },
            "training_runtime_ratio_uniform_over_central": {
                "mean": float(runtime_ratios.mean()),
                "sample_standard_deviation": float(runtime_ratios.std(ddof=1)),
            },
            "paired_wilcoxon_two_sided": tests,
            "section_win_counts": wins,
        },
        "interpretation_limits": [
            "Reconstruction is deterministic decoder output from the encoder mean on each model's unsupervised full-section training data.",
            "Section-level paired tests have n=8 and should be interpreted with effect sizes and direction consistency, not p-values alone.",
            "This comparison tests reconstruction, not peak-selection quality or biological validity.",
        ],
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    save_figure(records, args.output / "reconstruction_validation.png")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
