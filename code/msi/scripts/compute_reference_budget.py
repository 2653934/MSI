#!/usr/bin/env python3
"""RCC bin budget (protocol 18 Section 6.1, item D step 2).

Computes, with the existing nearest-threshold rule on raw-intensity class PCCs,
the size of the mixed reference set |R_t| over all label classes at every
threshold.

- Default (the first version, 16 October 18:10): K_bin = |R@0.4|.
- --released-target-config/--released-target-key (spec correction, supervisor
  chat 2026-10-16 19:47): K_bin = the released S3PL target num_GT_peaks[key]
  from baselines/s3pl/data_configs.py, the same convention as GBM/CAC. The
  paper sets the RCC budget at PCC 0.5, so |R@0.5| and its difference from
  the target are recorded beside it; |R@0.4| is descriptive only.

The sizes for a descriptive class subset (cancer/normal on RCC) are recorded
too and are never a budget. Reads Data, mzArray and Class_Label only; the
config file is parsed with ast, never executed. An existing result is reused
only if its provenance block is identical; otherwise the script stops (exit 3).
"""

import argparse
import ast
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
RELEASED_TARGET_THRESHOLD = 0.5  # the paper's RCC budget threshold (Weigand et al., Table 3)


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="reference_budget.json")
    parser.add_argument("--descriptive-class-subset", type=int, nargs="+",
                        help="raw Class_Label values whose reference sizes are recorded "
                             "descriptively; never used as a budget")
    parser.add_argument("--released-target-config", type=Path,
                        help="baselines/s3pl/data_configs.py; K_bin = num_GT_peaks[key]")
    parser.add_argument("--released-target-key",
                        help="run name in num_GT_peaks (e.g. MH0204_33)")
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--allow-outside-slurm", action="store_true",
                        help="tests only; real sections must run inside Slurm")
    args = parser.parse_args()
    if (args.released_target_config is None) != (args.released_target_key is None):
        parser.error("--released-target-config and --released-target-key go together")
    return args


def released_targets(path):
    """num_GT_peaks from the released S3PL config, read as a literal (never executed)."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "num_GT_peaks"
                for target in node.targets):
            values = ast.literal_eval(node.value)
            return {str(k): int(v) for k, v in values.items()}
    raise ValueError(f"{path}: no num_GT_peaks assignment")


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
    parameters = {"thresholds": list(THRESHOLDS), "budget_threshold": BUDGET_THRESHOLD,
                  "descriptive_class_subset": args.descriptive_class_subset}
    target = None
    if args.released_target_config is not None:
        targets = released_targets(args.released_target_config)
        if args.released_target_key not in targets:
            raise ValueError(f"{args.released_target_key} not in num_GT_peaks")
        target = targets[args.released_target_key]
        parameters = {"thresholds": list(THRESHOLDS),
                      "budget": "released S3PL target num_GT_peaks",
                      "released_target_key": args.released_target_key,
                      "reference_threshold": RELEASED_TARGET_THRESHOLD,
                      "descriptive_class_subset": args.descriptive_class_subset}
    expected = {
        "budget_version": BUDGET_VERSION,
        "protocol": PROTOCOL,
        "dataset": args.input.stem,
        "parameters": parameters,
        "input": file_record(args.input),
        "code": code_record(code),
    }
    if target is not None:
        expected["released_target_config"] = file_record(args.released_target_config)
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
    if target is not None:
        reference = all_classes[str(RELEASED_TARGET_THRESHOLD)]
        summary["K_bin"] = target
        summary["rule"] = ("K_bin = released S3PL target num_GT_peaks (baselines/s3pl/"
                           "data_configs.py), the GBM/CAC convention; the paper sets the RCC "
                           "budget at PCC 0.5 (spec correction, supervisor chat 2026-10-16 "
                           "19:47); |R@0.4| is descriptive only")
        summary["released_target"] = {
            "key": args.released_target_key, "num_GT_peaks": target,
            "our_R_at_0.5": reference, "target_minus_our_R_at_0.5": target - reference,
            "our_R_at_0.4_descriptive": all_classes["0.4"]}
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
