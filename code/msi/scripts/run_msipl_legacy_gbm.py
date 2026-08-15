#!/usr/bin/env python

"""
Legacy msiPL reproduction on the GBM dataset.

Purpose:
    Reproduce the original msiPL VAE-BN + LearnPeaks pipeline using
    the legacy software stack as closely as practical.

Environment:
    Python 3.6
    TensorFlow 1.8
    Keras 2.1.5
    NumPy 1.14.2
    SciPy 1.0.0
    h5py 2.7.1
    scikit-learn 0.19.1

This run intentionally focuses on:
    - data loading/orientation
    - TIC normalization
    - VAE-BN training
    - reconstruction
    - peak learning

GMM clustering is omitted from this validation run so that we can
first establish whether the legacy implementation reproduces the
published GBM reconstruction/peak-learning behaviour.
"""

from __future__ import print_function

import argparse
import json
import os
import sys
import time

import h5py
import numpy as np

# ---------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------

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
from LearnPeaks import LearnPeaks


def load_dataset(path):
    """Load GBM HDF5 and orient to (pixels, m/z)."""

    print("=== LOADING DATA ===")
    print("Input:", path)

    with h5py.File(path, "r") as f:

        print("HDF5 keys:", list(f.keys()))

        data = np.asarray(f["Data"])
        mz = np.asarray(f["mzArray"])
        x = np.asarray(f["xLocation"]).astype(int)
        y = np.asarray(f["yLocation"]).astype(int)

    n_mz = len(mz)
    n_pixels = len(x)

    print("Raw Data shape:", data.shape)
    print("mzArray shape:", mz.shape)
    print("xLocation shape:", x.shape)
    print("yLocation shape:", y.shape)

    if len(y) != n_pixels:
        raise ValueError(
            "xLocation/yLocation size mismatch."
        )

    if data.shape == (n_pixels, n_mz):

        spectra = data

    elif data.shape == (n_mz, n_pixels):

        print("Transposing Data to (pixels, m/z)...")
        spectra = data.T

    else:

        raise ValueError(
            "Unexpected Data shape: {}".format(data.shape)
        )

    print("Final spectra shape:", spectra.shape)
    print(
        "m/z range: {:.6f} - {:.6f}".format(
            np.min(mz),
            np.max(mz)
        )
    )

    return spectra, mz, x, y


def tic_normalise(spectra):
    """
    TIC-normalise each spectrum.

    Each spectrum is divided by its total ion current.
    """

    tic = np.sum(
        spectra,
        axis=1
    )

    if np.any(tic == 0):
        raise ValueError(
            "Found spectrum with zero TIC."
        )

    normalised = spectra / tic[:, None]

    return normalised


def describe(name, data):
    """Print basic statistics."""

    data = np.asarray(data)

    print()
    print("=== {} ===".format(name))
    print("shape:", data.shape)
    print("dtype:", data.dtype)
    print("min:", np.min(data))
    print("max:", np.max(data))
    print("mean:", np.mean(data))
    print("std:", np.std(data))


def save_json(path, obj):

    with open(path, "w") as f:
        json.dump(
            obj,
            f,
            indent=2
        )


def main():

    parser = argparse.ArgumentParser(
        description="Legacy msiPL GBM reproduction"
    )

    parser.add_argument(
        "--input",
        required=True
    )

    parser.add_argument(
        "--output-dir",
        required=True
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=100
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=128
    )

    parser.add_argument(
        "--latent-dim",
        type=int,
        default=5
    )

    parser.add_argument(
        "--intermediate-dim",
        type=int,
        default=512
    )

    parser.add_argument(
        "--beta",
        type=float,
        default=2.5
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=1337
    )

    args = parser.parse_args()

    output_dir = os.path.abspath(
        args.output_dir
    )

    os.makedirs(args.output_dir, exist_ok=True)

    # ---------------------------------------------------------------
    # Seeds
    # ---------------------------------------------------------------

    np.random.seed(args.seed)

    try:
        from tensorflow import set_random_seed
        set_random_seed(2)
    except Exception:
        pass

    # ---------------------------------------------------------------
    # Load data
    # ---------------------------------------------------------------

    spectra_raw, mz, x, y = load_dataset(
        args.input
    )

    n_pixels = spectra_raw.shape[0]
    n_features = spectra_raw.shape[1]

    print()
    print("=== DATASET INFORMATION ===")
    print("Pixels:", n_pixels)
    print("m/z features:", n_features)
    print("Latent dimension:", args.latent_dim)
    print("Intermediate dimension:", args.intermediate_dim)
    print("Epochs:", args.epochs)
    print("Batch size:", args.batch_size)
    print("Beta:", args.beta)

    # ---------------------------------------------------------------
    # TIC normalization
    # ---------------------------------------------------------------

    spectra = tic_normalise(
        spectra_raw
    )

    describe(
        "TIC-normalised spectra",
        spectra
    )

    normalized_tic = np.sum(
        spectra,
        axis=1
    )

    print()
    print(
        "Post-normalisation TIC range: {:.12f} - {:.12f}".format(
            np.min(normalized_tic),
            np.max(normalized_tic)
        )
    )

    # ---------------------------------------------------------------
    # Save dataset metadata
    # ---------------------------------------------------------------

    metadata = {
        "input": os.path.abspath(args.input),
        "pixels": int(n_pixels),
        "mz_features": int(n_features),
        "mz_min": float(np.min(mz)),
        "mz_max": float(np.max(mz)),
        "latent_dim": int(args.latent_dim),
        "intermediate_dim": int(args.intermediate_dim),
        "epochs": int(args.epochs),
        "batch_size": int(args.batch_size),
        "beta": float(args.beta),
        "numpy_seed": int(args.seed),
        "tensorflow_seed": 2
    }

    save_json(
        os.path.join(
            output_dir,
            "metadata.json"
        ),
        metadata
    )

    # ---------------------------------------------------------------
    # Build model
    # ---------------------------------------------------------------

    print()
    print("=== BUILDING LEGACY msiPL ===")

    builder = VAE_BN(
        nSpecFeatures=n_features,
        intermediate_dim=args.intermediate_dim,
        latent_dim=args.latent_dim
    )

    model, encoder = builder.get_architecture()

    # ---------------------------------------------------------------
    # Train
    # ---------------------------------------------------------------

    print()
    print("=== TRAINING ===")

    start_time = time.time()

    history = model.fit(
        spectra,
        epochs=args.epochs,
        batch_size=args.batch_size,
        shuffle="batch",
        verbose=1
    )

    training_time = (
        time.time() - start_time
    )

    print()
    print(
        "Training time: {:.2f} seconds".format(
            training_time
        )
    )

    # ---------------------------------------------------------------
    # Save weights into checkpoints, NOT results
    # ---------------------------------------------------------------

    checkpoint_dir = os.path.join(
        PROJECT_ROOT,
        "checkpoints",
        "baselines",
        "msipl",
        "legacy",
        os.path.splitext(
            os.path.basename(args.input)
        )[0]
    )

    if not os.path.exists(checkpoint_dir):
        os.makedirs(checkpoint_dir)

    weight_path = os.path.join(
        checkpoint_dir,
        "msipl_weights.h5"
    )

    model.save_weights(
        weight_path
    )

    print("Weights saved:", weight_path)

    # ---------------------------------------------------------------
    # Save training loss
    # ---------------------------------------------------------------

    loss_values = history.history.get(
        "loss",
        []
    )

    np.savetxt(
        os.path.join(
            output_dir,
            "training_loss.csv"
        ),
        np.asarray(loss_values),
        delimiter=",",
        header="loss",
        comments=""
    )

    # ---------------------------------------------------------------
    # Encode
    # ---------------------------------------------------------------

    print()
    print("=== ENCODING ===")

    start_time = time.time()

    encoded = encoder.predict(
        spectra,
        batch_size=args.batch_size
    )

    encode_time = (
        time.time() - start_time
    )

    latent_mean = encoded[0]
    latent_log_var = encoded[1]
    latent_z = encoded[2]

    print(
        "Latent shape:",
        latent_z.shape
    )

    # ---------------------------------------------------------------
    # Decode
    # ---------------------------------------------------------------

    print()
    print("=== RECONSTRUCTION ===")

    start_time = time.time()

    decoded = model.predict(
        spectra,
        batch_size=args.batch_size
    )

    decode_time = (
        time.time() - start_time
    )

    print(
        "Decoded shape:",
        decoded.shape
    )

    # ---------------------------------------------------------------
    # MSE #1
    #
    # Direct reconstruction MSE, exactly like the original script.
    # ---------------------------------------------------------------

    mse_direct = np.mean(
        np.square(
            spectra - decoded
        )
    )

    # ---------------------------------------------------------------
    # TIC-normalise decoder output
    #
    # The original script separately computes:
    #     dec_TIC = sum(decoded)
    #     decoded / dec_TIC
    #
    # We record the MSE after this operation as a second diagnostic.
    # ---------------------------------------------------------------

    decoded_tic = np.sum(
        decoded,
        axis=1
    )

    decoded_tic_safe = np.where(
        decoded_tic == 0,
        1.0,
        decoded_tic
    )

    decoded_tic_normalised = (
        decoded /
        decoded_tic_safe[:, None]
    )

    mse_tic_normalised = np.mean(
        np.square(
            spectra -
            decoded_tic_normalised
        )
    )

    print()
    print(
        "Direct reconstruction MSE:",
        mse_direct
    )

    print(
        "TIC-normalised reconstruction MSE:",
        mse_tic_normalised
    )

    # ---------------------------------------------------------------
    # Reconstruction statistics
    # ---------------------------------------------------------------

    describe(
        "Decoded output",
        decoded
    )

    describe(
        "TIC-normalised decoded output",
        decoded_tic_normalised
    )

    # ---------------------------------------------------------------
    # Save latent arrays
    # ---------------------------------------------------------------

    np.save(
        os.path.join(
            output_dir,
            "latent_mean.npy"
        ),
        latent_mean
    )

    np.save(
        os.path.join(
            output_dir,
            "latent_log_var.npy"
        ),
        latent_log_var
    )

    np.save(
        os.path.join(
            output_dir,
            "latent_z.npy"
        ),
        latent_z
    )

    # ---------------------------------------------------------------
    # Peak learning
    # ---------------------------------------------------------------

    print()
    print("=== PEAK LEARNING ===")

    weights = encoder.get_weights()

    std_spectra = np.std(
        spectra,
        axis=0
    )

    mean_spectrum = np.mean(
        spectra,
        axis=0
    )

    start_time = time.time()

    learned_bins, learned_peaks, common_peak_ids, real_peak_idx = (
        LearnPeaks(
            mz,
            weights,
            std_spectra,
            args.latent_dim,
            args.beta,
            mean_spectrum
        )
    )

    peak_learning_time = (
        time.time() - start_time
    )

    learned_peaks = np.asarray(
        learned_peaks
    )

    print(
        "Learned m/z peaks:",
        len(learned_peaks)
    )

    print(
        "Peak-learning time: {:.4f} seconds".format(
            peak_learning_time
        )
    )

    # ---------------------------------------------------------------
    # Save peak results
    # ---------------------------------------------------------------

    np.savetxt(
        os.path.join(
            output_dir,
            "learned_peaks.csv"
        ),
        learned_peaks,
        delimiter=",",
        header="mz_peak",
        comments=""
    )

    np.save(
        os.path.join(
            output_dir,
            "learned_mz_bins.npy"
        ),
        learned_bins
    )

    np.save(
        os.path.join(
            output_dir,
            "common_peak_ids.npy"
        ),
        common_peak_ids
    )

    np.save(
        os.path.join(
            output_dir,
            "real_peak_indices.npy"
        ),
        real_peak_idx
    )

    # ---------------------------------------------------------------
    # Final results
    # ---------------------------------------------------------------

    results = {
        "dataset": os.path.basename(args.input),
        "pixels": int(n_pixels),
        "mz_features": int(n_features),
        "latent_dim": int(args.latent_dim),
        "intermediate_dim": int(args.intermediate_dim),
        "epochs": int(args.epochs),
        "batch_size": int(args.batch_size),
        "beta": float(args.beta),
        "training_time_seconds": float(training_time),
        "encoding_time_seconds": float(encode_time),
        "decoding_time_seconds": float(decode_time),
        "peak_learning_time_seconds": float(
            peak_learning_time
        ),
        "direct_reconstruction_mse": float(
            mse_direct
        ),
        "tic_normalised_reconstruction_mse": float(
            mse_tic_normalised
        ),
        "learned_peak_count": int(
            len(learned_peaks)
        )
    }

    save_json(
        os.path.join(
            output_dir,
            "results.json"
        ),
        results
    )

    print()
    print("==========================================")
    print("       LEGACY msiPL S1 COMPLETE")
    print("==========================================")
    print("Dataset:", os.path.basename(args.input))
    print("Training time:", training_time)
    print("Direct MSE:", mse_direct)
    print(
        "TIC-normalised MSE:",
        mse_tic_normalised
    )
    print(
        "Learned peaks:",
        len(learned_peaks)
    )
    print(
        "Results:",
        output_dir
    )
    print(
        "Checkpoint:",
        weight_path
    )
    print("==========================================")


if __name__ == "__main__":
    main()