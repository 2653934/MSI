#!/usr/bin/env python3
"""Compare real and seeded nonlocal 3x3 contexts before model inference.

Expert labels define post-hoc boundary/interior groups only. They never enter
the context construction, model training, attribution, or peak selection.
"""

import argparse
import csv
import json
from pathlib import Path

import h5py
import numpy as np

from spatial_msipl.preprocessing import (
    CachedH5SpatialContextDataset,
    H5SpatialContextDataset,
    tic_normalize,
)


def cosine(left, right):
    denominator = np.linalg.norm(left) * np.linalg.norm(right)
    return float(np.dot(left, right) / denominator) if denominator > 0 else None


def mean_or_none(values):
    finite = [value for value in values if value is not None and np.isfinite(value)]
    return float(np.mean(finite)) if finite else None


def select_centres(slots, labels, per_class, seed):
    valid = slots >= 0
    other_label = valid & (labels[np.maximum(slots, 0)] != labels[:, None])
    boundary = np.any(other_label, axis=1)
    rng = np.random.default_rng(seed)
    selected = []
    for group_name, group_mask in (("boundary", boundary), ("interior", ~boundary)):
        for label in np.unique(labels):
            candidates = np.flatnonzero(group_mask & (labels == label))
            chosen = rng.choice(
                candidates, size=min(per_class, len(candidates)), replace=False
            )
            selected.extend((int(index), group_name) for index in np.sort(chosen))
    return selected, {
        "boundary_centres": int(boundary.sum()),
        "interior_centres": int((~boundary).sum()),
    }


def compare_section(input_path, metadata_path, output_dir, per_class, seed):
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    input_spec = metadata["resume_signature"] if "resume_signature" in metadata else None
    if input_spec is None:
        # Production metadata stores the data-input signature under experiment.
        input_spec = metadata.get("experiment", {})
    expected_hash = input_spec.get("context_permutation_sha256")
    expected_seed = input_spec.get("context_seed")
    if expected_seed is None or expected_hash is None:
        raise ValueError(f"shuffled metadata lacks seed/hash: {metadata_path}")

    measured = CachedH5SpatialContextDataset(input_path, window_size=3)
    shuffled = H5SpatialContextDataset(
        input_path, window_size=3, context_mode="shuffled",
        context_seed=int(expected_seed),
    )
    try:
        if not np.array_equal(measured.neighbour_slots, shuffled.neighbour_slots):
            raise AssertionError("real and shuffled geometries differ")
        if shuffled.context_permutation_sha256 != expected_hash:
            raise AssertionError("shuffled sources do not match the trained run")
        with h5py.File(input_path, "r") as handle:
            labels = np.asarray(handle["Class_Label"][:]).reshape(-1)
        if len(labels) != len(measured):
            raise ValueError("label count differs from measured spectra")

        selected, population = select_centres(
            measured.neighbour_slots, labels, per_class, seed
        )
        rows = []
        for index, group in selected:
            real_sources = measured.neighbour_indices[index]
            nonlocal_sources = shuffled.context_source_slots[index]
            nonlocal_sources = nonlocal_sources[nonlocal_sources >= 0]
            central = measured[index]["target"]
            real = measured[index]["context"]
            nonlocal_spectra = tic_normalize(measured._spectra[nonlocal_sources])
            nonlocal_context = (
                nonlocal_spectra.mean(axis=0, dtype=np.float32)
                if len(nonlocal_sources) else np.zeros_like(central)
            )
            rows.append({
                "index": index,
                "x": int(measured.x[index]),
                "y": int(measured.y[index]),
                "class_label": int(labels[index]),
                "group": group,
                "valid_neighbours": len(real_sources),
                "real_same_class_fraction": (
                    float(np.mean(labels[real_sources] == labels[index]))
                    if len(real_sources) else None
                ),
                "shuffled_same_class_fraction": (
                    float(np.mean(labels[nonlocal_sources] == labels[index]))
                    if len(nonlocal_sources) else None
                ),
                "cosine_central_real": cosine(central, real),
                "cosine_central_shuffled": cosine(central, nonlocal_context),
                "cosine_real_shuffled": cosine(real, nonlocal_context),
                "l1_central_real": float(np.abs(central - real).sum()),
                "l1_central_shuffled": float(np.abs(central - nonlocal_context).sum()),
                "l1_real_shuffled": float(np.abs(real - nonlocal_context).sum()),
            })

        # Three streamed canaries verify that the sampled shuffled context
        # constructed from the shared cache equals production __getitem__.
        canary_errors = []
        for index, _ in selected[:3]:
            sources = shuffled.context_source_slots[index]
            sources = sources[sources >= 0]
            expected = (
                tic_normalize(measured._spectra[sources]).mean(
                    axis=0, dtype=np.float32
                ) if len(sources) else np.zeros(measured.n_mz, dtype=np.float32)
            )
            observed = shuffled[index]["context"]
            canary_errors.append(float(np.max(np.abs(expected - observed))))
        if any(error > 1e-6 for error in canary_errors):
            raise AssertionError("cached and streamed shuffled contexts differ")

        by_group = {}
        for group in ("boundary", "interior"):
            group_rows = [row for row in rows if row["group"] == group]
            by_group[group] = {
                "sampled_centres": len(group_rows),
                "mean_real_same_class_fraction": mean_or_none(
                    [row["real_same_class_fraction"] for row in group_rows]
                ),
                "mean_shuffled_same_class_fraction": mean_or_none(
                    [row["shuffled_same_class_fraction"] for row in group_rows]
                ),
                "mean_cosine_central_real": mean_or_none(
                    [row["cosine_central_real"] for row in group_rows]
                ),
                "mean_cosine_central_shuffled": mean_or_none(
                    [row["cosine_central_shuffled"] for row in group_rows]
                ),
                "mean_cosine_real_shuffled": mean_or_none(
                    [row["cosine_real_shuffled"] for row in group_rows]
                ),
                "mean_l1_real_shuffled": mean_or_none(
                    [row["l1_real_shuffled"] for row in group_rows]
                ),
            }
        class_values, class_counts = np.unique(labels, return_counts=True)
        result = {
            "dataset": input_path.stem,
            "source_h5": str(input_path),
            "shuffled_metadata": str(metadata_path),
            "context_seed": int(expected_seed),
            "context_permutation_sha256": expected_hash,
            "sampling_seed": seed,
            "maximum_sampled_centres_per_group_and_class": per_class,
            "measured_pixels": len(measured),
            "class_counts": {
                str(int(value)): int(count)
                for value, count in zip(class_values, class_counts)
            },
            "population_groups": population,
            "groups": by_group,
            "streamed_vs_cached_canary_max_abs_errors": canary_errors,
            "interpretation_limit": (
                "Descriptive, class-balanced sample of input contexts, not a "
                "model-performance or causal test. Boundary groups use expert "
                "labels post hoc; input contexts remain label-free."
            ),
            "status": "valid",
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{input_path.stem}.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        with (output_dir / f"{input_path.stem}_pixels.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return result
    finally:
        measured.close()
        shuffled.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--shuffled-metadata", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--per-class", type=int, default=64)
    parser.add_argument("--sampling-seed", type=int, default=23)
    args = parser.parse_args()
    if args.per_class < 1:
        raise ValueError("per-class must be positive")
    result = compare_section(
        args.input, args.shuffled_metadata, args.output_dir,
        args.per_class, args.sampling_seed,
    )
    print(json.dumps({
        "dataset": result["dataset"], "population_groups": result["population_groups"],
        "groups": result["groups"], "status": result["status"],
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()
