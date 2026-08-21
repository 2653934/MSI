#!/usr/bin/env python3
"""Inspect MassNet GBM HDF5 structure without loading spectral matrices."""

import argparse
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

INTERESTING_NAMES = (
    "mz",
    "mass",
    "xlocation",
    "ylocation",
    "coordinate",
    "mask",
    "label",
    "segment",
    "class",
    "annotation",
)


def format_attributes(obj):
    if not obj.attrs:
        return

    print("    attributes:")
    for key, value in obj.attrs.items():
        rendered = np.asarray(value)
        if rendered.size > 20:
            print(f"      {key}: shape={rendered.shape}, dtype={rendered.dtype}")
        else:
            print(f"      {key}: {value!r}")


def inspect_small_or_interesting_dataset(name, dataset):
    normalized_name = name.lower().replace("_", "")
    is_interesting = any(token in normalized_name for token in INTERESTING_NAMES)

    if not is_interesting or dataset.size > 2_000_000:
        return

    try:
        values = np.asarray(dataset[...])
    except Exception as exc:
        print(f"    value inspection failed: {exc}")
        return

    if values.size == 0:
        print("    values: empty")
        return

    if np.issubdtype(values.dtype, np.number):
        finite = values[np.isfinite(values)]
        if finite.size:
            print(f"    value range: {finite.min()} to {finite.max()}")

    if any(token in normalized_name for token in ("mask", "label", "segment", "class")):
        unique = np.unique(values)
        if unique.size <= 50:
            print(f"    unique values: {unique.tolist()}")
        else:
            print(f"    unique value count: {unique.size}")


def inspect_file(path):
    print("=" * 78)
    print(f"FILE: {path.name}")
    print(f"SIZE: {path.stat().st_size} bytes")

    with h5py.File(path, "r") as handle:
        format_attributes(handle)

        dataset_count = 0
        possible_mask_paths = []

        def visitor(name, obj):
            nonlocal dataset_count

            if isinstance(obj, h5py.Group):
                print(f"GROUP: /{name}")
                format_attributes(obj)
                return

            dataset_count += 1
            print(
                f"DATASET: /{name} | shape={obj.shape} | dtype={obj.dtype} "
                f"| chunks={obj.chunks} | compression={obj.compression}"
            )
            format_attributes(obj)
            inspect_small_or_interesting_dataset(name, obj)

            normalized_name = name.lower()
            if any(token in normalized_name for token in ("mask", "label", "segment", "annotation")):
                possible_mask_paths.append("/" + name)

        handle.visititems(visitor)

        print(f"DATASET COUNT: {dataset_count}")
        if possible_mask_paths:
            print("POSSIBLE MASK/LABEL DATASETS:")
            for candidate in possible_mask_paths:
                print(f"  {candidate}")
        else:
            print("POSSIBLE MASK/LABEL DATASETS: none found by name")


def main():
    parser = argparse.ArgumentParser(
        description="Inspect MassNet GBM HDF5 files without loading large spectra arrays."
    )
    parser.add_argument("--input-dir", required=True, type=Path)
    args = parser.parse_args()

    input_dir = args.input_dir.expanduser().resolve()
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    missing = [name for name in EXPECTED_FILES if not (input_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing expected files: {missing}")

    print("MassNet GBM HDF5 metadata inspection")
    print(f"Input directory: {input_dir}")
    print(f"Files: {len(EXPECTED_FILES)}")

    for filename in EXPECTED_FILES:
        inspect_file(input_dir / filename)

    print("=" * 78)
    print("INSPECTION COMPLETE")


if __name__ == "__main__":
    main()
