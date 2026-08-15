#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

import h5py
import numpy as np


def describe(name, array):
    array = np.asarray(array)

    finite = np.isfinite(array)

    print(f"\n=== {name} ===")
    print(f"shape: {array.shape}")
    print(f"dtype: {array.dtype}")
    print(f"min: {np.nanmin(array):.10g}")
    print(f"max: {np.nanmax(array):.10g}")
    print(f"mean: {np.nanmean(array):.10g}")
    print(f"std: {np.nanstd(array):.10g}")
    print(f"zeros: {np.sum(array == 0)}")
    print(f"zero fraction: {np.mean(array == 0):.6%}")
    print(f"finite fraction: {np.mean(finite):.6%}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        help="Path to GBM HDF5 dataset",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="JSON output path",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    print("=== msiPL DATA DIAGNOSTIC ===")
    print(f"Input: {input_path}")

    with h5py.File(input_path, "r") as f:
        data = np.asarray(f["Data"], dtype=np.float64)
        mz = np.asarray(f["mzArray"], dtype=np.float64)
        x = np.asarray(f["xLocation"], dtype=np.int32)
        y = np.asarray(f["yLocation"], dtype=np.int32)

    print("\n=== RAW DATA ===")

    describe("Raw Data", data)
    describe("m/z", mz)
    describe("x coordinates", x)
    describe("y coordinates", y)

    # ------------------------------------------------------------
    # Orient to pixels x m/z
    # ------------------------------------------------------------

    if data.shape == (len(x), len(mz)):
        spectra = data

    elif data.shape == (len(mz), len(x)):
        spectra = data.T

    else:
        raise ValueError(
            f"Unexpected Data shape {data.shape}; "
            f"pixels={len(x)}, mz={len(mz)}"
        )

    print("\n=== ORIENTED SPECTRA ===")

    describe(
        "Spectra (pixels x m/z)",
        spectra,
    )

    # ------------------------------------------------------------
    # TIC
    # ------------------------------------------------------------

    tic = np.sum(
        spectra,
        axis=1,
    )

    describe(
        "TIC",
        tic,
    )

    # ------------------------------------------------------------
    # TIC normalization
    # ------------------------------------------------------------

    safe_tic = np.where(
        tic == 0,
        1.0,
        tic,
    )

    normalized = (
        spectra / safe_tic[:, None]
    )

    print("\n=== TIC-NORMALIZED SPECTRA ===")

    describe(
        "TIC-normalized spectra",
        normalized,
    )

    # ------------------------------------------------------------
    # Per-spectrum TIC sanity check
    # ------------------------------------------------------------

    normalized_tic = np.sum(
        normalized,
        axis=1,
    )

    describe(
        "TIC after normalization",
        normalized_tic,
    )

    # ------------------------------------------------------------
    # Save summary
    # ------------------------------------------------------------

    summary = {
        "input": str(input_path),
        "raw_shape": list(data.shape),
        "oriented_shape": list(spectra.shape),
        "mz_count": int(len(mz)),
        "pixel_count": int(len(x)),
        "mz_min": float(mz.min()),
        "mz_max": float(mz.max()),
        "raw_min": float(np.min(spectra)),
        "raw_max": float(np.max(spectra)),
        "raw_mean": float(np.mean(spectra)),
        "raw_std": float(np.std(spectra)),
        "raw_zero_fraction": float(
            np.mean(spectra == 0)
        ),
        "tic_min": float(tic.min()),
        "tic_max": float(tic.max()),
        "tic_mean": float(tic.mean()),
        "tic_std": float(tic.std()),
        "normalized_min": float(
            normalized.min()
        ),
        "normalized_max": float(
            normalized.max()
        ),
        "normalized_mean": float(
            normalized.mean()
        ),
        "normalized_std": float(
            normalized.std()
        ),
        "normalized_tic_min": float(
            normalized_tic.min()
        ),
        "normalized_tic_max": float(
            normalized_tic.max()
        ),
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            summary,
            indent=2,
        )
    )

    print("\n=== DIAGNOSTIC COMPLETE ===")
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()