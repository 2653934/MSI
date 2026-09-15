#!/usr/bin/env python3
"""Evaluate matched five-epoch spatial-loss pilots on the development section."""

import argparse
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from evaluate_spatial_msipl_neighbourhoods import (
    encode_dataset,
    load_labels,
    spatial_probe,
)
from evaluate_spatial_reconstruction import deterministic_reconstruction_metrics
from spatial_msipl.evaluation import morans_i
from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.preprocessing import H5SpatialContextDataset


PILOTS = (
    ("uniform_mean_lambda_0p0_spectral_scaled_pilot", "λ = 0", 0.0),
    ("uniform_mean_lambda_0p01_spectral_scaled_pilot", "λ = 0.01", 0.01),
    ("uniform_mean_lambda_0p1_spectral_scaled_pilot", "λ = 0.1", 0.1),
    ("uniform_mean_lambda_1p0_spectral_scaled_pilot", "λ = 1", 1.0),
)
COLOURS = ("#264653", "#457B9D", "#E9C46A", "#E76F51")


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--checkpoint-root", required=True, type=Path)
    parser.add_argument("--training-results", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=1)
    return parser.parse_args()


def load_pilot_model(checkpoint_path, spectral_dim, device):
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    if int(checkpoint.get("completed_epochs", 0)) != 5:
        raise ValueError(f"{checkpoint_path} is not a complete five-epoch pilot")
    configuration = checkpoint["model_configuration"]
    neighbourhood = configuration["neighbourhood"]
    if neighbourhood["name"] != "uniform_mean":
        raise ValueError(f"{checkpoint_path} is not a uniform-mean checkpoint")
    if int(configuration["spectral_dim"]) != spectral_dim:
        raise ValueError(f"{checkpoint_path} has the wrong spectral dimension")
    model = NeighbourhoodSpatialVAE(
        spectral_dim=spectral_dim,
        neighbourhood="uniform_mean",
        hidden_dim=configuration["hidden_dim"],
        latent_dim=configuration["latent_dim"],
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    return model, checkpoint


def full_neighbour_latent_mse(latent, neighbour_slots):
    centres = np.repeat(np.arange(len(latent)), neighbour_slots.shape[1])
    neighbours = neighbour_slots.reshape(-1)
    keep = (neighbours >= 0) & (centres < neighbours)
    centres = centres[keep]
    neighbours = neighbours[keep]
    if len(centres) == 0:
        raise ValueError("dataset contains no measured neighbouring pairs")
    differences = latent[centres] - latent[neighbours]
    return float(np.mean(np.square(differences))), int(len(centres))


def evaluate_pilot(args, folder, label, expected_lambda, dataset, labels, device):
    checkpoint_path = args.checkpoint_root / folder / "checkpoint.pt"
    summary_path = args.training_results / folder / "summary.json"
    if not checkpoint_path.is_file() or not summary_path.is_file():
        raise FileNotFoundError(f"missing pilot artifacts for {folder}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    controls = summary["controls"]
    if float(controls["spatial_lambda"]) != expected_lambda:
        raise ValueError(f"{folder} has an unexpected lambda")
    if controls["spatial_loss_scale_name"] != "spectral_bins":
        raise ValueError(f"{folder} did not use spectral-bin scaling")

    started = time.perf_counter()
    model, checkpoint = load_pilot_model(checkpoint_path, dataset.n_mz, device)
    latent, _, _ = encode_dataset(model, dataset, args.batch_size, device)
    reconstruction, pixels = deterministic_reconstruction_metrics(
        model, dataset, args.batch_size, device
    )
    standardized = StandardScaler().fit_transform(latent)
    probe, _, _ = spatial_probe(
        latent,
        labels,
        dataset.x,
        dataset.y,
        rows=4,
        columns=4,
        halo=1,
        seed=args.seed,
    )
    gmm = GaussianMixture(n_components=2, n_init=20, random_state=args.seed)
    gmm_labels = gmm.fit_predict(standardized)
    neighbour_mse, neighbour_pairs = full_neighbour_latent_mse(
        latent, dataset.neighbour_slots
    )
    moran_values = [
        morans_i(standardized[:, dimension], dataset.neighbour_slots)
        for dimension in range(standardized.shape[1])
    ]
    final_epoch = summary["history"][-1]
    result = {
        "label": label,
        "lambda": expected_lambda,
        "spatial_loss_scale": float(controls["spatial_loss_scale"]),
        "checkpoint": str(checkpoint_path),
        "pixels": pixels,
        "training": {
            "final_reconstruction_loss": final_epoch["reconstruction_loss"],
            "final_kl_loss": final_epoch["kl_loss"],
            "final_raw_batch_spatial_loss": final_epoch["spatial_loss"],
            "final_weighted_spatial_loss": final_epoch["weighted_spatial_loss"],
        },
        "deterministic_reconstruction": reconstruction,
        "full_neighbour_latent_mse": neighbour_mse,
        "full_neighbour_pairs": neighbour_pairs,
        "spatial_probe": probe,
        "label_silhouette": float(silhouette_score(standardized, labels)),
        "gmm_two_cluster": {
            "adjusted_rand_index": float(adjusted_rand_score(labels, gmm_labels)),
            "normalized_mutual_information": float(
                normalized_mutual_info_score(labels, gmm_labels)
            ),
        },
        "morans_i": {
            "per_latent_dimension": moran_values,
            "mean": float(np.mean(moran_values)),
        },
        "evaluation_seconds": float(time.perf_counter() - started),
        "completed_epochs": int(checkpoint["completed_epochs"]),
    }
    del model
    torch.cuda.empty_cache()
    print(json.dumps({folder: result}, indent=2), flush=True)
    return result


def save_comparison(results, output):
    folders = [folder for folder, _, _ in PILOTS]
    labels = [results[folder]["label"] for folder in folders]
    x = np.arange(len(folders))
    baseline = results[folders[0]]
    mse_excess = [
        100.0
        * (
            results[folder]["deterministic_reconstruction"]["mean_squared_error"]
            - baseline["deterministic_reconstruction"]["mean_squared_error"]
        )
        / baseline["deterministic_reconstruction"]["mean_squared_error"]
        for folder in folders
    ]
    panels = (
        (mse_excess, "Deterministic reconstruction MSE", "% above λ = 0 (lower is better)"),
        (
            [results[folder]["full_neighbour_latent_mse"] for folder in folders],
            "Full-section adjacent latent MSE",
            "Lower is smoother",
        ),
        (
            [results[folder]["spatial_probe"]["balanced_accuracy"] for folder in folders],
            "Spatially blocked probe",
            "Balanced accuracy",
        ),
        (
            [results[folder]["gmm_two_cluster"]["adjusted_rand_index"] for folder in folders],
            "Unsupervised GMM agreement",
            "Adjusted Rand index",
        ),
        (
            [results[folder]["morans_i"]["mean"] for folder in folders],
            "Latent spatial autocorrelation",
            "Mean Moran's I",
        ),
        (
            [results[folder]["label_silhouette"] for folder in folders],
            "Label separation",
            "Silhouette score",
        ),
    )
    figure, axes = plt.subplots(2, 3, figsize=(17, 10))
    for axis, (values, title, ylabel) in zip(axes.flat, panels):
        bars = axis.bar(x, values, color=COLOURS)
        axis.set_xticks(x, labels)
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.grid(axis="y", alpha=0.2)
        axis.bar_label(bars, fmt="%.4g", padding=3, fontsize=8)
    figure.suptitle("Five-epoch spectral-scaled spatial-loss pilots")
    figure.text(
        0.5,
        0.01,
        "Development-only evaluation on GBM108_positive, seed 1; select lambda only after considering reconstruction and representation together.",
        ha="center",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.035, 1, 0.96))
    figure.savefig(output / "spatial_loss_pilot_comparison.png", dpi=220, bbox_inches="tight")
    plt.close(figure)


def main():
    args = parse_arguments()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; pilot evaluation stopped")
    args.output.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda")
    dataset = H5SpatialContextDataset(args.input, include_neighbourhood=True)
    try:
        labels = load_labels(args.input, len(dataset))
        results = {
            folder: evaluate_pilot(
                args, folder, label, expected_lambda, dataset, labels, device
            )
            for folder, label, expected_lambda in PILOTS
        }
    finally:
        dataset.close()
    save_comparison(results, args.output)
    comparison = {
        "dataset": "GBM108_positive",
        "scope": "five-epoch development-only spatial-loss scale selection",
        "spatial_loss_scale": "number of spectral bins",
        "pilots": results,
        "status": "complete",
    }
    (args.output / "comparison.json").write_text(
        json.dumps(comparison, indent=2), encoding="utf-8"
    )
    print(f"Spatial-loss pilot evaluation complete: {args.output}", flush=True)


if __name__ == "__main__":
    main()
