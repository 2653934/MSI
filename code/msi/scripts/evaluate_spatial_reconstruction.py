#!/usr/bin/env python3
"""Compare deterministic central-spectrum reconstruction across VAE inputs.

This is an in-sample reconstruction control: every model was trained without
labels on the same full tissue section.  The encoder mean is decoded instead
of drawing a random latent sample, so differences reflect the learned models
rather than Monte Carlo noise.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from spatial_msipl.model import CentralOnlyVAE, NeighbourhoodSpatialVAE
from spatial_msipl.preprocessing import H5SpatialContextDataset


MODEL_SPECS = {
    "central_only": {
        "label": "Centre-only VAE",
        "colour": "#264653",
        "checkpoint_group": "reconstruction",
    },
    "uniform_mean": {
        "label": "Uniform mean",
        "colour": "#457B9D",
        "checkpoint_group": "production",
    },
    "depthwise": {
        "label": "Depthwise",
        "colour": "#E9C46A",
        "checkpoint_group": "production",
    },
    "attention": {
        "label": "Original attention",
        "colour": "#E76F51",
        "checkpoint_group": "production",
    },
    "attention_sqrt_bins": {
        "label": "Corrected attention",
        "colour": "#6D597A",
        "checkpoint_group": "production",
    },
}


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--checkpoint-base", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=64)
    return parser.parse_args()


def build_model(name, checkpoint, spectral_dim, device):
    configuration = checkpoint["model_configuration"]
    if int(checkpoint.get("completed_epochs", 0)) != 100:
        raise ValueError(f"{name}: checkpoint is not a complete 100-epoch run")
    if int(configuration["spectral_dim"]) != spectral_dim:
        raise ValueError(f"{name}: checkpoint spectral dimension does not match data")

    if name == "central_only":
        if configuration.get("input_mode") != "central_only":
            raise ValueError("central_only checkpoint has the wrong input mode")
        model = CentralOnlyVAE(
            spectral_dim=spectral_dim,
            hidden_dim=configuration["hidden_dim"],
            latent_dim=configuration["latent_dim"],
        )
    else:
        neighbourhood = configuration["neighbourhood"]
        expected = "attention" if name == "attention_sqrt_bins" else name
        if neighbourhood["name"] != expected:
            raise ValueError(f"{name}: checkpoint neighbourhood does not match")
        model = NeighbourhoodSpatialVAE(
            spectral_dim=spectral_dim,
            neighbourhood=expected,
            hidden_dim=configuration["hidden_dim"],
            latent_dim=configuration["latent_dim"],
            attention_dim=neighbourhood.get("attention_dim", 8),
            attention_input_scale=neighbourhood.get(
                "input_scale_name", "spectral_bins"
            ),
        )

    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    return model


def deterministic_reconstruction_metrics(model, dataset, batch_size, device):
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    totals = {
        "scaled_categorical_cross_entropy": 0.0,
        "mean_squared_error": 0.0,
        "mean_absolute_error": 0.0,
        "cosine_similarity": 0.0,
        "pixels": 0,
    }
    epsilon = torch.finfo(torch.float32).eps

    with torch.no_grad():
        for batch in loader:
            target = batch["target"].to(device=device, dtype=torch.float32)
            neighbours = batch["neighbours"].to(device=device, dtype=torch.float32)
            neighbour_mask = batch["neighbour_mask"].to(
                device=device, dtype=torch.bool
            )
            if isinstance(model, CentralOnlyVAE):
                mean, _ = model.encode(target)
            else:
                mean, _, _, _ = model.encode(target, neighbours, neighbour_mask)
            reconstruction = model.vae.decode(mean)
            probabilities = reconstruction / reconstruction.sum(
                dim=1, keepdim=True
            ).clamp_min(epsilon)
            probabilities = probabilities.clamp(min=epsilon, max=1.0 - epsilon)

            cross_entropy = -(
                target * probabilities.log()
            ).sum(dim=1) * target.shape[1]
            mse = (target - probabilities).pow(2).mean(dim=1)
            mae = (target - probabilities).abs().mean(dim=1)
            cosine = torch.nn.functional.cosine_similarity(
                target, probabilities, dim=1
            )
            count = target.shape[0]
            totals["scaled_categorical_cross_entropy"] += float(cross_entropy.sum())
            totals["mean_squared_error"] += float(mse.sum())
            totals["mean_absolute_error"] += float(mae.sum())
            totals["cosine_similarity"] += float(cosine.sum())
            totals["pixels"] += count

    pixels = totals.pop("pixels")
    return {name: value / pixels for name, value in totals.items()}, pixels


def save_figure(metrics, output):
    names = list(metrics)
    labels = [MODEL_SPECS[name]["label"] for name in names]
    colours = [MODEL_SPECS[name]["colour"] for name in names]
    figure, axes = plt.subplots(1, 3, figsize=(16, 5))
    panels = (
        ("scaled_categorical_cross_entropy", "Scaled categorical cross-entropy", False),
        ("mean_squared_error", "TIC-normalized MSE", False),
        ("cosine_similarity", "Cosine similarity", True),
    )
    for axis, (key, title, higher_is_better) in zip(axes, panels):
        values = [metrics[name][key] for name in names]
        axis.bar(np.arange(len(names)), values, color=colours)
        axis.set_xticks(np.arange(len(names)), labels, rotation=25, ha="right")
        axis.set_title(title)
        axis.set_ylabel("Higher is better" if higher_is_better else "Lower is better")
        axis.ticklabel_format(axis="y", style="sci", scilimits=(-3, 4))
    figure.suptitle("Matched deterministic reconstruction on GBM108_positive")
    figure.tight_layout()
    figure.savefig(output / "reconstruction_comparison.png", dpi=220, bbox_inches="tight")
    plt.close(figure)


def main():
    args = parse_arguments()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; reconstruction evaluation stopped")
    if args.batch_size < 1:
        raise ValueError("batch size must be positive")

    args.output.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda")
    dataset = H5SpatialContextDataset(args.input, include_neighbourhood=True)
    results = {}
    try:
        for name, spec in MODEL_SPECS.items():
            checkpoint_path = (
                args.checkpoint_base
                / spec["checkpoint_group"]
                / "GBM108_positive_seed1"
                / name
                / "checkpoint.pt"
            )
            if not checkpoint_path.is_file():
                raise FileNotFoundError(f"missing checkpoint: {checkpoint_path}")
            checkpoint = torch.load(checkpoint_path, map_location="cpu")
            model = build_model(name, checkpoint, dataset.n_mz, device)
            model_metrics, pixels = deterministic_reconstruction_metrics(
                model, dataset, args.batch_size, device
            )
            results[name] = {
                "label": spec["label"],
                "checkpoint": str(checkpoint_path),
                "parameters": sum(parameter.numel() for parameter in model.parameters()),
                "pixels": pixels,
                **model_metrics,
            }
            del model
            torch.cuda.empty_cache()
            print(json.dumps({name: results[name]}, indent=2), flush=True)
    finally:
        dataset.close()

    save_figure(results, args.output)
    comparison = {
        "dataset": "GBM108_positive",
        "evaluation": "deterministic decoder output from encoder mean",
        "scope": "in-sample reconstruction of the label-free full-section training data",
        "interpretation": {
            "scaled_categorical_cross_entropy": "lower is better; matches the training reconstruction definition",
            "mean_squared_error": "lower is better; calculated after decoder TIC normalization",
            "mean_absolute_error": "lower is better; calculated after decoder TIC normalization",
            "cosine_similarity": "higher is better; calculated after decoder TIC normalization",
        },
        "models": results,
        "status": "complete",
    }
    (args.output / "comparison.json").write_text(
        json.dumps(comparison, indent=2), encoding="utf-8"
    )
    print(f"Reconstruction comparison complete: {args.output}", flush=True)


if __name__ == "__main__":
    main()
