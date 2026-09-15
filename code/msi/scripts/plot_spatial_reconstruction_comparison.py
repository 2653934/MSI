#!/usr/bin/env python3
"""Create an interpretable relative reconstruction comparison figure."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


COLOURS = ("#264653", "#457B9D", "#E9C46A", "#E76F51", "#6D597A")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comparison", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    comparison = json.loads(args.comparison.read_text(encoding="utf-8"))
    models = comparison["models"]
    names = list(models)
    labels = [models[name]["label"] for name in names]
    centre = models["central_only"]
    output = args.output or args.comparison.with_name(
        "reconstruction_comparison_relative.png"
    )

    cross_entropy_excess = [
        100.0
        * (models[name]["scaled_categorical_cross_entropy"] - centre["scaled_categorical_cross_entropy"])
        / centre["scaled_categorical_cross_entropy"]
        for name in names
    ]
    mse_excess = [
        100.0
        * (models[name]["mean_squared_error"] - centre["mean_squared_error"])
        / centre["mean_squared_error"]
        for name in names
    ]
    cosine = [models[name]["cosine_similarity"] for name in names]
    parameters = [models[name]["parameters"] / 1e6 for name in names]

    figure, axes = plt.subplots(2, 2, figsize=(14, 10))
    panels = (
        (cross_entropy_excess, "Cross-entropy excess vs centre-only", "% higher (lower is better)"),
        (mse_excess, "TIC-MSE excess vs centre-only", "% higher (lower is better)"),
        (cosine, "Cosine similarity", "Higher is better"),
        (parameters, "Model size", "Million parameters"),
    )
    for axis, (values, title, ylabel) in zip(axes.flat, panels):
        bars = axis.bar(np.arange(len(names)), values, color=COLOURS)
        axis.set_xticks(np.arange(len(names)), labels, rotation=22, ha="right")
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.grid(axis="y", alpha=0.2)
        axis.bar_label(bars, fmt="%.3f", padding=3, fontsize=8)
    axes[1, 0].set_ylim(min(cosine) - 0.001, max(cosine) + 0.001)
    figure.suptitle("Controlled reconstruction comparison on GBM108_positive (seed 1)")
    figure.text(
        0.5,
        0.01,
        "In-sample deterministic evaluation. Centre-only has a narrower encoder; this is a model-family comparison, not a parameter-matched ablation.",
        ha="center",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.035, 1, 0.96))
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)
    print(output)


if __name__ == "__main__":
    main()
