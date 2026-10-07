#!/usr/bin/env python3
"""Independently check HDF5 spectra, coordinates, masks and measured neighbours.

Expert labels are read for alignment and the saved visual audit only. They are
never supplied to a model, clusterer or peak ranking by this program.
"""

import argparse
import json
from pathlib import Path

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from spatial_msipl.preprocessing import H5SpatialContextDataset


def reference_slots(x, y, width):
    """Build a coordinate lookup independently of the production slot builder."""
    if width not in (3, 5):
        raise ValueError("audit supports the evaluated 3x3 and 5x5 windows")
    coordinates = [(int(a), int(b)) for a, b in zip(x, y)]
    lookup = {point: index for index, point in enumerate(coordinates)}
    if len(lookup) != len(coordinates):
        raise ValueError("duplicate measured coordinates")
    radius = width // 2
    offsets = [(dx, dy) for dy in range(-radius, radius + 1)
               for dx in range(-radius, radius + 1) if (dx, dy) != (0, 0)]
    slots = np.full((len(x), len(offsets)), -1, dtype=np.int64)
    for index, (cx, cy) in enumerate(coordinates):
        for position, (dx, dy) in enumerate(offsets):
            slots[index, position] = lookup.get((cx + dx, cy + dy), -1)
    return slots


def read_raw(data, indices, pixels_first):
    """Read selected spectra in HDF5 row order without using the model loader."""
    return np.stack([
        np.asarray(data[int(i), :] if pixels_first else data[:, int(i)], dtype=np.float32)
        for i in indices
    ])


def spotcheck_indices(x, y):
    """Include file endpoints, centre, and spatial extrema for a visual check."""
    indices = [0, len(x) // 2, len(x) - 1,
               int(np.argmin(x + y)), int(np.argmax(x + y)),
               int(np.argmin(x)), int(np.argmax(x)),
               int(np.argmin(y)), int(np.argmax(y))]
    return list(dict.fromkeys(indices))


def check_source_imzml(path, x, y, mz, data, pixels_first, indices):
    from pyimzml.ImzMLParser import ImzMLParser

    parser = ImzMLParser(str(path))
    if len(parser.coordinates) != len(x):
        raise AssertionError("imzML/HDF5 pixel counts differ")
    source_xy = np.asarray([(int(point[0]), int(point[1]))
                            for point in parser.coordinates], dtype=np.int64)
    if not np.array_equal(source_xy[:, 0], x) or not np.array_equal(source_xy[:, 1], y):
        raise AssertionError("imzML/HDF5 coordinate order differs")
    for index in indices:
        source_mz, source_intensity = parser.getspectrum(index)
        if not np.array_equal(source_mz, mz):
            raise AssertionError(f"imzML m/z axis differs at pixel {index}")
        h5_intensity = read_raw(data, [index], pixels_first)[0]
        if not np.array_equal(np.asarray(source_intensity, dtype=np.float32), h5_intensity):
            raise AssertionError(f"imzML/HDF5 intensities differ at pixel {index}")
    return {"source_imzml": str(path), "checked_spectra": indices,
            "coordinates_in_original_order": True, "sampled_intensities_exact": True}


def render_spotcheck(output, mz, mask, coverage, x, y, index, slots, raw, normalized):
    figure, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    axes[0].imshow(mask, origin="upper", interpolation="nearest", cmap="viridis")
    axes[0].scatter([x[index] - 1], [y[index] - 1], s=80, c="white", marker="x", label="centre")
    valid = slots[index][slots[index] >= 0]
    axes[0].scatter(x[valid] - 1, y[valid] - 1, s=30, facecolors="none",
                    edgecolors="red", linewidths=1.2, label="3x3 neighbours")
    axes[0].set_title("Mask with audited centre/neighbours")
    axes[0].legend(loc="best", fontsize=8)
    axes[1].imshow(coverage, origin="upper", interpolation="nearest", cmap="gray_r", vmin=0, vmax=1)
    axes[1].set_title("Measured-pixel coverage")
    axes[2].plot(mz, raw, label="raw", color="tab:blue", alpha=0.8)
    normalized_axis = axes[2].twinx()
    normalized_axis.plot(mz, normalized, label="TIC-normalized", color="tab:orange", alpha=0.8)
    axes[2].set_ylabel("raw intensity", color="tab:blue")
    normalized_axis.set_ylabel("TIC-normalized intensity", color="tab:orange")
    axes[2].set_title(f"Pixel {index}: original m/z axis")
    axes[2].set_xlabel("m/z")
    axes[2].legend(loc="upper left", fontsize=8)
    normalized_axis.legend(loc="upper right", fontsize=8)
    figure.tight_layout()
    figure.savefig(output, dpi=180)
    plt.close(figure)


def audit(h5_path, mask_path, output, collection, source_imzml=None):
    if collection not in ("cac", "gbm"):
        raise ValueError("collection must be cac or gbm")
    h5_path = h5_path.resolve(strict=True)
    mask_path = mask_path.resolve(strict=True)
    mask = np.load(mask_path, allow_pickle=False)
    if mask.ndim != 2:
        raise ValueError("mask must be a two-dimensional y-by-x array")
    with h5py.File(h5_path, "r") as handle:
        for name in ("Data", "mzArray", "xLocation", "yLocation", "Class_Label"):
            if name not in handle:
                raise KeyError(f"missing HDF5 dataset: {name}")
        data = handle["Data"]
        mz = np.asarray(handle["mzArray"]).reshape(-1)
        x = np.asarray(handle["xLocation"]).reshape(-1)
        y = np.asarray(handle["yLocation"]).reshape(-1)
        labels = np.asarray(handle["Class_Label"]).reshape(-1)
        if not (len(x) == len(y) == len(labels) > 0):
            raise ValueError("pixel coordinate and label lengths differ or are empty")
        if len(mz) < 2:
            raise ValueError("m/z axis needs at least two values")
        if any(not np.issubdtype(values.dtype, np.number) or
               not np.all(np.isfinite(values)) for values in (mz, x, y, labels)):
            raise ValueError("metadata must be finite and numeric")
        if np.any(np.diff(mz) <= 0):
            raise ValueError("m/z axis is not strictly increasing")
        if not np.all(x == np.rint(x)) or not np.all(y == np.rint(y)):
            raise ValueError("coordinates must be integers")
        x, y = x.astype(np.int64), y.astype(np.int64)
        if np.any(x < 1) or np.any(y < 1) or np.any(x > mask.shape[1]) or np.any(y > mask.shape[0]):
            raise ValueError("measured coordinates fall outside the mask")
        if len(set(zip(x.tolist(), y.tolist()))) != len(x):
            raise ValueError("duplicate measured coordinates")
        pixels_first = data.shape == (len(x), len(mz))
        mz_first = data.shape == (len(mz), len(x))
        if pixels_first == mz_first:
            raise ValueError(f"HDF5 orientation is invalid or ambiguous: {data.shape}")
        if collection == "gbm":
            if not set(np.unique(labels).tolist()) <= {1, 2}:
                raise ValueError("GBM HDF5 labels are not raw classes 1/2")
            expected_mask = labels.astype(np.int64) - 1
        else:
            if not set(np.unique(labels).tolist()) <= {0, 1, 2}:
                raise ValueError("CAC HDF5 labels are not classes 0/1/2")
            expected_mask = labels.astype(np.int64)
        if not np.array_equal(mask[y - 1, x - 1], expected_mask):
            raise AssertionError("mask and HDF5 labels disagree at measured coordinates")

        zero_tic = 0
        minimum_intensity = float("inf")
        maximum_intensity = 0.0
        minimum_nonzero_tic = float("inf")
        maximum_tic = 0.0
        for start in range(0, len(x), 32):
            stop = min(start + 32, len(x))
            block = np.asarray(data[start:stop, :] if pixels_first else data[:, start:stop].T,
                               dtype=np.float32)
            if not np.all(np.isfinite(block)) or np.any(block < 0):
                raise ValueError(f"invalid raw intensity in pixel chunk {start}:{stop}")
            totals_chunk = block.sum(axis=1, dtype=np.float64)
            zero_tic += int(np.count_nonzero(totals_chunk == 0))
            positive = totals_chunk[totals_chunk > 0]
            if len(positive):
                minimum_nonzero_tic = min(minimum_nonzero_tic, float(positive.min()))
            maximum_tic = max(maximum_tic, float(totals_chunk.max()))
            minimum_intensity = min(minimum_intensity, float(block.min()))
            maximum_intensity = max(maximum_intensity, float(block.max()))

        indices = spotcheck_indices(x, y)
        raw = read_raw(data, indices, pixels_first)
        if not np.all(np.isfinite(raw)) or np.any(raw < 0):
            raise ValueError("sampled raw spectra contain invalid intensities")
        totals = raw.sum(axis=1, dtype=np.float64)
        independent_tic = np.divide(raw, totals[:, None],
                                    out=np.zeros_like(raw), where=totals[:, None] != 0)
        source = (check_source_imzml(source_imzml.resolve(strict=True), x, y, mz,
                                    data, pixels_first, indices)
                  if source_imzml is not None else None)
        h5_shape = list(data.shape)

    reference = {size: reference_slots(x, y, size) for size in (3, 5)}
    dataset = H5SpatialContextDataset(h5_path, include_neighbourhood=True)
    try:
        if not np.array_equal(dataset.x, x) or not np.array_equal(dataset.y, y):
            raise AssertionError("production dataset reordered coordinates")
        for size, slots in reference.items():
            production = H5SpatialContextDataset(h5_path, window_size=size)
            try:
                if not np.array_equal(production.neighbour_slots, slots):
                    raise AssertionError(f"production {size}x{size} slots differ from independent reference")
            finally:
                production.close()
        with h5py.File(h5_path, "r") as raw_handle:
            raw_data = raw_handle["Data"]
            for position, index in enumerate(indices):
                sample = dataset[index]
                np.testing.assert_allclose(sample["target"], independent_tic[position], rtol=1e-6, atol=1e-7)
                valid = reference[3][index] >= 0
                if not np.array_equal(sample["neighbour_mask"], valid):
                    raise AssertionError(f"neighbour mask differs at pixel {index}")
                if not np.array_equal(sample["neighbours"][~valid],
                                      np.zeros_like(sample["neighbours"][~valid])):
                    raise AssertionError(f"invalid neighbour carries intensity at pixel {index}")
                neighbour_indices = reference[3][index][valid]
                expected = []
                for neighbour in neighbour_indices:
                    spectrum = read_raw(raw_data, [neighbour], pixels_first)[0]
                    total = float(spectrum.sum(dtype=np.float64))
                    expected.append(spectrum / total if total else np.zeros_like(spectrum))
                if expected:
                    np.testing.assert_allclose(sample["neighbours"][valid], expected, rtol=1e-6, atol=1e-7)
            # Make the visual audit useful at a tissue-class boundary when one
            # exists, without using that label for any model computation.
            boundary_counts = np.asarray([
                np.count_nonzero(expected_mask[row[row >= 0]] != expected_mask[index])
                for index, row in enumerate(reference[3])
            ])
            centre = int(np.argmax(boundary_counts))
            centre_raw = read_raw(raw_data, [centre], pixels_first)[0]
        coverage = np.zeros(mask.shape, dtype=bool)
        coverage[y - 1, x - 1] = True
        output.mkdir(parents=True, exist_ok=True)
        render_spotcheck(output / "spotcheck.png", mz, mask, coverage, x, y,
                         centre, reference[3], centre_raw, dataset[centre]["target"])
    finally:
        dataset.close()

    result = {
        "status": "valid", "section": h5_path.stem, "collection": collection,
        "h5": str(h5_path), "mask": str(mask_path), "source_roundtrip": source,
        "h5_shape": h5_shape, "orientation": "pixels_by_mz" if pixels_first else "mz_by_pixels",
        "measured_pixels": len(x), "mz_bins": len(mz), "mask_shape_y_x": list(mask.shape),
        "coverage_fraction": float(len(x) / mask.size),
        "sampled_indices": indices, "mask_labels_match_at_all_measured_pixels": True,
        "visual_boundary_pixel_index": centre,
        "visual_boundary_pixel_coordinate_x_y": [int(x[centre]), int(y[centre])],
        "visual_different_label_neighbours": int(boundary_counts[centre]),
        "all_raw_spectra_checked": True, "zero_tic_spectra": zero_tic,
        "raw_intensity_min_max": [minimum_intensity, maximum_intensity],
        "nonzero_tic_min": None if minimum_nonzero_tic == float("inf") else minimum_nonzero_tic,
        "tic_max": maximum_tic,
        "reference_neighbours_match_production_all_pixels": {"3": True, "5": True},
        "sampled_raw_tic_and_neighbours_match": True,
        "limitations": ["imzML intensities checked only at sampled pixels" if source else
                        "no original imzML source was supplied",
                        "visual spot-check requires human inspection and does not by itself prove orientation"],
    }
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h5", required=True, type=Path)
    parser.add_argument("--mask", required=True, type=Path)
    parser.add_argument("--collection", required=True, choices=("cac", "gbm"))
    parser.add_argument("--source-imzml", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        audit(args.h5, args.mask, args.output, args.collection, args.source_imzml)
    except Exception as error:
        # Never leave an earlier valid summary looking like the result of a
        # failed rerun. The traceback is still emitted for diagnosis.
        args.output.mkdir(parents=True, exist_ok=True)
        failure = {"status": "failed", "section": args.h5.stem,
                   "error_type": type(error).__name__, "error": str(error)}
        (args.output / "summary.json").write_text(
            json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
