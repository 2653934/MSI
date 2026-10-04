#!/usr/bin/env python3
"""Evaluate a real-attention checkpoint with real versus shuffled neighbours.

The model, central spectra, missing-slot masks, and fitted GMM stay fixed.
This is an in-sample input intervention, not a new training or peak evaluation.
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from torch.utils.data import DataLoader

from run_spatial_msipl_gmm_integrated_gradients import load_model, state_sha256
from spatial_msipl.attribution import gmm_posterior
from spatial_msipl.preprocessing import CachedH5SpatialContextDataset, checkpoint_input_spec


def reconstruction_errors(target, reconstruction):
    """Use the same TIC-normalised MSE and scaled CE as reconstruction audits."""
    epsilon = torch.finfo(torch.float32).eps
    probabilities = reconstruction / reconstruction.sum(dim=1, keepdim=True).clamp_min(epsilon)
    probabilities = probabilities.clamp(min=epsilon, max=1.0 - epsilon)
    mse = (target - probabilities).square().mean(dim=1)
    cross_entropy = -(target * probabilities.log()).sum(dim=1) * target.shape[1]
    return mse, cross_entropy


def fixed_gmm_parameters(path, device):
    with np.load(path) as saved:
        names = (
            "scaler_mean", "scaler_scale", "mixture_weights",
            "component_means", "precision_cholesky",
        )
        return {
            name: torch.as_tensor(saved[name], dtype=torch.float32, device=device)
            for name in names
        }


def evaluate_pair(model, real_dataset, shuffled_dataset, gmm, batch_size, device,
                  original_labels, original_latent, original_confidence):
    if len(real_dataset) != len(shuffled_dataset):
        raise ValueError("real and shuffled datasets have different pixel counts")
    if not np.array_equal(real_dataset.neighbour_slots, shuffled_dataset.neighbour_slots):
        raise ValueError("neighbour slot topology or masks changed")
    if not np.array_equal(real_dataset.mz_values, shuffled_dataset.mz_values):
        raise ValueError("m/z axes differ")
    totals = {name: 0.0 for name in (
        "real_mse", "shuffled_mse", "real_scaled_ce", "shuffled_scaled_ce",
        "latent_l2", "posterior_total_variation", "original_component_posterior_drop",
        "label_flips", "baseline_label_mismatches", "changed_context_pixels", "original_latent_max_error",
        "original_confidence_max_error",
    )}
    pixels = 0
    real_loader = DataLoader(real_dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    shuffled_loader = DataLoader(shuffled_dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    with torch.no_grad():
        for real, shuffled in zip(real_loader, shuffled_loader):
            indices = real["index"].numpy()
            if not np.array_equal(indices, shuffled["index"].numpy()):
                raise ValueError("paired batches are not aligned by pixel index")
            if not torch.equal(real["target"], shuffled["target"]):
                raise ValueError("central spectra changed in the intervention")
            if not torch.equal(real["neighbour_mask"], shuffled["neighbour_mask"]):
                raise ValueError("missing-neighbour masks changed in the intervention")
            central = real["target"].to(device=device, dtype=torch.float32)
            mask = real["neighbour_mask"].to(device=device, dtype=torch.bool)
            real_neighbours = real["neighbours"].to(device=device, dtype=torch.float32)
            shuffled_neighbours = shuffled["neighbours"].to(device=device, dtype=torch.float32)
            real_latent = model.encode(central, real_neighbours, mask)[0]
            shuffled_latent = model.encode(central, shuffled_neighbours, mask)[0]
            real_mse, real_ce = reconstruction_errors(central, model.vae.decode(real_latent))
            shuffled_mse, shuffled_ce = reconstruction_errors(
                central, model.vae.decode(shuffled_latent)
            )
            real_posterior = gmm_posterior(real_latent, **gmm)
            shuffled_posterior = gmm_posterior(shuffled_latent, **gmm)
            labels = torch.as_tensor(original_labels[indices], dtype=torch.long, device=device)
            original_real = real_posterior.gather(1, labels[:, None]).squeeze(1)
            original_shuffled = shuffled_posterior.gather(1, labels[:, None]).squeeze(1)
            totals["real_mse"] += float(real_mse.double().sum())
            totals["shuffled_mse"] += float(shuffled_mse.double().sum())
            totals["real_scaled_ce"] += float(real_ce.double().sum())
            totals["shuffled_scaled_ce"] += float(shuffled_ce.double().sum())
            totals["latent_l2"] += float(torch.linalg.vector_norm(
                real_latent - shuffled_latent, dim=1
            ).double().sum())
            totals["posterior_total_variation"] += float((
                0.5 * (real_posterior - shuffled_posterior).abs().sum(dim=1)
            ).double().sum())
            totals["original_component_posterior_drop"] += float((
                original_real - original_shuffled
            ).double().sum())
            totals["label_flips"] += int((shuffled_posterior.argmax(dim=1) != labels).sum())
            totals["baseline_label_mismatches"] += int((real_posterior.argmax(dim=1) != labels).sum())
            totals["changed_context_pixels"] += int((
                (real_neighbours - shuffled_neighbours).abs().sum(dim=(1, 2)) > 0
            ).sum())
            totals["original_latent_max_error"] = max(
                totals["original_latent_max_error"],
                float((real_latent - torch.as_tensor(
                    original_latent[indices], device=device
                )).abs().max()),
            )
            totals["original_confidence_max_error"] = max(
                totals["original_confidence_max_error"],
                float((original_real - torch.as_tensor(
                    original_confidence[indices], device=device
                )).abs().max()),
            )
            pixels += len(indices)
    if pixels != len(real_dataset):
        raise ValueError("paired evaluation did not cover every measured pixel")
    if totals["original_latent_max_error"] > 1e-4 or totals["original_confidence_max_error"] > 1e-4:
        raise ValueError("real-input checkpoint/GMM does not reproduce saved baseline")
    if totals["baseline_label_mismatches"]:
        raise ValueError("fixed GMM does not reproduce saved real-input component labels")
    return {
        "pixels": pixels,
        "real_reconstruction_mse": totals["real_mse"] / pixels,
        "shuffled_reconstruction_mse": totals["shuffled_mse"] / pixels,
        "shuffled_minus_real_mse": (totals["shuffled_mse"] - totals["real_mse"]) / pixels,
        "real_scaled_cross_entropy": totals["real_scaled_ce"] / pixels,
        "shuffled_scaled_cross_entropy": totals["shuffled_scaled_ce"] / pixels,
        "shuffled_minus_real_scaled_cross_entropy": (
            totals["shuffled_scaled_ce"] - totals["real_scaled_ce"]
        ) / pixels,
        "mean_latent_l2_change": totals["latent_l2"] / pixels,
        "mean_gmm_posterior_total_variation": totals["posterior_total_variation"] / pixels,
        "mean_original_component_posterior_drop": (
            totals["original_component_posterior_drop"] / pixels
        ),
        "fixed_gmm_label_flip_fraction": totals["label_flips"] / pixels,
        "changed_context_fraction": totals["changed_context_pixels"] / pixels,
        "baseline_latent_max_absolute_error": totals["original_latent_max_error"],
        "baseline_confidence_max_absolute_error": totals["original_confidence_max_error"],
    }


def save_figure(result, output):
    metrics = result["metrics"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    axes[0].bar(["Real", "Shuffled"], [
        metrics["real_reconstruction_mse"], metrics["shuffled_reconstruction_mse"]
    ], color=["#457B9D", "#E76F51"])
    axes[0].set_title("Reconstruction MSE\n(lower is better)")
    axes[1].bar(["Mean change"], [metrics["mean_gmm_posterior_total_variation"]], color="#6D597A")
    axes[1].set_title("Fixed-GMM posterior\ntotal variation")
    axes[2].bar(["Changed labels"], [metrics["fixed_gmm_label_flip_fraction"]], color="#2A9D8F")
    axes[2].set_title("Fixed-GMM label\nflip fraction")
    for axis in axes:
        axis.set_ylim(bottom=0)
    fig.suptitle(f"{result['section']}: one fixed model, two neighbour inputs")
    fig.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--attribution-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--shuffle-seed", type=int, default=1701)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("batch size must be positive")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; input-swap audit stopped before loading model")
    checkpoint = torch.load(args.checkpoint, map_location="cpu")
    specification = checkpoint_input_spec(checkpoint)
    if specification["context_mode"] != "measured" or specification["window_size"] != 3:
        raise ValueError("audit requires a measured-context 3x3 checkpoint")
    if checkpoint["model_configuration"]["neighbourhood"].get("input_scale_name") != "sqrt_bins":
        raise ValueError("audit requires corrected attention scaling")
    with (args.attribution_dir / "summary.json").open(encoding="utf-8") as handle:
        attribution_summary = json.load(handle)
    if attribution_summary["status"] != "valid":
        raise ValueError("original attribution must be valid")
    # The inherited sample path performs exactly the usual TIC normalization;
    # caching avoids two passes of random HDF5 reads over every neighbour slot.
    real = CachedH5SpatialContextDataset(
        args.input, include_neighbourhood=True, window_size=3, context_mode="measured"
    )
    shuffled = CachedH5SpatialContextDataset(
        args.input, include_neighbourhood=True, window_size=3,
        context_mode="shuffled", context_seed=args.shuffle_seed,
    )
    try:
        device = torch.device("cuda")
        model, _ = load_model(args.checkpoint, real.n_mz, "attention", device, checkpoint)
        checkpoint_sha = state_sha256(model)
        if attribution_summary["model_state_sha256"] != checkpoint_sha:
            raise ValueError("attribution and intervention model weights differ")
        if Path(attribution_summary["dataset"]).name != args.input.name:
            raise ValueError("attribution and intervention sections differ")
        gmm = fixed_gmm_parameters(args.attribution_dir / "gmm_parameters.npz", device)
        with np.load(args.attribution_dir / "coordinates_and_gmm.npz") as saved:
            if not np.array_equal(saved["x"], real.x) or not np.array_equal(saved["y"], real.y):
                raise ValueError("saved GMM pixel coordinates do not match input")
            labels = saved["component"].copy()
            confidence = saved["assigned_posterior"].copy()
        latent = np.load(args.attribution_dir / "latent_mean.npy")
        metrics = evaluate_pair(
            model, real, shuffled, gmm, args.batch_size, device, labels, latent, confidence
        )
        result = {
            "status": "valid",
            "scope": "in-sample same-checkpoint neighbour-input intervention; no retraining, GMM refit or peak evaluation",
            "section": args.input.stem,
            "input": str(args.input),
            "checkpoint": str(args.checkpoint),
            "checkpoint_state_sha256": checkpoint_sha,
            "fixed_gmm": str(args.attribution_dir / "gmm_parameters.npz"),
            "window_size": 3,
            "spectra_io": "cached float32 HDF5 read, original per-sample TIC normalization",
            "shuffle_seed": args.shuffle_seed,
            "shuffle_source_slots_sha256": shuffled.context_permutation_sha256,
            "metrics": metrics,
            "limitations": [
                "The model was trained on real neighbours, so shuffled inputs may be out of distribution.",
                "One fixed seed and section do not establish reproducibility.",
                "No Integrated Gradients or mSCF1 ranking is recomputed here.",
            ],
        }
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        save_figure(result, args.output / "input_swap.png")
        print(json.dumps(result, indent=2), flush=True)
    finally:
        real.close()
        shuffled.close()


if __name__ == "__main__":
    main()
