"""
Run msiPL on the GBM HDF5 dataset.

Adapted from the original msiPL implementation by Abdelmoula et al.
The model architecture and peak-learning procedure are retained, while
the data loading, output handling, and execution are adapted for the
current GBM HDF5 dataset.

Expected HDF5 structure:
    Data
    mzArray
    xLocation
    yLocation

Expected Data orientation:
    either (m/z, pixels) or (pixels, m/z)

The script automatically determines the required orientation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.mixture import GaussianMixture
from sklearn.metrics import mean_squared_error
from kneed import KneeLocator

# ---------------------------------------------------------------------------
# Make the msiPL repository importable when this script is run from ~/msi
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MSIPL_DIR = PROJECT_ROOT / "baselines" / "msipl"

if str(MSIPL_DIR) not in sys.path:
    sys.path.insert(0, str(MSIPL_DIR))

from Computational_Model import VAE_BN
from LearnPeaks import LearnPeaks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_gbm_h5(path: Path):
    """Load one GBM HDF5 file and orient spectra as (pixels, m/z)."""

    print(f"\nLoading: {path}")

    with h5py.File(path, "r") as f:
        required = ["Data", "mzArray", "xLocation", "yLocation"]

        for key in required:
            if key not in f:
                raise KeyError(f"{path}: missing required dataset '{key}'")

        data = np.asarray(f["Data"], dtype=np.float32)
        mz = np.asarray(f["mzArray"], dtype=np.float32)
        x = np.asarray(f["xLocation"], dtype=np.int32)
        y = np.asarray(f["yLocation"], dtype=np.int32)

    print(f"Raw Data shape: {data.shape}")
    print(f"mzArray shape: {mz.shape}")
    print(f"xLocation shape: {x.shape}")
    print(f"yLocation shape: {y.shape}")

    n_mz = len(mz)
    n_pixels = len(x)

    if len(y) != n_pixels:
        raise ValueError(
            f"{path}: xLocation and yLocation lengths differ "
            f"({len(x)} vs {len(y)})"
        )

    if data.shape == (n_pixels, n_mz):
        spectra = data

    elif data.shape == (n_mz, n_pixels):
        print("Transposing Data to (pixels, m/z)...")
        spectra = data.T

    else:
        raise ValueError(
            f"{path}: cannot orient Data shape {data.shape}. "
            f"Expected ({n_pixels}, {n_mz}) or ({n_mz}, {n_pixels})."
        )

    print(f"Spectra shape: {spectra.shape}")
    print(f"m/z range: {mz.min():.4f} - {mz.max():.4f}")
    print(
        f"Spatial range: "
        f"x={x.min()}..{x.max()}, "
        f"y={y.min()}..{y.max()}"
    )

    return spectra, mz, x, y


def spatial_image(values, x, y):
    """Place per-pixel values into a 2D spatial image."""

    width = int(x.max())
    height = int(y.max())

    image = np.full(
        (height, width),
        np.nan,
        dtype=np.float32,
    )

    for i in range(len(values)):
        xi = int(x[i]) - 1
        yi = int(y[i]) - 1

        if 0 <= xi < width and 0 <= yi < height:
            image[yi, xi] = values[i]

    return image


def save_spatial_image(
    values,
    x,
    y,
    output_path,
    title,
    cmap="viridis",
    colorbar=True,
):
    """Save a spatial MSI image."""

    image = spatial_image(values, x, y)

    plt.figure(figsize=(8, 7))
    plt.imshow(image, cmap=cmap)
    plt.title(title)
    plt.axis("off")

    if colorbar:
        plt.colorbar()

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close()


def tic_normalise(spectra):
    """TIC-normalise spectra."""

    tic = np.sum(spectra, axis=1)

    # Avoid division by zero.
    tic = np.where(tic == 0, 1.0, tic)

    return spectra / tic[:, None]


# ---------------------------------------------------------------------------
# Main msiPL experiment
# ---------------------------------------------------------------------------

def run_msipl(
    input_path: Path,
    output_dir: Path,
    epochs: int,
    batch_size: int,
    latent_dim: int,
    intermediate_dim: int,
    beta: float,
    seed: int,
):
    """Run msiPL on one GBM section."""

    import tensorflow as tf

    np.random.seed(seed)
    tf.random.set_seed(seed)

    output_dir.mkdir(parents=True, exist_ok=True)

    spectra, mz, x, y = load_gbm_h5(input_path)

    n_pixels, n_features = spectra.shape

    print("\n=== DATASET INFORMATION ===")
    print(f"Pixels: {n_pixels}")
    print(f"m/z features: {n_features}")
    print(f"Latent dimension: {latent_dim}")
    print(f"Intermediate dimension: {intermediate_dim}")
    print(f"Epochs: {epochs}")
    print(f"Batch size: {batch_size}")
    print(f"Beta: {beta}")

    # -----------------------------------------------------------------------
    # TIC normalisation
    # -----------------------------------------------------------------------

    print("\n=== TIC NORMALISATION ===")

    spectra = tic_normalise(spectra)

    print("TIC normalisation complete.")

    # -----------------------------------------------------------------------
    # Save basic dataset information
    # -----------------------------------------------------------------------

    dataset_info = {
        "input_file": str(input_path),
        "pixels": int(n_pixels),
        "mz_features": int(n_features),
        "mz_min": float(mz.min()),
        "mz_max": float(mz.max()),
        "x_min": int(x.min()),
        "x_max": int(x.max()),
        "y_min": int(y.min()),
        "y_max": int(y.max()),
        "latent_dim": int(latent_dim),
        "intermediate_dim": int(intermediate_dim),
        "epochs": int(epochs),
        "batch_size": int(batch_size),
        "beta": float(beta),
        "seed": int(seed),
    }

    with open(output_dir / "dataset_info.json", "w") as f:
        json.dump(dataset_info, f, indent=2)

    # -----------------------------------------------------------------------
    # Build msiPL model
    # -----------------------------------------------------------------------

    print("\n=== BUILDING msiPL VAE-BN ===")

    model_builder = VAE_BN(
        nSpecFeatures=n_features,
        intermediate_dim=intermediate_dim,
        latent_dim=latent_dim,
    )

    model, encoder = model_builder.get_architecture()

    # -----------------------------------------------------------------------
    # Train
    # -----------------------------------------------------------------------

    print("\n=== TRAINING ===")

    start_time = time.time()

    history = model.fit(
        spectra,
        epochs=epochs,
        batch_size=batch_size,
        shuffle=True,
        verbose=1,
    )

    training_time = time.time() - start_time

    print(f"\nTraining time: {training_time:.2f} seconds")

    # -----------------------------------------------------------------------
    # Save model weights
    # -----------------------------------------------------------------------

    model.save_weights(
        output_dir / "msipl_weights.h5"
    )

    # -----------------------------------------------------------------------
    # Save training history
    # -----------------------------------------------------------------------

    history_df = pd.DataFrame(history.history)
    history_df.to_csv(
        output_dir / "training_history.csv",
        index=False,
    )

    plt.figure(figsize=(8, 5))
    plt.plot(history.history["loss"])
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.title("msiPL Training Loss")
    plt.tight_layout()
    plt.savefig(
        output_dir / "training_loss.png",
        dpi=200,
    )
    plt.close()

    # -----------------------------------------------------------------------
    # Encode / decode
    # -----------------------------------------------------------------------

    print("\n=== ENCODING DATA ===")

    start_time = time.time()

    encoded_imgs = encoder.predict(
        spectra,
        batch_size=batch_size,
        verbose=1,
    )

    decoded_imgs = model.predict(
        spectra,
        batch_size=batch_size,
        verbose=1,
    )

    inference_time = time.time() - start_time

    latent_mean, latent_log_var, latent_z = encoded_imgs

    print(f"Latent shape: {latent_z.shape}")
    print(f"Reconstruction shape: {decoded_imgs.shape}")

    # -----------------------------------------------------------------------
    # Reconstruction error
    # -----------------------------------------------------------------------

    mse = mean_squared_error(
        spectra,
        decoded_imgs,
    )

    print(f"\nReconstruction MSE: {mse:.8f}")

    # -----------------------------------------------------------------------
    # Save latent representation
    # -----------------------------------------------------------------------

    np.save(
        output_dir / "latent_mean.npy",
        latent_mean,
    )

    np.save(
        output_dir / "latent_log_var.npy",
        latent_log_var,
    )

    np.save(
        output_dir / "latent_z.npy",
        latent_z,
    )

    # -----------------------------------------------------------------------
    # Latent spatial visualisations
    # -----------------------------------------------------------------------

    print("\n=== LATENT VISUALISATIONS ===")

    for i in range(latent_z.shape[1]):
        save_spatial_image(
            latent_z[:, i],
            x,
            y,
            output_dir / f"latent_{i + 1}.png",
            f"m/z latent dimension {i + 1}",
            cmap="viridis",
        )

    # -----------------------------------------------------------------------
    # Mean spectrum comparison
    # -----------------------------------------------------------------------

    mean_original = np.mean(spectra, axis=0)
    mean_reconstructed = np.mean(decoded_imgs, axis=0)

    plt.figure(figsize=(11, 6))

    plt.plot(
        mz,
        mean_original,
        label="Original",
    )

    plt.plot(
        mz,
        mean_reconstructed,
        label="Reconstructed",
    )

    plt.xlabel("m/z")
    plt.ylabel("Intensity")
    plt.title("Mean Spectrum: Original vs Reconstruction")
    plt.legend()

    plt.tight_layout()

    plt.savefig(
        output_dir / "mean_spectrum_comparison.png",
        dpi=200,
    )

    plt.close()

    # -----------------------------------------------------------------------
    # Peak learning
    # -----------------------------------------------------------------------

    print("\n=== PEAK LEARNING ===")

    weights = encoder.get_weights()

    std_spectra = np.std(
        spectra,
        axis=0,
    )

    learned_bins, learned_peaks, mz_bin_index, real_peak_idx = LearnPeaks(
        mz,
        weights,
        std_spectra,
        latent_dim,
        beta,
        mean_original,
    )

    learned_peaks = np.asarray(learned_peaks)

    print(f"Learned peaks: {len(learned_peaks)}")

    peaks_df = pd.DataFrame(
        {
            "mz_peak": learned_peaks,
        }
    )

    peaks_df.to_csv(
        output_dir / "learned_peaks.csv",
        index=False,
    )

    peaks_df.to_excel(
        output_dir / "learned_peaks.xlsx",
        index=False,
    )

    # -----------------------------------------------------------------------
    # GMM + BIC
    # -----------------------------------------------------------------------

    print("\n=== GMM CLUSTERING ===")

    max_clusters = min(
        19,
        max(3, n_pixels // 100),
    )

    n_components = np.arange(
        3,
        max_clusters + 1,
    )

    bic_scores = []
    models = []

    for n in n_components:

        print(f"Fitting GMM with {n} clusters...")

        gmm = GaussianMixture(
            n_components=int(n),
            covariance_type="full",
            random_state=seed,
        )

        gmm.fit(latent_z)

        models.append(gmm)
        bic_scores.append(gmm.bic(latent_z))

    bic_scores = np.asarray(bic_scores)

    knee = KneeLocator(
        n_components,
        bic_scores,
        curve="convex",
        direction="decreasing",
    )

    suggested_clusters = knee.knee

    if suggested_clusters is None:
        suggested_clusters = int(
            n_components[np.argmin(bic_scores)]
        )

        print(
            "Kneedle did not identify a knee; "
            "using minimum BIC."
        )

    suggested_clusters = int(suggested_clusters)

    print(
        f"Suggested number of clusters: "
        f"{suggested_clusters}"
    )

    plt.figure(figsize=(8, 5))

    plt.plot(
        n_components,
        bic_scores,
        marker="o",
    )

    plt.xlabel("Number of clusters")
    plt.ylabel("BIC")
    plt.title(
        f"mSiPL GMM Model Selection "
        f"(suggested K={suggested_clusters})"
    )

    plt.tight_layout()

    plt.savefig(
        output_dir / "gmm_bic.png",
        dpi=200,
    )

    plt.close()

    # -----------------------------------------------------------------------
    # Final GMM
    # -----------------------------------------------------------------------

    gmm = GaussianMixture(
        n_components=suggested_clusters,
        covariance_type="full",
        random_state=seed,
    )

    gmm.fit(latent_z)

    labels = gmm.predict(latent_z) + 1

    np.save(
        output_dir / "gmm_labels.npy",
        labels,
    )

    # Spatial cluster map.
    save_spatial_image(
        labels,
        x,
        y,
        output_dir / "gmm_clusters.png",
        f"mSiPL GMM Clusters (K={suggested_clusters})",
        cmap="tab20",
    )

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------

    results = {
        "dataset": input_path.name,
        "pixels": int(n_pixels),
        "mz_features": int(n_features),
        "latent_dim": int(latent_dim),
        "intermediate_dim": int(intermediate_dim),
        "epochs": int(epochs),
        "batch_size": int(batch_size),
        "beta": float(beta),
        "training_time_seconds": float(training_time),
        "inference_time_seconds": float(inference_time),
        "reconstruction_mse": float(mse),
        "learned_peak_count": int(len(learned_peaks)),
        "suggested_gmm_clusters": int(suggested_clusters),
    }

    with open(output_dir / "results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n========================================")
    print("mSiPL RUN COMPLETE")
    print("========================================")
    print(f"Dataset: {input_path.name}")
    print(f"Training time: {training_time:.2f} s")
    print(f"Inference time: {inference_time:.2f} s")
    print(f"Reconstruction MSE: {mse:.8f}")
    print(f"Learned peaks: {len(learned_peaks)}")
    print(f"GMM clusters: {suggested_clusters}")
    print(f"Results: {output_dir}")
    print("========================================")


def main():
    parser = argparse.ArgumentParser(
        description="Run msiPL on a GBM HDF5 dataset."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to GBM HDF5 file.",
    )

    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for results.",
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=128,
    )

    parser.add_argument(
        "--latent-dim",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--intermediate-dim",
        type=int,
        default=512,
    )

    parser.add_argument(
        "--beta",
        type=float,
        default=2.5,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=0,
    )

    args = parser.parse_args()

    run_msipl(
        input_path=Path(args.input),
        output_dir=Path(args.output_dir),
        epochs=args.epochs,
        batch_size=args.batch_size,
        latent_dim=args.latent_dim,
        intermediate_dim=args.intermediate_dim,
        beta=args.beta,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()