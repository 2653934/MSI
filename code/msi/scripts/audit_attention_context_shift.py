#!/usr/bin/env python3
"""Screen for a centre–context distribution shift in the frozen shuffle.

This reads the same section and seeded shuffle as the completed input-swap
audit. It uses no expert labels, model, GPU, GMM, or peak score. A difference
in these two simple input statistics is evidence of shift, not a complete
out-of-distribution test or a verdict on spatial usefulness.
"""

import argparse
import json
from pathlib import Path

import numpy as np


def input_similarity(centre, context):
    """Return cosine and half-L1 distance, or None for a zero vector."""
    centre = np.asarray(centre, dtype=np.float32)
    context = np.asarray(context, dtype=np.float32)
    if centre.shape != context.shape or centre.ndim != 1:
        raise ValueError("centre and context must be same-length spectra")
    if not np.all(np.isfinite(centre)) or not np.all(np.isfinite(context)):
        raise ValueError("non-finite spectrum")
    a = float(np.linalg.norm(centre))
    b = float(np.linalg.norm(context))
    if a == 0 or b == 0:
        return None
    cosine = float(np.dot(centre, context) / (a * b))
    half_l1 = float(0.5 * np.abs(centre - context).sum(dtype=np.float64))
    return cosine, half_l1


def describe(real, shuffled):
    """Summarise paired values without treating pixels as independent patients."""
    real = np.asarray(real, dtype=np.float64)
    shuffled = np.asarray(shuffled, dtype=np.float64)
    if real.ndim != 1 or real.shape != shuffled.shape or len(real) == 0:
        raise ValueError("non-empty paired one-dimensional values are required")
    if not np.all(np.isfinite(real)) or not np.all(np.isfinite(shuffled)):
        raise ValueError("non-finite paired values")
    low, high = np.quantile(real, [0.05, 0.95])
    return {
        "real_median": float(np.median(real)),
        "shuffled_median": float(np.median(shuffled)),
        "median_paired_change_shuffled_minus_real": float(np.median(shuffled - real)),
        "real_5th_percentile": float(low),
        "real_95th_percentile": float(high),
        "shuffled_below_real_5th_fraction": float(np.mean(shuffled < low)),
        "shuffled_above_real_95th_fraction": float(np.mean(shuffled > high)),
    }


def save_plot(output, section, real_cosine, shuffled_cosine, real_l1, shuffled_l1):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for axis, real, shuffled, label in (
        (axes[0], real_cosine, shuffled_cosine, "Centre–context cosine"),
        (axes[1], real_l1, shuffled_l1, "Centre–context half-L1"),
    ):
        axis.hist(real, bins=25, alpha=0.55, label="Real", density=True)
        axis.hist(shuffled, bins=25, alpha=0.55, label="Shuffled", density=True)
        axis.set_xlabel(label)
        axis.set_ylabel("Density")
        axis.legend()
    fig.suptitle(f"{section}: input relationship under the frozen shuffle")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main():
    from spatial_msipl.preprocessing import CachedH5SpatialContextDataset

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--input-swap-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-pixels", type=int, default=512)
    parser.add_argument("--sample-seed", type=int, default=20261006)
    args = parser.parse_args()
    if args.max_pixels < 1:
        parser.error("max-pixels must be positive")

    with args.input_swap_summary.open(encoding="utf-8") as handle:
        previous = json.load(handle)
    if previous.get("status") != "valid" or previous.get("section") != args.input.stem:
        raise ValueError("input-swap summary does not validate this section")
    if Path(previous["input"]).resolve() != args.input.resolve():
        raise ValueError("input-swap source HDF5 differs")
    shuffle_seed = int(previous["shuffle_seed"])

    real = CachedH5SpatialContextDataset(args.input, window_size=3, context_mode="measured")
    shuffled = CachedH5SpatialContextDataset(
        args.input, window_size=3, context_mode="shuffled", context_seed=shuffle_seed
    )
    try:
        if shuffled.context_permutation_sha256 != previous["shuffle_source_slots_sha256"]:
            raise ValueError("seeded shuffle is not the completed input-swap intervention")
        if not np.array_equal(real.neighbour_slots, shuffled.neighbour_slots):
            raise ValueError("neighbour topology changed")
        eligible = np.flatnonzero(np.any(real.neighbour_slots >= 0, axis=1))
        if not len(eligible):
            raise ValueError("section has no measured neighbour pairs")
        chosen = np.sort(np.random.default_rng(args.sample_seed).choice(
            eligible, size=min(args.max_pixels, len(eligible)), replace=False
        ))
        real_cosine, shuffled_cosine, real_l1, shuffled_l1 = [], [], [], []
        skipped_zero = 0
        for index in chosen:
            original, intervention = real[int(index)], shuffled[int(index)]
            if not np.array_equal(original["target"], intervention["target"]):
                raise ValueError("central spectrum changed")
            if original["neighbour_count"] != intervention["neighbour_count"]:
                raise ValueError("measured neighbour count changed")
            a = input_similarity(original["target"], original["context"])
            b = input_similarity(intervention["target"], intervention["context"])
            if a is None or b is None:
                skipped_zero += 1
                continue
            real_cosine.append(a[0])
            real_l1.append(a[1])
            shuffled_cosine.append(b[0])
            shuffled_l1.append(b[1])
        if not real_cosine:
            raise ValueError("no nonzero paired spectra were available")
        result = {
            "status": "valid",
            "scope": "label-free input-distribution screen; no model or peak evaluation",
            "section": args.input.stem,
            "input": str(args.input),
            "source_input_swap_summary": str(args.input_swap_summary),
            "shuffle_seed": shuffle_seed,
            "shuffle_source_slots_sha256": shuffled.context_permutation_sha256,
            "sample_seed": args.sample_seed,
            "sampled_centres": len(chosen),
            "nonzero_paired_centres": len(real_cosine),
            "skipped_zero_pairs": skipped_zero,
            "cosine_similarity": describe(real_cosine, shuffled_cosine),
            "half_l1_distance": describe(real_l1, shuffled_l1),
            "interpretation_limit": (
                "A shift in centre–context similarity supports an input-distribution "
                "warning; overlap does not prove in-distribution input. Sampled pixels "
                "are spatially dependent and this is not a peak-quality test."
            ),
        }
        args.output.mkdir(parents=True, exist_ok=True)
        save_plot(args.output / "centre_context_shift.png", args.input.stem,
                  real_cosine, shuffled_cosine, real_l1, shuffled_l1)
        (args.output / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2), flush=True)
    finally:
        real.close()
        shuffled.close()


if __name__ == "__main__":
    main()
