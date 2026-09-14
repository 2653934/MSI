#!/usr/bin/env python3
"""Convert one CAC imzML section into the small HDF5 schema msiPL expects.

No intensities, m/z values, coordinates, or labels are transformed.  The
script only places them in one file so that the legacy msiPL loader can read
the CAC data in the same way that it reads the MassNet GBM data.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import h5py
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
S3PL_ROOT = PROJECT_ROOT / "baselines" / "s3pl"
if str(S3PL_ROOT) not in sys.path:
    sys.path.insert(0, str(S3PL_ROOT))

from utils.data_source import load_imzml_table


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--mask", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    args = parser.parse_args()

    input_path = args.input.expanduser().resolve()
    mask_path = args.mask.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    audit_path = args.audit.expanduser().resolve()

    if not input_path.is_file():
        raise FileNotFoundError("imzML input not found: {}".format(input_path))
    if not mask_path.is_file():
        raise FileNotFoundError("CAC mask not found: {}".format(mask_path))
    if output_path.exists():
        raise FileExistsError("refusing to overwrite existing adapter: {}".format(output_path))

    table = load_imzml_table(input_path)
    mask = np.load(mask_path)
    expected_shape = (int(table.y.max()), int(table.x.max()))
    if mask.shape != expected_shape:
        raise ValueError(
            "mask shape {} does not match coordinate grid {}".format(
                mask.shape, expected_shape
            )
        )

    labels = np.asarray(mask[table.y - 1, table.x - 1], dtype=np.int64)
    class_values, class_counts = np.unique(labels, return_counts=True)
    if class_values.tolist() != [0, 1, 2]:
        raise ValueError(
            "expected CAC labels [0, 1, 2] at measured locations; found {}".format(
                class_values.tolist()
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = output_path.with_suffix(output_path.suffix + ".partial")
    with h5py.File(partial_path, "w") as handle:
        handle.create_dataset("Data", data=table.spectra, dtype=np.float32)
        handle.create_dataset("mzArray", data=table.mz_values)
        handle.create_dataset("xLocation", data=table.x, dtype=np.int32)
        handle.create_dataset("yLocation", data=table.y, dtype=np.int32)
        handle.create_dataset("Class_Label", data=labels, dtype=np.int64)
        handle.attrs["source_imzml"] = str(input_path)
        handle.attrs["source_mask"] = str(mask_path)
        handle.attrs["adapter_purpose"] = "legacy msiPL compatibility"
    os.replace(str(partial_path), str(output_path))

    # Read the written file back.  This catches orientation, truncation, and
    # coordinate/label mistakes before any model time is spent.
    with h5py.File(output_path, "r") as handle:
        if handle["Data"].shape != table.spectra.shape:
            raise RuntimeError("written spectra shape failed round-trip validation")
        if not np.array_equal(handle["mzArray"][:], table.mz_values):
            raise RuntimeError("m/z axis failed round-trip validation")
        if not np.array_equal(handle["xLocation"][:], table.x):
            raise RuntimeError("x coordinates failed round-trip validation")
        if not np.array_equal(handle["yLocation"][:], table.y):
            raise RuntimeError("y coordinates failed round-trip validation")
        if not np.array_equal(handle["Class_Label"][:], labels):
            raise RuntimeError("class labels failed round-trip validation")

    summary = {
        "dataset": input_path.stem,
        "source_imzml": str(input_path),
        "source_mask": str(mask_path),
        "output_h5": str(output_path),
        "spectra_shape_pixels_mz": [int(value) for value in table.spectra.shape],
        "mz_range": [float(table.mz_values[0]), float(table.mz_values[-1])],
        "spatial_shape_y_x": list(expected_shape),
        "measured_pixels": int(len(table.x)),
        "grid_pixels": int(mask.size),
        "coverage_percent": float(100.0 * len(table.x) / mask.size),
        "class_counts_at_measured_pixels": {
            str(int(value)): int(count)
            for value, count in zip(class_values, class_counts)
        },
        "checks": {
            "shared_mz_axis": True,
            "mask_coordinate_alignment": True,
            "h5_round_trip": True,
            "intensity_transformation": "none",
        },
        "status": "valid",
    }
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
