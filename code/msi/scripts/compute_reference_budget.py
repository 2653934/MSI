#!/usr/bin/env python3
"""RCC bin budget: K_bin = |R@0.4| over all label classes (protocol 18 Section 6.1).

Computes, with the existing nearest-threshold rule on raw-intensity class PCCs,
the size of the mixed reference set at every threshold and takes K_bin as its
size at PCC 0.4. The sizes for a descriptive class subset (cancer/normal on
RCC) are recorded beside it and are never a budget. Reads Data, mzArray and
Class_Label only. An existing result is reused only if its provenance block is
identical; otherwise the script stops (exit 3).
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from evaluate_msipl_massnet_peaks import THRESHOLDS, true_indices_at_threshold
from evaluate_spatial_msipl_attributed_peaks import load_correlations, read_h5_metadata
import evaluate_msipl_massnet_peaks
import evaluate_spatial_msipl_attributed_peaks
from spatial_msipl import provenance
from spatial_msipl.provenance import (
    StaleResultError,
    atomic_write_json,
    check_existing,
    code_record,
    file_record,
    require_slurm,
)

BUDGET_VERSION = 1
PROTOCOL = "docs/research/18 Fair Scoring and Simple Baselines Protocol.md (v3.2), Section 6.1 item D step 2"
BUDGET_THRESHOLD = 0.4
COMPLETE = "complete"


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="reference_budget.json")
    parser.add_argument("--descriptive-class-subset", type=int, nargs="+",
                        help="raw Class_Label values whose reference sizes are recorded "
                             "descriptively; never used as a budget")
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--allow-outside-slurm", action="store_true",
                        help="tests only; real sections must run inside Slurm")
    return parser.parse_args()


def reference_sizes(correlations, classes):
    sizes = {}
    for threshold in THRESHOLDS:
        union = set().union(*(true_indices_at_threshold(correlations[c], threshold)
                              for c in classes))
        sizes[str(threshold)] = len(union)
    return sizes


def main():
    args = parse_arguments()
    require_slurm(args.allow_outside_slurm)
    started = time.perf_counter()
    code = [Path(__file__).resolve()] + [
        Path(m.__file__).resolve()
        for m in (provenance, evaluate_msipl_massnet_peaks,
                  evaluate_spatial_msipl_attributed_peaks)]
    expected = {
        "budget_version": BUDGET_VERSION,
        "protocol": PROTOCOL,
        "dataset": args.input.stem,
        "parameters": {"thresholds": list(THRESHOLDS), "budget_threshold": BUDGET_THRESHOLD,
                       "descriptive_class_subset": args.descriptive_class_subset},
        "input": file_record(args.input),
        "code": code_record(code),
    }
    try:
        state = check_existing(args.output, expected, COMPLETE)
    except StaleResultError as error:
        print(f"STALE: {error}", file=sys.stderr)
        raise SystemExit(3)
    if state == "valid":
        print(f"Existing budget matches current provenance; skipped: {args.output}")
        return

    mz, labels, _, _, pixels_first = read_h5_metadata(args.input)
    correlations = load_correlations(args.input, labels, len(mz), pixels_first,
                                     args.chunk_size)
    classes = sorted(correlations)
    all_classes = reference_sizes(correlations, classes)
    summary = {
        "status": COMPLETE,
        "provenance": expected,
        "dataset": args.input.stem,
        "K_bin": all_classes[str(BUDGET_THRESHOLD)],
        "rule": ("K_bin = |R@0.4|: size of the mixed reference set at PCC 0.4 over all "
                 "label classes, existing nearest-threshold rule on raw-intensity PCC"),
        "classes": classes,
        "pixels_per_class": {str(c): int(np.count_nonzero(labels == c)) for c in classes},
        "spectral_bins": int(len(mz)),
        "reference_set_sizes_all_classes": all_classes,
        "reference_set_sizes_per_class": {
            str(c): reference_sizes(correlations, [c]) for c in classes},
    }
    if args.descriptive_class_subset is not None:
        missing = sorted(set(args.descriptive_class_subset) - set(classes))
        if missing:
            raise ValueError(f"descriptive class subset {missing} not in labels {classes}")
        summary["reference_set_sizes_descriptive_subset"] = {
            "classes": sorted(args.descriptive_class_subset),
            "sizes": reference_sizes(correlations, sorted(args.descriptive_class_subset)),
            "use": "descriptive only; never a budget (the sensitivity analysis keeps K_bin)",
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary["runtime_seconds"] = time.perf_counter() - started
    atomic_write_json(args.output, summary)
    print(f"K_bin = {summary['K_bin']} ({args.input.stem})")


if __name__ == "__main__":
    main()
