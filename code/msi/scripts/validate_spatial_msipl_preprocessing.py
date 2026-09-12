#!/usr/bin/env python3
"""Validate the Spatial-msiPL preprocessing contract on one real HDF5 file."""

import argparse
import json
from pathlib import Path

import numpy as np

from spatial_msipl.preprocessing import H5SpatialContextDataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    dataset = H5SpatialContextDataset(args.input)
    sampled_indices = sorted({0, len(dataset) // 2, len(dataset) - 1})
    samples = []
    for index in sampled_indices:
        sample = dataset[index]
        central_sum = float(sample["target"].sum(dtype=np.float64))
        context_sum = float(sample["context"].sum(dtype=np.float64))
        if not np.isclose(central_sum, 1.0, atol=1e-5):
            raise ValueError(f"sample {index}: central TIC sum is {central_sum}")
        if sample["neighbour_count"] and not np.isclose(context_sum, 1.0, atol=1e-5):
            raise ValueError(f"sample {index}: context sum is {context_sum}")
        samples.append(
            {
                "index": index,
                "coordinate_x_y": [int(sample["x"]), int(sample["y"])],
                "neighbour_count": int(sample["neighbour_count"]),
                "input_shape": list(sample["input"].shape),
                "target_shape": list(sample["target"].shape),
                "central_tic_sum": central_sum,
                "context_tic_sum": context_sum,
            }
        )

    neighbour_counts = np.asarray(
        [len(indices) for indices in dataset.neighbour_indices], dtype=np.int64
    )
    summary = {
        "input": str(dataset.path),
        "pixels": len(dataset),
        "mz_bins": dataset.n_mz,
        "model_input_features": 2 * dataset.n_mz,
        "streaming": "spectra are read on demand; the full Data matrix is not loaded",
        "context_rule": "mean TIC-normalized spectra from valid measured Moore neighbours",
        "neighbour_count_min": int(neighbour_counts.min()),
        "neighbour_count_max": int(neighbour_counts.max()),
        "neighbour_count_mean": float(neighbour_counts.mean()),
        "sample_checks": samples,
        "status": "valid",
    }
    dataset.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
