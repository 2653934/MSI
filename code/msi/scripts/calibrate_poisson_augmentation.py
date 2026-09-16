#!/usr/bin/env python3
"""Measure candidate Poisson augmentation strengths without training a model."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as functional

from spatial_msipl.preprocessing import H5SpatialContextDataset
from spatial_msipl.training import (
    poisson_augment_tic_normalized,
    set_random_seed,
)


def summarize(values):
    values = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(values.mean()),
        "standard_deviation": float(values.std()),
        "minimum": float(values.min()),
        "median": float(np.median(values)),
        "maximum": float(values.max()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--effective-counts",
        nargs="+",
        type=float,
        default=(1e4, 1e5, 1e6),
    )
    parser.add_argument("--samples", type=int, default=32)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    if args.samples < 2:
        raise ValueError("samples must be at least 2")
    if any(value <= 0 for value in args.effective_counts):
        raise ValueError("effective counts must be positive")

    dataset = H5SpatialContextDataset(args.input)
    try:
        generator = np.random.default_rng(args.seed)
        indices = sorted(
            generator.choice(
                len(dataset), size=min(args.samples, len(dataset)), replace=False
            ).tolist()
        )
        clean = torch.stack(
            [torch.as_tensor(dataset[index]["target"]) for index in indices]
        ).to(dtype=torch.float32)
    finally:
        dataset.close()

    results = []
    for offset, effective_count in enumerate(args.effective_counts):
        set_random_seed(args.seed + offset)
        poisson_generator = torch.Generator().manual_seed(
            args.seed + 1_000_003 + offset
        )
        noisy = poisson_augment_tic_normalized(
            clean, effective_count, generator=poisson_generator
        )
        l1 = (noisy - clean).abs().sum(dim=1)
        cosine = functional.cosine_similarity(noisy, clean, dim=1, eps=1e-12)
        clean_nonzero = (clean > 0).sum(dim=1).clamp_min(1)
        retained = ((noisy > 0) & (clean > 0)).sum(dim=1) / clean_nonzero
        results.append(
            {
                "effective_count": float(effective_count),
                "central_spectral_l1": summarize(l1.numpy()),
                "central_cosine_similarity": summarize(cosine.numpy()),
                "fraction_clean_nonzero_bins_retained": summarize(
                    retained.numpy()
                ),
                "mean_sampled_tic": float(noisy.sum(dim=1).mean()),
            }
        )

    summary = {
        "purpose": "Poisson severity calibration before model training",
        "input": str(args.input),
        "formula": (
            "Poisson(TIC-normalized spectrum * effective_count), followed by "
            "TIC renormalization"
        ),
        "training_policy": (
            "apply independently to central and measured-neighbour encoder "
            "inputs only; retain the clean central spectrum as decoder target"
        ),
        "seed": args.seed,
        "sample_indices": indices,
        "sample_count": len(indices),
        "spectral_bins": int(clean.shape[1]),
        "candidates": results,
        "status": "complete",
    }

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "calibration.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    counts = np.asarray([row["effective_count"] for row in results])
    figure, axes = plt.subplots(1, 3, figsize=(12, 3.6))
    panels = (
        ("central_spectral_l1", "mean", "Spectral L1 distance", False),
        ("central_cosine_similarity", "mean", "Cosine similarity", True),
        (
            "fraction_clean_nonzero_bins_retained",
            "mean",
            "Non-zero bins retained",
            True,
        ),
    )
    for axis, (metric, statistic, title, higher_is_better) in zip(axes, panels):
        values = [row[metric][statistic] for row in results]
        axis.plot(counts, values, marker="o", color="#2f5d7c", linewidth=2)
        axis.set_xscale("log")
        axis.set_xlabel("Effective ion count N")
        axis.set_title(title)
        axis.grid(alpha=0.25)
        if higher_is_better:
            axis.set_ylim(0, 1.02)
    figure.suptitle(
        f"Poisson augmentation severity ({len(indices)} fixed spectra)"
    )
    figure.tight_layout()
    figure.savefig(args.output / "calibration.png", dpi=180, bbox_inches="tight")
    plt.close(figure)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
