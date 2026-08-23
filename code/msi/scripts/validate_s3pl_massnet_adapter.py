#!/usr/bin/env python3
"""Validate the S3PL HDF5 adapter against one real MassNet GBM section."""

import argparse
import json
import sys
from pathlib import Path

import h5py
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
S3PL_ROOT = PROJECT_ROOT / "baselines" / "s3pl"
if str(S3PL_ROOT) not in sys.path:
    sys.path.insert(0, str(S3PL_ROOT))

from utils.data_source import H5SpectrumPatchDataset, load_massnet_h5


def main():
    parser = argparse.ArgumentParser(
        description="Validate S3PL spatial patches for one MassNet HDF5 file."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--patch-size", type=int, default=9)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    input_path = args.input.expanduser().resolve()
    table = load_massnet_h5(input_path)
    dataset = H5SpectrumPatchDataset(table, args.patch_size)

    mask_path = input_path.parent / "masks" / f"{input_path.stem}_mask.npy"
    coverage_path = (
        input_path.parent
        / "masks"
        / "audit"
        / f"{input_path.stem}_coverage.npy"
    )
    mask = np.load(mask_path)
    coverage = np.load(coverage_path)

    expected_shape = (int(table.y.max()), int(table.x.max()))
    if mask.shape != expected_shape or coverage.shape != expected_shape:
        raise ValueError(
            f"mask/coverage shape mismatch: expected {expected_shape}, "
            f"found {mask.shape}/{coverage.shape}"
        )
    if not np.all(coverage[table.y - 1, table.x - 1]):
        raise ValueError("coverage omits one or more measured HDF5 coordinates")
    if int(np.count_nonzero(coverage)) != len(table.x):
        raise ValueError("coverage count does not equal the number of spectra")

    with h5py.File(input_path, "r") as handle:
        raw_labels = np.asarray(handle["Class_Label"]).reshape(-1).astype(np.uint8)
    mapped_labels = raw_labels - 1
    if not np.array_equal(mask[table.y - 1, table.x - 1], mapped_labels):
        raise ValueError("mask values do not match MassNet Class_Label values")

    centre = args.patch_size // 2
    checked_indices = sorted({0, len(dataset) // 2, len(dataset) - 1})
    for index in checked_indices:
        patch, returned_index = dataset[index]
        if returned_index != index:
            raise RuntimeError("dataset returned an incorrect centre index")
        expected_patch_shape = (
            1,
            len(table.mz_values),
            args.patch_size,
            args.patch_size,
        )
        if patch.shape != expected_patch_shape:
            raise ValueError(
                f"patch {index} shape {patch.shape}, expected {expected_patch_shape}"
            )
        if not np.array_equal(
            patch[0, :, centre, centre], table.spectra[index]
        ):
            raise ValueError(f"patch {index} centre spectrum does not round-trip")

    patch_bytes = (
        len(table.mz_values)
        * args.patch_size
        * args.patch_size
        * np.dtype(np.float32).itemsize
    )
    summary = {
        "dataset": input_path.stem,
        "input": str(input_path),
        "spectra_shape_pixels_mz": [int(v) for v in table.spectra.shape],
        "mz_range": [float(table.mz_values[0]), float(table.mz_values[-1])],
        "spatial_shape_y_x": [int(v) for v in expected_shape],
        "measured_pixels": int(len(table.x)),
        "grid_pixels": int(mask.size),
        "coverage_percent": float(100.0 * len(table.x) / mask.size),
        "class_counts": {
            "normal": int(np.count_nonzero(mapped_labels == 0)),
            "tumour": int(np.count_nonzero(mapped_labels == 1)),
        },
        "patch_size": args.patch_size,
        "single_patch_bytes": int(patch_bytes),
        "estimated_batch_input_bytes": int(patch_bytes * args.batch_size),
        "checked_patch_indices": checked_indices,
        "status": "valid",
    }

    output_path = args.output
    if output_path:
        output_path = output_path.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)

    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
