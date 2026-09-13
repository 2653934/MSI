#!/usr/bin/env python3
"""Evaluate three trained Spatial-msiPL neighbourhoods without retraining them.

The script deliberately uses the encoder mean rather than a random latent draw.
Its linear probe holds out rectangular spatial tiles and removes a one-pixel
halo from training, reducing the spatial leakage caused by random pixel splits.
"""

import argparse
import json
import time
from pathlib import Path

import h5py
import numpy as np
import torch
from torch.utils.data import DataLoader

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    adjusted_rand_score,
    balanced_accuracy_score,
    f1_score,
    normalized_mutual_info_score,
    roc_auc_score,
    silhouette_score,
)
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from spatial_msipl.evaluation import morans_i, spatial_tile_folds
from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.preprocessing import H5SpatialContextDataset, MOORE_OFFSETS


VARIANTS = ("uniform_mean", "depthwise", "attention")
DISPLAY_NAMES = {
    "uniform_mean": "Uniform mean",
    "depthwise": "Depthwise",
    "attention": "Attention",
}
NORMAL_COLOUR = "#2A9D8F"
TUMOUR_COLOUR = "#E76F51"
VARIANT_COLOURS = {
    "uniform_mean": "#457B9D",
    "depthwise": "#E9C46A",
    "attention": "#E76F51",
}
UNMEASURED_COLOUR = "#ECECEC"


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--checkpoint-root", required=True, type=Path)
    parser.add_argument("--training-results", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--tile-rows", type=int, default=4)
    parser.add_argument("--tile-columns", type=int, default=4)
    parser.add_argument("--halo", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1)
    return parser.parse_args()


def load_labels(path, expected_pixels):
    """Map MassNet Class_Label 1/2 to analysis labels 0/1."""
    with h5py.File(path, "r") as handle:
        if "Class_Label" not in handle:
            raise KeyError("HDF5 input has no Class_Label dataset")
        raw = np.asarray(handle["Class_Label"], dtype=np.int64).reshape(-1)
    if len(raw) != expected_pixels or set(np.unique(raw).tolist()) != {1, 2}:
        raise ValueError("expected one MassNet label (1 normal, 2 tumour) per pixel")
    return raw - 1


def load_model(checkpoint_path, variant, spectral_dim, device):
    """Reconstruct a model from its saved configuration and weights."""
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    if int(checkpoint.get("completed_epochs", 0)) != 100:
        raise ValueError(f"{checkpoint_path} is not a complete 100-epoch checkpoint")
    configuration = checkpoint["model_configuration"]
    neighbourhood = configuration["neighbourhood"]
    if neighbourhood["name"] != variant or configuration["spectral_dim"] != spectral_dim:
        raise ValueError(f"checkpoint configuration does not match {variant}")
    model = NeighbourhoodSpatialVAE(
        spectral_dim=spectral_dim,
        neighbourhood=variant,
        hidden_dim=configuration["hidden_dim"],
        latent_dim=configuration["latent_dim"],
        attention_dim=neighbourhood.get("attention_dim", 8),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    return model, checkpoint


def encode_dataset(model, dataset, batch_size, device):
    """Return deterministic latent means and compact neighbour-weight summaries."""
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    latent = np.empty((len(dataset), model.vae.latent_dim), dtype=np.float32)
    slot_weights = np.empty((len(dataset), len(MOORE_OFFSETS)), dtype=np.float32)
    entropy = np.empty(len(dataset), dtype=np.float32)
    mean_deviation = np.empty(len(dataset), dtype=np.float32)
    max_deviation = np.empty(len(dataset), dtype=np.float32)
    attention_similarity_spread = np.full(len(dataset), np.nan, dtype=np.float32)
    central_saturation = np.full(len(dataset), np.nan, dtype=np.float32)
    neighbour_saturation = np.full(len(dataset), np.nan, dtype=np.float32)

    with torch.no_grad():
        for batch in loader:
            central = batch["target"].to(device=device, dtype=torch.float32)
            neighbours = batch["neighbours"].to(device=device, dtype=torch.float32)
            mask = batch["neighbour_mask"].to(device=device, dtype=torch.bool)
            indices = batch["index"].numpy()
            mean, _, _, weights = model.encode(central, neighbours, mask)

            counts = mask.sum(dim=1)
            maximum_entropy = counts.clamp_min(2).to(weights.dtype).log()
            uniform = mask.to(weights.dtype) / counts.clamp_min(1).unsqueeze(1)

            # Depthwise has a separate eight-neighbour distribution for every
            # m/z bin. Calculate its entropy before making a compact slot average.
            if weights.ndim == 3:
                safe_weights = weights.clamp_min(torch.finfo(weights.dtype).eps)
                entropy_by_mz = -(weights * safe_weights.log()).sum(dim=1)
                normalized_entropy = torch.where(
                    counts.unsqueeze(1) > 1,
                    entropy_by_mz / maximum_entropy.unsqueeze(1),
                    torch.zeros_like(entropy_by_mz),
                ).mean(dim=1)
                deviations = (weights - uniform.unsqueeze(2)).abs()
                mean_batch_deviation = deviations.sum(dim=(1, 2)) / (
                    counts.clamp_min(1).to(weights.dtype) * weights.shape[2]
                )
                max_batch_deviation = deviations.amax(dim=(1, 2))
                compact_weights = weights.mean(dim=2)
            else:
                safe_weights = weights.clamp_min(torch.finfo(weights.dtype).eps)
                raw_entropy = -(weights * safe_weights.log()).sum(dim=1)
                normalized_entropy = torch.where(
                    counts > 1,
                    raw_entropy / maximum_entropy,
                    torch.zeros_like(raw_entropy),
                )
                deviations = (weights - uniform).abs()
                mean_batch_deviation = deviations.sum(dim=1) / counts.clamp_min(1)
                max_batch_deviation = deviations.amax(dim=1)
                compact_weights = weights

            # Attention diagnostics distinguish genuinely similar neighbours
            # from a saturated projection that merely produces equal logits.
            if hasattr(model.aggregator, "projection"):
                scale = float(model.vae.spectral_dim)
                central_embedding = torch.tanh(model.aggregator.projection(central * scale))
                neighbour_embedding = torch.tanh(
                    model.aggregator.projection(neighbours * scale)
                )
                similarity = torch.sum(
                    neighbour_embedding * central_embedding.unsqueeze(1), dim=2
                ) / np.sqrt(model.aggregator.attention_dim)
                minimum = torch.finfo(similarity.dtype).min
                maximum_similarity = torch.where(mask, similarity, minimum).max(dim=1).values
                minimum_similarity = torch.where(mask, similarity, -minimum).min(dim=1).values
                spread = torch.where(
                    counts > 1,
                    maximum_similarity - minimum_similarity,
                    torch.zeros_like(maximum_similarity),
                )
                central_sat = (central_embedding.abs() >= 0.99).to(weights.dtype).mean(dim=1)
                valid_neighbour_values = counts.clamp_min(1) * model.aggregator.attention_dim
                neighbour_sat = (
                    ((neighbour_embedding.abs() >= 0.99) & mask.unsqueeze(2))
                    .to(weights.dtype)
                    .sum(dim=(1, 2))
                    / valid_neighbour_values
                )
                attention_similarity_spread[indices] = spread.cpu().numpy()
                central_saturation[indices] = central_sat.cpu().numpy()
                neighbour_saturation[indices] = neighbour_sat.cpu().numpy()

            latent[indices] = mean.cpu().numpy()
            slot_weights[indices] = compact_weights.cpu().numpy()
            entropy[indices] = normalized_entropy.cpu().numpy()
            mean_deviation[indices] = mean_batch_deviation.cpu().numpy()
            max_deviation[indices] = max_batch_deviation.cpu().numpy()
    diagnostics = {
        "normalized_entropy": entropy,
        "mean_absolute_deviation_from_uniform": mean_deviation,
        "max_absolute_deviation_from_uniform": max_deviation,
        "attention_similarity_spread": attention_similarity_spread,
        "central_projection_saturation": central_saturation,
        "neighbour_projection_saturation": neighbour_saturation,
    }
    return latent, slot_weights, diagnostics


def spatial_probe(latent, labels, x, y, rows, columns, halo, seed):
    """Out-of-fold linear predictions from spatial tile holdouts."""
    probabilities = np.full(len(labels), np.nan, dtype=np.float64)
    predictions = np.full(len(labels), -1, dtype=np.int64)
    fold_records = []
    folds = spatial_tile_folds(x, y, rows=rows, columns=columns, halo=halo)
    for fold in folds:
        train = fold["train"]
        test = fold["test"]
        if len(np.unique(labels[train])) != 2:
            raise ValueError(f"tile {fold['tile']} training split does not contain both classes")
        classifier = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                class_weight="balanced", max_iter=2000, random_state=seed
            ),
        )
        classifier.fit(latent[train], labels[train])
        probabilities[test] = classifier.predict_proba(latent[test])[:, 1]
        predictions[test] = (probabilities[test] >= 0.5).astype(np.int64)
        fold_records.append(
            {
                "tile": fold["tile"],
                "training_pixels": int(len(train)),
                "test_pixels": int(len(test)),
                "halo_pixels_excluded": int(len(fold["excluded_halo"])),
                "test_normal": int(np.count_nonzero(labels[test] == 0)),
                "test_tumour": int(np.count_nonzero(labels[test] == 1)),
            }
        )
    if np.any(~np.isfinite(probabilities)) or np.any(predictions < 0):
        raise RuntimeError("spatial probe did not predict every pixel")
    metrics = {
        "balanced_accuracy": float(balanced_accuracy_score(labels, predictions)),
        "macro_f1": float(f1_score(labels, predictions, average="macro")),
        "roc_auc": float(roc_auc_score(labels, probabilities)),
        "folds": fold_records,
    }
    return metrics, probabilities, predictions


def spatial_image(values, x, y):
    image = np.full((int(y.max()), int(x.max())), np.nan, dtype=np.float64)
    image[y - 1, x - 1] = values
    return image


def save_latent_maps(latent, x, y, path, variant):
    standardized = StandardScaler().fit_transform(latent)
    limit = max(1.0, float(np.percentile(np.abs(standardized), 98)))
    cmap = matplotlib.colormaps["coolwarm"].copy()
    cmap.set_bad(UNMEASURED_COLOUR)
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    for dimension, ax in enumerate(axes.ravel()):
        if dimension >= latent.shape[1]:
            ax.axis("off")
            continue
        shown = ax.imshow(
            spatial_image(standardized[:, dimension], x, y),
            cmap=cmap,
            vmin=-limit,
            vmax=limit,
            interpolation="nearest",
        )
        ax.set_title(f"Latent dimension {dimension + 1}")
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_aspect("equal")
        fig.colorbar(shown, ax=ax, fraction=0.046, label="Standard deviations")
    fig.suptitle(f"{DISPLAY_NAMES[variant]}: deterministic latent maps", fontsize=16)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_class_plots(latent, labels, path, variant, seed):
    standardized = StandardScaler().fit_transform(latent)
    pca = PCA(n_components=2, random_state=seed).fit_transform(standardized)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    for label, name, colour in (
        (0, "Normal", NORMAL_COLOUR),
        (1, "Tumour", TUMOUR_COLOUR),
    ):
        selected = labels == label
        axes[0].scatter(
            pca[selected, 0], pca[selected, 1], s=13, alpha=0.55,
            color=colour, label=name, edgecolors="none"
        )
    axes[0].set_title("PCA view of the five latent dimensions")
    axes[0].set_xlabel("Principal component 1")
    axes[0].set_ylabel("Principal component 2")
    axes[0].legend()

    positions = []
    values = []
    colours = []
    labels_for_axis = []
    for dimension in range(latent.shape[1]):
        for label, name, colour in (
            (0, "N", NORMAL_COLOUR), (1, "T", TUMOUR_COLOUR)
        ):
            positions.append(len(positions) + 1)
            values.append(standardized[labels == label, dimension])
            colours.append(colour)
            labels_for_axis.append(f"L{dimension + 1}\n{name}")
    boxes = axes[1].boxplot(values, positions=positions, patch_artist=True, showfliers=False)
    for box, colour in zip(boxes["boxes"], colours):
        box.set_facecolor(colour)
        box.set_alpha(0.75)
    axes[1].set_xticks(positions, labels_for_axis)
    axes[1].set_ylabel("Standardized latent value")
    axes[1].set_title("Normal and tumour distributions")
    fig.suptitle(f"{DISPLAY_NAMES[variant]}: latent class structure", fontsize=16)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_neighbourhood_plot(slot_weights, availability, entropy, x, y, path, variant):
    mask = np.asarray(availability, dtype=bool)
    conditional_means = np.divide(
        (slot_weights * mask).sum(axis=0),
        mask.sum(axis=0),
        out=np.zeros(slot_weights.shape[1]),
        where=mask.sum(axis=0) > 0,
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].bar(
        [f"({dx:+d},{dy:+d})" for dx, dy in MOORE_OFFSETS],
        conditional_means,
        color=VARIANT_COLOURS[variant],
    )
    axes[0].tick_params(axis="x", rotation=45)
    axes[0].set_ylabel("Mean weight when neighbour exists")
    axes[0].set_title("Eight neighbour slots")
    cmap = matplotlib.colormaps["viridis"].copy()
    cmap.set_bad(UNMEASURED_COLOUR)
    shown = axes[1].imshow(
        spatial_image(entropy, x, y), cmap=cmap, vmin=0, vmax=1,
        interpolation="nearest"
    )
    axes[1].set_title("Neighbour-weight entropy")
    axes[1].set_xlabel("X")
    axes[1].set_ylabel("Y")
    axes[1].set_aspect("equal")
    fig.colorbar(shown, ax=axes[1], label="0 concentrated, 1 uniform")
    fig.suptitle(f"{DISPLAY_NAMES[variant]}: neighbourhood behaviour", fontsize=16)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return conditional_means


def save_probe_maps(labels, probabilities, predictions, x, y, path, variant):
    """Show the expert mask, held-out predictions, and classification errors."""
    mask_cmap = matplotlib.colors.ListedColormap([NORMAL_COLOUR, TUMOUR_COLOUR])
    mask_cmap.set_bad(UNMEASURED_COLOUR)
    error_cmap = matplotlib.colors.ListedColormap(["#F4F1DE", "#9B2226"])
    error_cmap.set_bad(UNMEASURED_COLOUR)
    probability_cmap = matplotlib.colormaps["RdYlBu_r"].copy()
    probability_cmap.set_bad(UNMEASURED_COLOUR)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    axes[0].imshow(
        spatial_image(labels, x, y), cmap=mask_cmap, vmin=0, vmax=1,
        interpolation="nearest"
    )
    axes[0].set_title("Expert mask")
    shown = axes[1].imshow(
        spatial_image(probabilities, x, y), cmap=probability_cmap,
        vmin=0, vmax=1, interpolation="nearest"
    )
    axes[1].set_title("Held-out tumour probability")
    fig.colorbar(shown, ax=axes[1], fraction=0.046)
    axes[2].imshow(
        spatial_image((predictions != labels).astype(int), x, y),
        cmap=error_cmap, vmin=0, vmax=1, interpolation="nearest"
    )
    axes[2].set_title("Errors (dark red)")
    for ax in axes:
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_aspect("equal")
    fig.suptitle(f"{DISPLAY_NAMES[variant]}: spatially blocked probe", fontsize=16)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def evaluate_variant(args, variant, dataset, labels, device):
    output = args.output / variant
    output.mkdir(parents=True, exist_ok=True)
    checkpoint_path = args.checkpoint_root / variant / "checkpoint.pt"
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"completed checkpoint not found: {checkpoint_path}")

    print(f"Evaluating {variant} from {checkpoint_path}", flush=True)
    started = time.perf_counter()
    model, checkpoint = load_model(checkpoint_path, variant, dataset.n_mz, device)
    latent, slot_weights, weight_diagnostics = encode_dataset(
        model, dataset, args.batch_size, device
    )
    entropy = weight_diagnostics["normalized_entropy"]
    if not np.all(np.isfinite(latent)):
        raise ValueError(f"{variant} produced non-finite latent values")

    standardized = StandardScaler().fit_transform(latent)
    probe, probabilities, predictions = spatial_probe(
        latent, labels, dataset.x, dataset.y,
        args.tile_rows, args.tile_columns, args.halo, args.seed
    )
    gmm_labels = GaussianMixture(
        n_components=2, n_init=20, random_state=args.seed
    ).fit_predict(standardized)
    moran_values = [
        morans_i(standardized[:, dimension], dataset.neighbour_slots)
        for dimension in range(standardized.shape[1])
    ]
    silhouette = float(silhouette_score(standardized, labels))
    slot_means = save_neighbourhood_plot(
        slot_weights, dataset.neighbour_slots >= 0, entropy, dataset.x, dataset.y,
        output / "neighbourhood_weights.png", variant
    )
    save_latent_maps(latent, dataset.x, dataset.y, output / "latent_maps.png", variant)
    save_class_plots(latent, labels, output / "latent_class_structure.png", variant, args.seed)
    save_probe_maps(
        labels, probabilities, predictions, dataset.x, dataset.y,
        output / "spatial_probe_maps.png", variant
    )

    np.save(output / "latent_mean.npy", latent)
    np.save(output / "spatial_probe_tumour_probability.npy", probabilities)
    np.save(output / "spatial_probe_prediction.npy", predictions)
    np.savez(output / "neighbourhood_diagnostics.npz", **weight_diagnostics)
    np.savez(
        output / "coordinates_and_labels.npz",
        x=dataset.x,
        y=dataset.y,
        label=labels,
    )
    neighbourhood_metrics = {
        "offset_order_dx_dy": [list(offset) for offset in MOORE_OFFSETS],
        "mean_weight_when_present": slot_means.tolist(),
        "normalized_entropy": {
            "mean": float(np.mean(entropy)),
            "minimum": float(np.min(entropy)),
            "maximum": float(np.max(entropy)),
        },
        "absolute_deviation_from_uniform": {
            "mean": float(
                np.mean(weight_diagnostics["mean_absolute_deviation_from_uniform"])
            ),
            "maximum": float(
                np.max(weight_diagnostics["max_absolute_deviation_from_uniform"])
            ),
        },
        "entropy_method": (
            "per-pixel, per-m/z before averaging"
            if variant == "depthwise"
            else "per-pixel neighbour distribution"
        ),
    }
    similarity_spread = weight_diagnostics["attention_similarity_spread"]
    if np.any(np.isfinite(similarity_spread)):
        neighbourhood_metrics["attention_diagnostics"] = {
            "similarity_spread_mean": float(np.nanmean(similarity_spread)),
            "similarity_spread_maximum": float(np.nanmax(similarity_spread)),
            "central_projection_saturation_fraction": float(
                np.nanmean(weight_diagnostics["central_projection_saturation"])
            ),
            "neighbour_projection_saturation_fraction": float(
                np.nanmean(weight_diagnostics["neighbour_projection_saturation"])
            ),
            "saturation_threshold_absolute_tanh": 0.99,
        }

    metrics = {
        "evaluation_version": 2,
        "variant": variant,
        "checkpoint": str(checkpoint_path),
        "completed_training_epochs": int(checkpoint["completed_epochs"]),
        "pixels": int(len(dataset)),
        "latent_dimensions": int(latent.shape[1]),
        "class_counts": {
            "normal": int(np.count_nonzero(labels == 0)),
            "tumour": int(np.count_nonzero(labels == 1)),
        },
        "spatial_probe": {
            **probe,
            "tile_grid": [args.tile_rows, args.tile_columns],
            "halo_pixels": args.halo,
            "scope": "transductive: representation learned without labels on the full section",
            "interpretation": "higher is better; out-of-fold predictions",
        },
        "label_silhouette": silhouette,
        "gmm_two_cluster": {
            "adjusted_rand_index": float(adjusted_rand_score(labels, gmm_labels)),
            "normalized_mutual_information": float(
                normalized_mutual_info_score(labels, gmm_labels)
            ),
        },
        "morans_i": {
            "per_latent_dimension": moran_values,
            "mean": float(np.mean(moran_values)),
            "interpretation": "higher means neighbouring pixels have more similar latent values",
        },
        "neighbourhood_weights": neighbourhood_metrics,
        "evaluation_seconds": float(time.perf_counter() - started),
        "status": "complete",
    }
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    del model
    torch.cuda.empty_cache()
    print(json.dumps(metrics, indent=2), flush=True)
    return metrics


def save_comparison(metrics, training_results, output):
    names = [DISPLAY_NAMES[variant] for variant in VARIANTS]
    colours = [VARIANT_COLOURS[variant] for variant in VARIANTS]
    figure, axes = plt.subplots(2, 2, figsize=(14, 10))

    for variant, colour in zip(VARIANTS, colours):
        summary_path = training_results / variant / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        history = summary["history"]
        axes[0, 0].plot(
            [row["epoch"] for row in history],
            [row["total_loss"] for row in history],
            label=DISPLAY_NAMES[variant], color=colour, linewidth=1.8
        )
    axes[0, 0].set_title("Matched 100-epoch training curves")
    axes[0, 0].set_xlabel("Epoch")
    axes[0, 0].set_ylabel("Total loss")
    axes[0, 0].legend()

    x_positions = np.arange(len(VARIANTS))
    width = 0.24
    for offset, (key, label) in enumerate(
        (("balanced_accuracy", "Balanced accuracy"),
         ("macro_f1", "Macro F1"), ("roc_auc", "ROC AUC"))
    ):
        axes[0, 1].bar(
            x_positions + (offset - 1) * width,
            [metrics[v]["spatial_probe"][key] for v in VARIANTS],
            width, label=label
        )
    axes[0, 1].set_xticks(x_positions, names)
    axes[0, 1].set_ylim(0, 1)
    axes[0, 1].set_title("Spatially blocked linear probe")
    axes[0, 1].legend(fontsize=8)

    axes[1, 0].bar(
        x_positions - width / 2,
        [metrics[v]["gmm_two_cluster"]["adjusted_rand_index"] for v in VARIANTS],
        width, label="GMM adjusted Rand index"
    )
    axes[1, 0].bar(
        x_positions + width / 2,
        [metrics[v]["gmm_two_cluster"]["normalized_mutual_information"] for v in VARIANTS],
        width, label="GMM normalized mutual information"
    )
    axes[1, 0].set_xticks(x_positions, names)
    axes[1, 0].set_ylim(0, 1)
    axes[1, 0].set_title("Unsupervised two-cluster agreement")
    axes[1, 0].legend(fontsize=8)

    axes[1, 1].bar(
        x_positions - width / 2,
        [metrics[v]["label_silhouette"] for v in VARIANTS],
        width, label="Label silhouette"
    )
    axes[1, 1].bar(
        x_positions + width / 2,
        [metrics[v]["morans_i"]["mean"] for v in VARIANTS],
        width, label="Mean Moran's I"
    )
    axes[1, 1].set_xticks(x_positions, names)
    axes[1, 1].set_title("Class separation and spatial coherence")
    axes[1, 1].legend(fontsize=8)

    figure.suptitle("Spatial-msiPL neighbourhood comparison", fontsize=17)
    figure.tight_layout()
    figure.savefig(output / "neighbourhood_comparison.png", dpi=220, bbox_inches="tight")
    plt.close(figure)

    comparison = {
        "dataset": "GBM108_positive",
        "design": {
            "latent_representation": "deterministic encoder mean",
            "spatial_probe": "rectangular tile holdout with one-pixel halo",
            "same_training_controls": True,
        },
        "variants": metrics,
        "status": "complete",
    }
    (output / "comparison.json").write_text(
        json.dumps(comparison, indent=2), encoding="utf-8"
    )


def main():
    args = parse_arguments()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; evaluation stopped before loading a model")
    if args.batch_size < 1:
        raise ValueError("batch size must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda")
    dataset = H5SpatialContextDataset(args.input, include_neighbourhood=True)
    try:
        labels = load_labels(args.input, len(dataset))
        all_metrics = {
            variant: evaluate_variant(args, variant, dataset, labels, device)
            for variant in VARIANTS
        }
    finally:
        dataset.close()
    save_comparison(all_metrics, args.training_results, args.output)
    print(f"Evaluation complete: {args.output}", flush=True)


if __name__ == "__main__":
    main()
