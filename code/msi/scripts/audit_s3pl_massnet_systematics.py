#!/usr/bin/env python3
"""Check the three assumptions behind our MassNet S3PL adapter."""

import argparse
import json
import sys
from pathlib import Path

import h5py
import numpy as np


# Reuse the same loader and normalization function used by an S3PL run.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
S3PL_ROOT = PROJECT_ROOT / "baselines" / "s3pl"
sys.path.insert(0, str(S3PL_ROOT))

from utils.data_source import H5SpectrumPatchDataset, load_massnet_h5
from utils.helpers import tic_norm_spectra


def expected_neighbours(x_coordinates, y_coordinates, patch_size):
    """Independently find each pixel's neighbours from its (x, y) coordinate."""
    coordinate_to_spectrum = {
        (int(x), int(y)): index
        for index, (x, y) in enumerate(zip(x_coordinates, y_coordinates))
    }
    radius = patch_size // 2
    expected = []

    for x, y in zip(x_coordinates, y_coordinates):
        patch = []
        for y_offset in range(-radius, radius + 1):
            for x_offset in range(-radius, radius + 1):
                neighbour = (int(x) + x_offset, int(y) + y_offset)
                patch.append(coordinate_to_spectrum.get(neighbour, -1))
        expected.append(patch)

    return np.asarray(expected, dtype=np.int32)


def compare_normalizations(raw_patch, patch_size):
    """Compare the reference-code calculation with the TIC calculation in the paper."""
    centre = patch_size // 2

    # Current reference code: maximum over axis 2. For [channel, mz, y, x],
    # that is a maximum over y, not over the spectrum.
    reference_patch = tic_norm_spectra(raw_patch.copy())

    # TIC normalization: divide each spectrum by its sum over the mz axis (axis 1).
    spectrum_totals = raw_patch.sum(axis=1, keepdims=True, dtype=np.float64)
    spectrum_totals[spectrum_totals == 0] = 1
    tic_patch = raw_patch / spectrum_totals

    reference_centre = reference_patch[0, :, centre, centre]
    tic_centre = tic_patch[0, :, centre, centre]
    return {
        "reference_centre_sum": float(reference_centre.sum(dtype=np.float64)),
        "paper_tic_centre_sum": float(tic_centre.sum(dtype=np.float64)),
        "maximum_absolute_difference": float(
            np.max(np.abs(reference_centre - tic_centre))
        ),
        "equivalent": bool(np.allclose(reference_centre, tic_centre)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--patch-size", type=int, default=3)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()

    # Load spectra as [pixel, mz] and build the same patches used during training.
    table = load_massnet_h5(input_path)
    patches = H5SpectrumPatchDataset(table, args.patch_size)

    # Question 1: does mask[y - 1, x - 1] contain that spectrum's class label?
    with h5py.File(input_path, "r") as handle:
        h5_labels = np.asarray(handle["Class_Label"]).reshape(-1).astype(np.uint8)
    mask_path = input_path.parent / "masks" / f"{input_path.stem}_mask.npy"
    mask = np.load(mask_path)
    mask_labels = mask[table.y - 1, table.x - 1]
    mask_correct = np.array_equal(mask_labels, h5_labels - 1)

    # Question 2: does the adapter put the correct spectra in every p x p patch?
    expected = expected_neighbours(table.x, table.y, args.patch_size)
    neighbour_mismatches = int(np.count_nonzero(patches.patch_indices != expected))
    centre_position = (args.patch_size**2) // 2
    centres_correct = np.array_equal(
        patches.patch_indices[:, centre_position],
        np.arange(len(table.x)),
    )
    valid_neighbours = np.count_nonzero(patches.patch_indices >= 0, axis=1)

    # Question 3: does the current preprocessing equal paper-described TIC?
    # A central, measured spectrum is sufficient to prove whether the operations differ.
    sample_index = len(patches) // 2
    raw_patch, _ = patches[sample_index]
    normalization = compare_normalizations(raw_patch, args.patch_size)

    result = {
        "dataset": input_path.stem,
        "spectra_shape_pixels_mz": [int(value) for value in table.spectra.shape],
        "spatial_shape_y_x": [int(mask.shape[0]), int(mask.shape[1])],
        "patch_size": args.patch_size,
        "mask_mapping": {
            "rule": "mask[y - 1, x - 1] == Class_Label - 1",
            "all_pixels_correct": mask_correct,
        },
        "neighbour_mapping": {
            "entries_checked": int(patches.patch_indices.size),
            "mismatches": neighbour_mismatches,
            "all_centres_correct": centres_correct,
            "valid_neighbours_including_centre": {
                "minimum": int(valid_neighbours.min()),
                "mean": float(valid_neighbours.mean()),
                "maximum": int(valid_neighbours.max()),
            },
        },
        "normalization": {
            "tensor_order": "[channel, mz, y, x]",
            "reference_code": "divide by max over axis 2 (y)",
            "paper": "divide each spectrum by its total over mz",
            "sample_spectrum_index": sample_index,
            **normalization,
        },
        "conclusion": {
            "spatial_adapter_passes": bool(
                mask_correct and neighbour_mismatches == 0 and centres_correct
            ),
            "reference_preprocessing_matches_paper": normalization["equivalent"],
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)

    if not result["conclusion"]["spatial_adapter_passes"]:
        raise SystemExit("The spatial adapter failed its audit")


if __name__ == "__main__":
    main()
