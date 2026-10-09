#!/usr/bin/env python3
"""Structural audit of the predeclared P1/P3 m/z peak partitions (gate a).

Reads only ``Data`` and ``mzArray``. It never reads class labels, masks,
peak lists or scores. It writes the partition arrays, structural summaries and
the S1 verdict (the only hard rule) plus S2/S3 diagnostics for human
review. Peak-level scoring may use a
partition only after a reviewer records it in ``partition_approval.json``.
"""

import argparse
import csv
import sys
import time
from pathlib import Path

import h5py
import numpy as np

from spatial_msipl import peak_groups, provenance
from spatial_msipl.provenance import (
    StaleResultError,
    atomic_write_json,
    check_existing,
    code_record,
    file_record,
    require_slurm,
)
from spatial_msipl.peak_groups import (
    P1_DEFAULTS,
    P3_DEFAULTS,
    SANITY_DEFAULTS,
    check_partition_sanity,
    partition_p1_basins,
    partition_p3_ppm,
    partition_structure,
)


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=2048)
    parser.add_argument("--allow-outside-slurm", action="store_true",
                        help="tests only; real sections must run inside Slurm")
    return parser.parse_args()


AUDIT_VERSION = 3
PROTOCOL = "docs/research/18 Fair Scoring and Simple Baselines Protocol.md (v3)"


def expected_provenance(args):
    code = [Path(__file__).resolve(), Path(peak_groups.__file__).resolve(),
            Path(provenance.__file__).resolve()]
    return {
        "audit_version": AUDIT_VERSION,
        "protocol": PROTOCOL,
        "dataset": args.input.stem,
        "parameters": {"P1": P1_DEFAULTS, "P3": P3_DEFAULTS, "sanity": SANITY_DEFAULTS},
        "input": file_record(args.input),
        "code": code_record(code),
    }


def mean_tic_spectrum(path, chunk_size):
    """Mean TIC-normalised spectrum over measured pixels (zero-TIC pixels stay zero)."""
    with h5py.File(path, "r") as handle:
        mz = np.asarray(handle["mzArray"], dtype=np.float64).reshape(-1)
        data = handle["Data"]
        if data.shape[1] == len(mz):
            pixels_first = True
            n_pixels = data.shape[0]
        elif data.shape[0] == len(mz):
            pixels_first = False
            n_pixels = data.shape[1]
        else:
            raise ValueError(f"cannot orient Data shape {data.shape}")

        tic = np.zeros(n_pixels, dtype=np.float64)
        for start in range(0, len(mz), chunk_size):
            stop = min(start + chunk_size, len(mz))
            block = (np.asarray(data[:, start:stop], dtype=np.float64) if pixels_first
                     else np.asarray(data[start:stop, :], dtype=np.float64).T)
            if np.any(block < 0) or not np.all(np.isfinite(block)):
                raise ValueError("negative or non-finite intensities")
            tic += block.sum(axis=1)
        scale = np.zeros_like(tic)
        np.divide(1.0, tic, out=scale, where=tic > 0)

        mean = np.zeros(len(mz), dtype=np.float64)
        for start in range(0, len(mz), chunk_size):
            stop = min(start + chunk_size, len(mz))
            block = (np.asarray(data[:, start:stop], dtype=np.float64) if pixels_first
                     else np.asarray(data[start:stop, :], dtype=np.float64).T)
            mean[start:stop] = (block * scale[:, None]).mean(axis=0)
    return mz, mean, int(n_pixels), int(np.count_nonzero(tic == 0))


def write_extremes(path, structure):
    with open(path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["list", "group", "first_mz", "last_mz", "bins", "width_da", "width_ppm"])
        for name in ("widest_groups", "largest_groups"):
            for row in structure[name]:
                writer.writerow([name, row["group"], row["first_mz"], row["last_mz"],
                                 row["bins"], row["width_da"], row["width_ppm"]])


def main():
    args = parse_arguments()
    require_slurm(args.allow_outside_slurm)
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    expected = expected_provenance(args)
    try:
        if check_existing(args.output / "summary.json", expected, "complete") == "valid":
            print(f"Existing audit matches current provenance; skipped: {args.output}")
            return
    except StaleResultError as error:
        print(f"STALE: {error}", file=sys.stderr)
        raise SystemExit(3)
    mz, mean, n_pixels, zero_tic = mean_tic_spectrum(args.input, args.chunk_size)

    partitions = {
        "P1": (partition_p1_basins(mean, mz, **P1_DEFAULTS), P1_DEFAULTS),
        "P3": (partition_p3_ppm(mean, mz, **P3_DEFAULTS), P3_DEFAULTS),
    }
    gaps = np.diff(mz) / mz[:-1] * 1e6
    summary = {
        "status": "complete",
        "provenance": expected,
        "dataset": args.input.stem,
        "inputs_read": ["Data", "mzArray"],
        "labels_or_scores_read": False,
        "pixels": n_pixels,
        "zero_tic_pixels": zero_tic,
        "axis_gap_ppm": {
            "min": float(gaps.min()), "median": float(np.median(gaps)),
            "p99": float(np.percentile(gaps, 99)), "max": float(gaps.max()),
        },
        "sanity_rules": SANITY_DEFAULTS,
        "partitions": {},
    }
    arrays = {"mz": mz, "mean_tic_spectrum": mean}
    for name, ((group_of_bin, apex), parameters) in partitions.items():
        structure = partition_structure(group_of_bin, mz)
        verdict = check_partition_sanity(structure, **SANITY_DEFAULTS)
        summary["partitions"][name] = {
            "parameters": parameters, "structure": structure, "sanity": verdict,
        }
        arrays[f"{name}_group_of_bin"] = group_of_bin
        arrays[f"{name}_apex"] = apex
        write_extremes(args.output / f"{name}_extreme_groups.csv", structure)

    np.savez_compressed(args.output / "partitions.npz", **arrays)
    summary["runtime_seconds"] = time.perf_counter() - started
    atomic_write_json(args.output / "summary.json", summary)
    for name, record in summary["partitions"].items():
        structure = record["structure"]
        print(f"{args.input.stem} {name}: groups={structure['groups']} "
              f"max_width={structure['width_da']['max']:.4f} Da "
              f"S1_passed={record['sanity']['passed']} {record['sanity']['failures']} "
              f"largest_group_bins={record['sanity']['diagnostics']['S2_largest_group_bins']}")


if __name__ == "__main__":
    main()
