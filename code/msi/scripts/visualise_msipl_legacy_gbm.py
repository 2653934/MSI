#!/usr/bin/env python
from __future__ import print_function

import argparse
import json
import os
import sys

import h5py
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.mixture import GaussianMixture
from kneed import KneeLocator


PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

MSIPL_DIR = os.path.join(
    PROJECT_ROOT,
    "baselines",
    "msipl"
)

if MSIPL_DIR not in sys.path:
    sys.path.insert(0, MSIPL_DIR)

from Computational_Model_legacy import VAE_BN


# ---------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------

def load_dataset(path):

    with h5py.File(path, "r") as f:
        data = np.asarray(f["Data"])
        mz = np.asarray(f["mzArray"])
        x = np.asarray(f["xLocation"]).astype(int)
        y = np.asarray(f["yLocation"]).astype(int)

    n_mz = len(mz)
    n_pixels = len(x)

    if data.shape == (n_pixels, n_mz):
        spectra = data

    elif data.shape == (n_mz, n_pixels):
        spectra = data.T

    else:
        raise ValueError(
            "Unexpected Data shape {} for {} pixels and {} m/z".format(
                data.shape,
                n_pixels,
                n_mz,
            )
        )

    return spectra, mz, x, y


def tic_normalise(spectra):

    tic = np.sum(spectra, axis=1)

    if np.any(tic == 0):
        raise ValueError("Found spectrum with zero TIC.")

    return spectra / tic[:, None]


# ---------------------------------------------------------------------
# Spatial utilities
# ---------------------------------------------------------------------

def spatial_image(values, x, y):

    width = int(np.max(x))
    height = int(np.max(y))

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


def save_image(
    image,
    path,
    title,
    cmap="viridis",
    colorbar=False,
    vmin=None,
    vmax=None,
):

    plt.figure(figsize=(7, 6))

    plt.imshow(
        image,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
    )

    plt.title(title)
    plt.axis("off")

    if colorbar:
        plt.colorbar()

    plt.tight_layout()

    plt.savefig(
        path,
        dpi=250,
        bbox_inches="tight",
    )

    plt.close()


# ---------------------------------------------------------------------
# Spectral plot
# ---------------------------------------------------------------------

def save_mean_spectrum(
    mz,
    original,
    reconstructed,
    path,
):

    plt.figure(figsize=(11, 5))

    plt.plot(
        mz,
        original,
        label="Measured",
        linewidth=1.2,
    )

    plt.plot(
        mz,
        reconstructed,
        label="Predicted",
        linewidth=1.2,
    )

    plt.xlabel("m/z")
    plt.ylabel("TIC-normalized intensity")
    plt.title("Mean TIC-normalized spectrum")

    plt.legend()

    plt.tight_layout()

    plt.savefig(
        path,
        dpi=250,
        bbox_inches="tight",
    )

    plt.close()


# ---------------------------------------------------------------------
# Training-independent visualisation
# ---------------------------------------------------------------------

def save_latent_maps(
    latent_z,
    x,
    y,
    output_dir,
):

    for i in range(latent_z.shape[1]):

        image = spatial_image(
            latent_z[:, i],
            x,
            y,
        )

        save_image(
            image,
            os.path.join(
                output_dir,
                "latent_{}.png".format(i + 1),
            ),
            "Latent feature Z{}".format(i + 1),
            cmap="hot",
        )


# ---------------------------------------------------------------------
# GMM
# ---------------------------------------------------------------------

def run_gmm(
    latent_z,
    x,
    y,
    output_dir,
    seed,
):

    # -------------------------------------------------------------
    # Published GBM configuration
    # -------------------------------------------------------------

    k_published = 8

    gmm_8 = GaussianMixture(
        n_components=k_published,
        covariance_type="full",
        random_state=seed,
    )

    gmm_8.fit(latent_z)

    labels_8 = gmm_8.predict(latent_z) + 1

    np.save(
        os.path.join(
            output_dir,
            "gmm_k8_labels.npy",
        ),
        labels_8,
    )

    image_8 = spatial_image(
        labels_8,
        x,
        y,
    )

    save_image(
        image_8,
        os.path.join(
            output_dir,
            "gmm_k8.png",
        ),
        "mSiPL GMM clustering (K=8)",
        cmap="tab10",
    )

    # -------------------------------------------------------------
    # BIC / Kneedle additional analysis
    # -------------------------------------------------------------

    n_components = np.arange(3, 20)

    bic_scores = []

    for k in n_components:

        print(
            "BIC: fitting GMM K={}".format(k)
        )

        gmm = GaussianMixture(
            n_components=int(k),
            covariance_type="full",
            random_state=seed,
        )

        gmm.fit(latent_z)

        bic_scores.append(
            gmm.bic(latent_z)
        )

    bic_scores = np.asarray(bic_scores)

    knee = KneeLocator(
        n_components,
        bic_scores,
        curve="convex",
        direction="decreasing",
    )

    k_kneedle = knee.knee

    if k_kneedle is None:
        k_kneedle = int(
            n_components[
                np.argmin(bic_scores)
            ]
        )

    k_kneedle = int(k_kneedle)

    plt.figure(figsize=(8, 5))

    plt.plot(
        n_components,
        bic_scores,
        marker="o",
    )

    plt.axvline(
        8,
        linestyle="--",
        label="Published K=8",
    )

    plt.axvline(
        k_kneedle,
        linestyle=":",
        label="Kneedle K={}".format(
            k_kneedle
        ),
    )

    plt.xlabel("Number of clusters")
    plt.ylabel("BIC")
    plt.title("GMM model selection")

    plt.legend()

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            output_dir,
            "gmm_bic.png",
        ),
        dpi=250,
        bbox_inches="tight",
    )

    plt.close()

    np.save(
        os.path.join(
            output_dir,
            "gmm_bic_scores.npy",
        ),
        bic_scores,
    )

    return {
        "published_k": 8,
        "kneedle_k": k_kneedle,
        "bic_clusters": n_components.tolist(),
        "bic_scores": bic_scores.tolist(),
    }


# ---------------------------------------------------------------------
# Ion maps
# ---------------------------------------------------------------------

def nearest_mz_index(
    mz,
    target,
):

    return int(
        np.argmin(
            np.abs(mz - target)
        )
    )


def save_ion_comparison(
    target_mz,
    mz,
    original,
    reconstructed,
    x,
    y,
    output_dir,
):

    idx = nearest_mz_index(
        mz,
        target_mz,
    )

    actual_mz = float(
        mz[idx]
    )

    original_img = spatial_image(
        original[:, idx],
        x,
        y,
    )

    reconstructed_img = spatial_image(
        reconstructed[:, idx],
        x,
        y,
    )

    all_values = np.concatenate(
        [
            original_img[
                np.isfinite(original_img)
            ],
            reconstructed_img[
                np.isfinite(reconstructed_img)
            ],
        ]
    )

    if len(all_values) > 0:
        vmin = float(np.min(all_values))
        vmax = float(np.max(all_values))
    else:
        vmin = None
        vmax = None

    stem = "mz_{:.4f}".format(
        actual_mz
    )

    save_image(
        original_img,
        os.path.join(
            output_dir,
            stem + "_measured.png",
        ),
        "Measured m/z {:.4f}".format(
            actual_mz
        ),
        cmap="viridis",
        colorbar=True,
        vmin=vmin,
        vmax=vmax,
    )

    save_image(
        reconstructed_img,
        os.path.join(
            output_dir,
            stem + "_predicted.png",
        ),
        "Predicted m/z {:.4f}".format(
            actual_mz
        ),
        cmap="viridis",
        colorbar=True,
        vmin=vmin,
        vmax=vmax,
    )

    # -------------------------------------------------------------
    # Side-by-side comparison
    # -------------------------------------------------------------

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(12, 5),
    )

    im0 = axes[0].imshow(
        original_img,
        cmap="viridis",
        vmin=vmin,
        vmax=vmax,
    )

    axes[0].set_title(
        "Measured {:.4f}".format(
            actual_mz
        )
    )

    axes[0].axis("off")

    axes[1].imshow(
        reconstructed_img,
        cmap="viridis",
        vmin=vmin,
        vmax=vmax,
    )

    axes[1].set_title(
        "Predicted {:.4f}".format(
            actual_mz
        )
    )

    axes[1].axis("off")

    fig.colorbar(
        im0,
        ax=axes,
        fraction=0.025,
        pad=0.04,
    )

    fig.suptitle(
        "Measured vs predicted ion image"
    )

    fig.tight_layout()

    fig.savefig(
        os.path.join(
            output_dir,
            stem + "_comparison.png",
        ),
        dpi=250,
        bbox_inches="tight",
    )

    plt.close(fig)

    return actual_mz


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
    )

    parser.add_argument(
        "--checkpoint",
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        required=True,
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
        "--batch-size",
        type=int,
        default=128,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=1337,
    )

    args = parser.parse_args()

    if not os.path.exists(
        args.output_dir
    ):
        os.makedirs(
            args.output_dir
        )

    print("==========================================")
    print("       LEGACY msiPL VISUALISATION")
    print("==========================================")
    print("Input:", args.input)
    print("Checkpoint:", args.checkpoint)
    print("Output:", args.output_dir)

    # -------------------------------------------------------------
    # Load data
    # -------------------------------------------------------------

    spectra_raw, mz, x, y = load_dataset(
        args.input
    )

    spectra = tic_normalise(
        spectra_raw
    )

    n_features = spectra.shape[1]

    # -------------------------------------------------------------
    # Build model + load checkpoint
    # -------------------------------------------------------------

    print()
    print("Building model...")

    builder = VAE_BN(
        nSpecFeatures=n_features,
        intermediate_dim=args.intermediate_dim,
        latent_dim=args.latent_dim,
    )

    model, encoder = builder.get_architecture()

    print()
    print("Loading weights...")

    model.load_weights(
        args.checkpoint
    )

    # -------------------------------------------------------------
    # Encode/decode
    # -------------------------------------------------------------

    print()
    print("Encoding...")

    encoded = encoder.predict(
        spectra,
        batch_size=args.batch_size,
    )

    latent_mean = encoded[0]
    latent_log_var = encoded[1]
    latent_z = encoded[2]

    print(
        "Latent shape:",
        latent_z.shape,
    )

    print()
    print("Reconstructing...")

    decoded = model.predict(
        spectra,
        batch_size=args.batch_size,
    )

    # -------------------------------------------------------------
    # Save latent arrays
    # -------------------------------------------------------------

    np.save(
        os.path.join(
            args.output_dir,
            "latent_mean.npy",
        ),
        latent_mean,
    )

    np.save(
        os.path.join(
            args.output_dir,
            "latent_log_var.npy",
        ),
        latent_log_var,
    )

    np.save(
        os.path.join(
            args.output_dir,
            "latent_z.npy",
        ),
        latent_z,
    )

    # -------------------------------------------------------------
    # Mean spectra
    # -------------------------------------------------------------

    mean_original = np.mean(
        spectra,
        axis=0,
    )

    mean_decoded = np.mean(
        decoded,
        axis=0,
    )

    decoded_tic = np.sum(
        decoded,
        axis=1,
    )

    decoded_tic_safe = np.where(
        decoded_tic == 0,
        1.0,
        decoded_tic,
    )

    decoded_tic_normalised = (
        decoded /
        decoded_tic_safe[:, None]
    )

    mean_decoded_tic = np.mean(
        decoded_tic_normalised,
        axis=0,
    )

    save_mean_spectrum(
        mz,
        mean_original,
        mean_decoded_tic,
        os.path.join(
            args.output_dir,
            "mean_spectrum.png",
        ),
    )

    # -------------------------------------------------------------
    # Latent visualisation
    # -------------------------------------------------------------

    print()
    print("Saving latent maps...")

    save_latent_maps(
        latent_z,
        x,
        y,
        args.output_dir,
    )

    # -------------------------------------------------------------
    # GMM
    # -------------------------------------------------------------

    print()
    print("Running GMM analysis...")

    gmm_info = run_gmm(
        latent_z,
        x,
        y,
        args.output_dir,
        args.seed,
    )

    # -------------------------------------------------------------
    # Published GBM ion targets
    # -------------------------------------------------------------

    target_mzs = [
        394.1757,
        529.9846,
        558.2953,
        438.2978,
    ]

    resolved_mzs = []

    print()
    print("Saving ion maps...")

    for target in target_mzs:

        actual = save_ion_comparison(
            target,
            mz,
            spectra,
            decoded_tic_normalised,
            x,
            y,
            args.output_dir,
        )

        resolved_mzs.append({
            "requested_mz": target,
            "actual_dataset_mz": actual,
        })

    # -------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------

    summary = {
        "dataset": os.path.basename(
            args.input
        ),
        "pixels": int(
            spectra.shape[0]
        ),
        "mz_features": int(
            spectra.shape[1]
        ),
        "published_gmm_k": 8,
        "kneedle_gmm_k": gmm_info["kneedle_k"],
        "resolved_target_mz": resolved_mzs,
    }

    with open(
        os.path.join(
            args.output_dir,
            "visualisation_summary.json",
        ),
        "w",
    ) as f:
        json.dump(
            summary,
            f,
            indent=2,
        )

    print()
    print("==========================================")
    print("     LEGACY VISUALISATION COMPLETE")
    print("==========================================")


if __name__ == "__main__":
    main()