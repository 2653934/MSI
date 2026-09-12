#!/usr/bin/env python3
"""Compare official GBM imzML inputs with the MassNet HDF5 release."""

import argparse
import json
from pathlib import Path

import h5py
import numpy as np
from pyimzml.ImzMLParser import ImzMLParser


DATASETS = (
    "GBM108_negative",
    "GBM108_positive",
    "GBM12_1",
    "GBM12_2",
    "GBM22_1",
    "GBM22_2",
    "GBM39_1",
    "GBM39_2",
)


def h5_spectrum(data, index, pixels, mz_count):
    if data.shape == (mz_count, pixels):
        return np.asarray(data[:, index]).reshape(-1)
    if data.shape == (pixels, mz_count):
        return np.asarray(data[index, :]).reshape(-1)
    raise ValueError(f"Cannot orient HDF5 Data shape {data.shape}")


def compare_section(dataset, imzml_root, h5_root):
    parser = ImzMLParser(str(imzml_root / f"{dataset}.imzML"))
    imz_coordinates = np.asarray(
        [(x, y) for x, y, _z in parser.coordinates], dtype=np.int32
    )

    official_mask = np.load(imzml_root / "masks" / f"{dataset}_mask.npy")
    reconstructed_mask = np.load(h5_root / "masks" / f"{dataset}_mask.npy")

    with h5py.File(h5_root / f"{dataset}.h5", "r") as handle:
        h5_mz = np.asarray(handle["mzArray"]).reshape(-1)
        h5_labels = np.asarray(handle["Class_Label"]).reshape(-1).astype(np.int64)
        h5_coordinates = np.column_stack(
            (
                np.asarray(handle["xLocation"]).reshape(-1),
                np.asarray(handle["yLocation"]).reshape(-1),
            )
        ).astype(np.int32)
        data = handle["Data"]

        if len(parser.coordinates) != len(h5_coordinates):
            indices = []
        else:
            indices = sorted({0, len(h5_coordinates) // 2, len(h5_coordinates) - 1})

        spectrum_checks = []
        for index in indices:
            imz_mz, imz_intensity = parser.getspectrum(index)
            h5_intensity = h5_spectrum(
                data, index, len(h5_coordinates), len(h5_mz)
            )
            same_length = len(imz_intensity) == len(h5_intensity)
            spectrum_checks.append(
                {
                    "index": index,
                    "mz_exact": bool(np.array_equal(imz_mz, h5_mz)),
                    "mz_allclose": bool(
                        len(imz_mz) == len(h5_mz)
                        and np.allclose(imz_mz, h5_mz, rtol=0, atol=1e-6)
                    ),
                    "intensity_exact": bool(
                        same_length and np.array_equal(imz_intensity, h5_intensity)
                    ),
                    "intensity_allclose": bool(
                        same_length
                        and np.allclose(
                            imz_intensity, h5_intensity, rtol=1e-6, atol=1e-8
                        )
                    ),
                    "maximum_absolute_intensity_difference": (
                        float(np.max(np.abs(imz_intensity - h5_intensity)))
                        if same_length
                        else None
                    ),
                }
            )

    coordinate_order_exact = bool(np.array_equal(imz_coordinates, h5_coordinates))
    coordinate_sets_equal = bool(
        set(map(tuple, imz_coordinates)) == set(map(tuple, h5_coordinates))
    )
    masks_same_shape = official_mask.shape == reconstructed_mask.shape
    masks_exact = bool(
        masks_same_shape and np.array_equal(official_mask, reconstructed_mask)
    )
    rows = h5_coordinates[:, 1] - 1
    columns = h5_coordinates[:, 0] - 1
    official_measured = official_mask[rows, columns]
    reconstructed_measured = reconstructed_mask[rows, columns]
    mapped_h5_labels = h5_labels - 1

    coverage = np.zeros(official_mask.shape, dtype=bool)
    coverage[rows, columns] = True
    difference = official_mask != reconstructed_mask
    official_values, official_counts = np.unique(official_mask, return_counts=True)
    reconstructed_values, reconstructed_counts = np.unique(
        reconstructed_mask, return_counts=True
    )
    mask_combinations = {}
    for official_value in np.unique(official_measured):
        for reconstructed_value in np.unique(reconstructed_measured):
            key = f"official_{official_value}_reconstructed_{reconstructed_value}"
            mask_combinations[key] = int(
                np.count_nonzero(
                    (official_measured == official_value)
                    & (reconstructed_measured == reconstructed_value)
                )
            )

    mask_comparison = {
        "official_dtype": str(official_mask.dtype),
        "reconstructed_dtype": str(reconstructed_mask.dtype),
        "official_value_counts": {
            str(value): int(count)
            for value, count in zip(official_values.tolist(), official_counts.tolist())
        },
        "reconstructed_value_counts": {
            str(value): int(count)
            for value, count in zip(
                reconstructed_values.tolist(), reconstructed_counts.tolist()
            )
        },
        "different_grid_locations": int(np.count_nonzero(difference)),
        "different_measured_locations": int(np.count_nonzero(difference & coverage)),
        "different_unmeasured_locations": int(
            np.count_nonzero(difference & ~coverage)
        ),
        "official_measured_matches_h5_labels": bool(
            np.array_equal(official_measured, mapped_h5_labels)
        ),
        "official_measured_matches_inverted_h5_labels": bool(
            np.array_equal(official_measured, 1 - mapped_h5_labels)
        ),
        "measured_label_combinations": mask_combinations,
    }

    return {
        "dataset": dataset,
        "imzml_spectra": int(len(imz_coordinates)),
        "h5_spectra": int(len(h5_coordinates)),
        "coordinate_order_exact": coordinate_order_exact,
        "coordinate_sets_equal": coordinate_sets_equal,
        "official_mask_shape": list(official_mask.shape),
        "reconstructed_mask_shape": list(reconstructed_mask.shape),
        "masks_exact": masks_exact,
        "mask_comparison": mask_comparison,
        "spectrum_checks": spectrum_checks,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--imzml-root", required=True, type=Path)
    parser.add_argument("--h5-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    results = [
        compare_section(dataset, args.imzml_root, args.h5_root)
        for dataset in DATASETS
    ]
    summary = {
        "comparison": "official GBM imzML package versus MassNet HDF5 release",
        "sections": results,
        "all_coordinate_sets_equal": all(
            item["coordinate_sets_equal"] for item in results
        ),
        "all_masks_exact": all(item["masks_exact"] for item in results),
        "all_official_measured_labels_match_h5": all(
            item["mask_comparison"]["official_measured_matches_h5_labels"]
            for item in results
        ),
        "total_different_measured_mask_locations": sum(
            item["mask_comparison"]["different_measured_locations"]
            for item in results
        ),
        "total_different_unmeasured_mask_locations": sum(
            item["mask_comparison"]["different_unmeasured_locations"]
            for item in results
        ),
        "all_sampled_spectra_close": all(
            check["intensity_allclose"]
            for item in results
            for check in item["spectrum_checks"]
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
