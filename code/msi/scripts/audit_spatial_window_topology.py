#!/usr/bin/env python3
"""Audit measured-neighbour geometry and label mixing without reading spectra.

Class labels are used only for this post-hoc diagnostic. They are never passed
to the VAE, GMM, attribution, or peak-selection code.
"""

import argparse
import csv
import json
from pathlib import Path

import h5py
import numpy as np

from spatial_msipl.preprocessing import build_square_neighbour_slots


def _integer_vector(values, name, positive=False):
    array = np.asarray(values).reshape(-1)
    if array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be non-empty and finite")
    if not np.all(array == np.rint(array)):
        raise ValueError(f"{name} must contain integers")
    result = array.astype(np.int64)
    if positive and np.any(result < 1):
        raise ValueError(f"{name} must be one-based and positive")
    return result


def load_coordinates_and_labels(path):
    with h5py.File(path, "r") as handle:
        required = ("xLocation", "yLocation", "Class_Label")
        missing = [name for name in required if name not in handle]
        if missing:
            raise KeyError(f"{path}: missing {missing}")
        x = _integer_vector(handle["xLocation"][:], "xLocation", positive=True)
        y = _integer_vector(handle["yLocation"][:], "yLocation", positive=True)
        labels = _integer_vector(handle["Class_Label"][:], "Class_Label")
    if not (len(x) == len(y) == len(labels)):
        raise ValueError(f"{path}: coordinates and labels have different lengths")
    return x, y, labels


def independent_reference_slots(x, y, window_size):
    """Coordinate lookup written separately from the production slot builder."""
    coordinates = list(zip(x.tolist(), y.tolist()))
    lookup = {coordinate: index for index, coordinate in enumerate(coordinates)}
    if len(lookup) != len(coordinates):
        raise ValueError("duplicate measured coordinates")
    radius = window_size // 2
    offsets = [
        (dx, dy)
        for dy in range(-radius, radius + 1)
        for dx in range(-radius, radius + 1)
        if dx != 0 or dy != 0
    ]
    slots = np.full((len(x), len(offsets)), -1, dtype=np.int64)
    for index, (centre_x, centre_y) in enumerate(coordinates):
        for slot, (dx, dy) in enumerate(offsets):
            slots[index, slot] = lookup.get((centre_x + dx, centre_y + dy), -1)
    return slots


def audit_window(x, y, labels, window_size):
    reference = independent_reference_slots(x, y, window_size)
    production = build_square_neighbour_slots(x, y, window_size)
    if not np.array_equal(reference, production):
        mismatch = np.argwhere(reference != production)[0]
        raise AssertionError(
            f"production/reference neighbour mismatch at pixel {mismatch[0]}, "
            f"slot {mismatch[1]}"
        )

    valid = reference >= 0
    counts = valid.sum(axis=1)
    safe_indices = np.maximum(reference, 0)
    cross_class = valid & (labels[safe_indices] != labels[:, None])
    cross_counts = cross_class.sum(axis=1)
    total_edges = int(valid.sum())
    class_stats = {}
    for label in np.unique(labels):
        selected = labels == label
        class_stats[str(int(label))] = {
            "centres": int(selected.sum()),
            "mean_valid_neighbours": float(counts[selected].mean()),
            "fraction_centres_with_cross_class_neighbour": float(
                np.mean(cross_counts[selected] > 0)
            ),
        }
    return {
        "window_size": window_size,
        "possible_neighbours_per_centre": int(reference.shape[1]),
        "reference_matches_production": True,
        "measured_centres": len(x),
        "valid_directed_edges": total_edges,
        "valid_slot_fraction": float(total_edges / reference.size),
        "mean_valid_neighbours": float(counts.mean()),
        "median_valid_neighbours": float(np.median(counts)),
        "min_valid_neighbours": int(counts.min()),
        "max_valid_neighbours": int(counts.max()),
        "centres_without_neighbours": int(np.count_nonzero(counts == 0)),
        "cross_class_directed_edges": int(cross_class.sum()),
        "cross_class_fraction_of_valid_edges": float(
            cross_class.sum() / total_edges if total_edges else 0.0
        ),
        "fraction_centres_with_cross_class_neighbour": float(
            np.mean(cross_counts > 0)
        ),
        "by_centre_class": class_stats,
    }


def audit_section(path):
    x, y, labels = load_coordinates_and_labels(path)
    label_values, label_counts = np.unique(labels, return_counts=True)
    grid_pixels = int(x.max() * y.max())
    return {
        "dataset": path.stem,
        "source_h5": str(path),
        "measured_pixels": len(x),
        "grid_shape_y_x": [int(y.max()), int(x.max())],
        "grid_coverage_fraction": float(len(x) / grid_pixels),
        "class_counts_at_measured_pixels": {
            str(int(label)): int(count)
            for label, count in zip(label_values, label_counts)
        },
        "windows": {
            str(size): audit_window(x, y, labels, size) for size in (3, 5)
        },
        "interpretation_limit": (
            "Cross-class measured edges are a label-informed post-hoc proxy "
            "for boundary mixing, not a causal explanation or training input. "
            "No spectra or model outputs were read."
        ),
        "status": "valid",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("inputs", type=Path, nargs="+")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if len({path.stem for path in args.inputs}) != len(args.inputs):
        raise ValueError("input section names must be unique")
    rows = []
    for path in args.inputs:
        result = audit_section(path)
        (args.output_dir / f"{path.stem}.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        for size, window in result["windows"].items():
            rows.append({
                "dataset": result["dataset"],
                "window_size": size,
                "measured_pixels": result["measured_pixels"],
                "grid_coverage_fraction": result["grid_coverage_fraction"],
                "mean_valid_neighbours": window["mean_valid_neighbours"],
                "valid_slot_fraction": window["valid_slot_fraction"],
                "cross_class_fraction_of_valid_edges": window[
                    "cross_class_fraction_of_valid_edges"
                ],
                "fraction_centres_with_cross_class_neighbour": window[
                    "fraction_centres_with_cross_class_neighbour"
                ],
            })
        print(
            f"{path.stem}: 3x3 valid={result['windows']['3']['valid_slot_fraction']:.3f}, "
            f"cross-class={result['windows']['3']['cross_class_fraction_of_valid_edges']:.3f}; "
            f"5x5 valid={result['windows']['5']['valid_slot_fraction']:.3f}, "
            f"cross-class={result['windows']['5']['cross_class_fraction_of_valid_edges']:.3f}",
            flush=True,
        )
    with (args.output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(args.inputs)} section audits to {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
