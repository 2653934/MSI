#!/usr/bin/env python3
"""Reconstruct S3PL-compatible GBM masks from the MassNet HDF5 labels."""

import argparse
import json
from pathlib import Path

import h5py
import numpy as np


EXPECTED_FILES = (
    "GBM108_negative.h5",
    "GBM108_positive.h5",
    "GBM12_1.h5",
    "GBM12_2.h5",
    "GBM22_1.h5",
    "GBM22_2.h5",
    "GBM39_1.h5",
    "GBM39_2.h5",
)

# Confirmed in the original MassNet implementation:
# Class_Label == 1 is normal tissue and Class_Label == 2 is tumour.
RAW_TO_S3PL = {1: 0, 2: 1}
CLASS_NAMES = {0: "normal", 1: "tumour"}


def load_spatial_labels(path):
    with h5py.File(path, "r") as handle:
        required = ("Class_Label", "xLocation", "yLocation")
        missing = [name for name in required if name not in handle]
        if missing:
            raise KeyError(f"{path.name}: missing datasets {missing}")

        raw_labels = np.asarray(handle["Class_Label"]).reshape(-1)
        x = np.asarray(handle["xLocation"]).reshape(-1)
        y = np.asarray(handle["yLocation"]).reshape(-1)

    if not (len(raw_labels) == len(x) == len(y)):
        raise ValueError(
            f"{path.name}: label/coordinate lengths differ: "
            f"labels={len(raw_labels)}, x={len(x)}, y={len(y)}"
        )

    if len(raw_labels) == 0:
        raise ValueError(f"{path.name}: contains no labelled pixels")

    if not np.all(np.isfinite(raw_labels)):
        raise ValueError(f"{path.name}: Class_Label contains non-finite values")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError(f"{path.name}: coordinates contain non-finite values")

    if not np.all(raw_labels == np.rint(raw_labels)):
        raise ValueError(f"{path.name}: Class_Label contains non-integer values")
    if not np.all(x == np.rint(x)) or not np.all(y == np.rint(y)):
        raise ValueError(f"{path.name}: coordinates contain non-integer values")

    raw_labels = raw_labels.astype(np.uint8)
    x = x.astype(np.int32)
    y = y.astype(np.int32)

    observed = set(np.unique(raw_labels).tolist())
    expected = set(RAW_TO_S3PL)
    if observed != expected:
        raise ValueError(
            f"{path.name}: expected raw labels {sorted(expected)}, "
            f"found {sorted(observed)}"
        )

    if np.any(x < 1) or np.any(y < 1):
        raise ValueError(f"{path.name}: coordinates must be one-based and positive")

    coordinates = np.column_stack((x, y))
    if len(np.unique(coordinates, axis=0)) != len(coordinates):
        raise ValueError(f"{path.name}: duplicate spatial coordinates found")

    return raw_labels, x, y


def create_grids(raw_labels, x, y):
    height = int(np.max(y))
    width = int(np.max(x))

    # S3PL indexes masks as mask[y - 1, x - 1].
    mask = np.zeros((height, width), dtype=np.uint8)
    coverage = np.zeros((height, width), dtype=bool)
    raw_grid = np.zeros((height, width), dtype=np.uint8)

    rows = y - 1
    columns = x - 1
    mapped_labels = np.fromiter(
        (RAW_TO_S3PL[int(label)] for label in raw_labels),
        dtype=np.uint8,
        count=len(raw_labels),
    )

    mask[rows, columns] = mapped_labels
    raw_grid[rows, columns] = raw_labels
    coverage[rows, columns] = True

    if not np.array_equal(mask[rows, columns], mapped_labels):
        raise RuntimeError("Mask reconstruction failed its round-trip check")

    return mask, coverage, raw_grid, mapped_labels


def process_file(path, mask_dir, audit_dir):
    raw_labels, x, y = load_spatial_labels(path)
    mask, coverage, raw_grid, mapped_labels = create_grids(raw_labels, x, y)
    dataset = path.stem

    mask_path = mask_dir / f"{dataset}_mask.npy"
    coverage_path = audit_dir / f"{dataset}_coverage.npy"
    raw_grid_path = audit_dir / f"{dataset}_raw_labels.npy"

    np.save(mask_path, mask)
    np.save(coverage_path, coverage)
    np.save(raw_grid_path, raw_grid)

    normal_count = int(np.count_nonzero(mapped_labels == 0))
    tumour_count = int(np.count_nonzero(mapped_labels == 1))
    grid_pixels = int(mask.size)
    measured_pixels = int(len(mapped_labels))

    summary = {
        "dataset": dataset,
        "source_file": str(path),
        "mask_file": str(mask_path),
        "coverage_file": str(coverage_path),
        "raw_label_grid_file": str(raw_grid_path),
        "mask_shape_y_x": [int(mask.shape[0]), int(mask.shape[1])],
        "measured_pixels": measured_pixels,
        "grid_pixels": grid_pixels,
        "unmeasured_grid_locations": grid_pixels - measured_pixels,
        "coverage_percent": 100.0 * measured_pixels / grid_pixels,
        "class_mapping": {
            "raw_1": "S3PL 0 (normal)",
            "raw_2": "S3PL 1 (tumour)",
            "raw_grid_0": "unmeasured location",
        },
        "measured_class_counts": {
            CLASS_NAMES[0]: normal_count,
            CLASS_NAMES[1]: tumour_count,
        },
    }

    print("=" * 72)
    print(dataset)
    print(f"  shape (y, x): {mask.shape}")
    print(f"  measured pixels: {measured_pixels}")
    print(f"  grid coverage: {summary['coverage_percent']:.2f}%")
    print(f"  normal (mask 0): {normal_count}")
    print(f"  tumour (mask 1): {tumour_count}")
    print(f"  saved: {mask_path}")

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Create S3PL-compatible masks from MassNet GBM HDF5 labels."
    )
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument(
        "--mask-dir",
        type=Path,
        help="Destination for <dataset>_mask.npy files (default: INPUT_DIR/masks)",
    )
    parser.add_argument(
        "--audit-dir",
        type=Path,
        help="Destination for coverage/raw grids and summary (default: MASK_DIR/audit)",
    )
    args = parser.parse_args()

    input_dir = args.input_dir.expanduser().resolve()
    mask_dir = (args.mask_dir or input_dir / "masks").expanduser().resolve()
    audit_dir = (args.audit_dir or mask_dir / "audit").expanduser().resolve()

    missing = [name for name in EXPECTED_FILES if not (input_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing expected files: {missing}")

    mask_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    summaries = [
        process_file(input_dir / filename, mask_dir, audit_dir)
        for filename in EXPECTED_FILES
    ]

    summary_path = audit_dir / "massnet_gbm_mask_summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "provenance": (
                    "MassNet Class_Label values derived from expert-pathologist "
                    "H&E tumour annotations manually transferred to MSI coordinates"
                ),
                "class_mapping": {"1": "normal", "2": "tumour"},
                "s3pl_mapping": {"0": "normal", "1": "tumour"},
                "datasets": summaries,
            },
            handle,
            indent=2,
        )

    print("=" * 72)
    print(f"Created {len(summaries)} masks")
    print(f"Audit summary: {summary_path}")


if __name__ == "__main__":
    main()
