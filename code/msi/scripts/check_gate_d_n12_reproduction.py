#!/usr/bin/env python3
"""Gate (d) stage 1: n = 12 run-validity checks and reproduction gate only.

CPU only. Supervisor review of 9 October approved GBM108_positive in stages:
n = 12 for both arms first, then n = 48 and 192 only for an arm whose n = 12
reproduces. evaluate_gate_d_pixel_counts.py needs all three runs, so this
script applies its n = 12 checks on their own, by importing its functions.
The evaluator itself is not changed, so its code hash (part of the campaign
provenance the summariser compares) stays the same as for 40TopL.

Checks, as in the evaluator: IG status 'valid'; labels aligned to the same
production reference; dataset and arm match; coordinates match the HDF5; GMM
assignment identical to production; exactly 12 attribution pixels requested
per component. Then the reproduction gate: identical bin set at K_bin as the
saved production IG list and saved mSCF1 to 1e-12.

Writes <run-root>/n12_reproduction/summary.json with status 'passed' or
'reproduction_failed' (exit 4). No n = 48 or 192 score is computed. The final
evaluation repeats every check on all three runs.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from evaluate_fair_scoring_baselines import read_saved_list
from evaluate_gate_d_pixel_counts import (
    code_paths,
    ig_ranking,
    max_relative_attribution_difference,
    reproduction_check,
    run_signature,
    sample_counts,
)
from evaluate_spatial_msipl_attributed_peaks import (
    load_correlations,
    read_h5_metadata,
    score_indices,
)
from spatial_msipl.provenance import (
    StaleResultError,
    atomic_write_json,
    check_existing,
    code_record,
    file_record,
    require_slurm,
)

CHECK_VERSION = 1
PASSED = "passed"
REPRODUCTION_FAILED = "reproduction_failed"


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path,
                        help="gate_d_pixel_counts/<section>_seed1/<arm> holding n12")
    parser.add_argument("--production-attribution-dir", required=True, type=Path)
    parser.add_argument("--saved-evaluation-dir", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--allow-outside-slurm", action="store_true",
                        help="tests only; real sections must run inside Slurm")
    return parser.parse_args()


def main():
    args = parse_arguments()
    require_slurm(args.allow_outside_slurm)
    started = time.perf_counter()
    dataset = args.input.stem
    arm = args.run_root.name
    output = args.run_root / "n12_reproduction"
    output.mkdir(parents=True, exist_ok=True)

    saved_summary_path = args.saved_evaluation_dir / "summary.json"
    saved_summary = json.loads(saved_summary_path.read_text(encoding="utf-8"))
    k_bin = int(saved_summary["matched_peak_evaluation"]["count"])
    saved_ig_mscf1 = float(saved_summary["matched_peak_evaluation"]["methods"]
                           ["integrated_gradients"]["mSCF1"])
    run_dir = args.run_root / "n12"
    source_paths = {
        "saved_evaluation_summary": saved_summary_path,
        "saved_ig_list": args.saved_evaluation_dir / f"ig_matched_{k_bin}_bins.csv",
        "production_coordinates_and_gmm":
            args.production_attribution_dir / "coordinates_and_gmm.npz",
        "production_attributions": args.production_attribution_dir / "attributions.npz",
        "n12_attributions": run_dir / "attributions.npz",
        "n12_coordinates_and_gmm": run_dir / "coordinates_and_gmm.npz",
        "n12_summary": run_dir / "summary.json",
    }
    expected = {
        "check_version": CHECK_VERSION,
        "dataset": dataset,
        "arm": arm,
        "input": file_record(args.input),
        "source_artifacts": {name: file_record(path) for name, path in source_paths.items()},
        "code": code_record(code_paths() + [Path(__file__).resolve()]),
    }
    summary_path = output / "summary.json"
    try:
        state = check_existing(summary_path, expected, PASSED)
    except StaleResultError as error:
        print(f"STALE: {error}", file=sys.stderr)
        raise SystemExit(3)
    if state == "valid":
        print(f"Existing result matches current provenance; skipped: {summary_path}")
        return

    mz, raw_labels, x, y, pixels_first = read_h5_metadata(args.input)
    n_bins = len(mz)

    run_summary = json.loads(source_paths["n12_summary"].read_text(encoding="utf-8"))
    if run_summary.get("status") != "valid":
        raise ValueError(f"n=12: IG run status is {run_summary.get('status')!r}, "
                         "not 'valid'; refusing to score incomplete attributions")
    alignment = run_summary.get("gmm_label_alignment") or {}
    if not alignment.get("enabled"):
        raise ValueError("n=12: run was not made with --align-gmm-labels-to-production; "
                         "all gate (d) runs must use the same code path")
    reference_sha256 = expected["source_artifacts"]["production_coordinates_and_gmm"]["sha256"]
    if (alignment.get("production_reference") or {}).get("sha256") != reference_sha256:
        raise ValueError("n=12: GMM labels were aligned to a different production "
                         "reference than the one this check compares against")
    signature = run_signature(run_summary)
    if signature["variant"] != arm or Path(signature["dataset"]).stem != dataset:
        raise ValueError("n=12: run summary dataset or arm does not match the request")
    gmm = np.load(source_paths["n12_coordinates_and_gmm"])
    if not (np.array_equal(gmm["x"], x) and np.array_equal(gmm["y"], y)):
        raise ValueError("n=12: coordinates do not match the HDF5 input")
    production_gmm = np.load(source_paths["production_coordinates_and_gmm"])
    if not np.array_equal(gmm["component"], production_gmm["component"]):
        raise ValueError("n=12: GMM assignment differs from production; the pixel "
                         "count would not be the only variable changed")
    counts = sample_counts(run_summary, 12)
    ranking = ig_ranking(np.load(source_paths["n12_attributions"]))

    correlations = load_correlations(args.input, raw_labels, n_bins, pixels_first,
                                     args.chunk_size)
    reproduction = reproduction_check(
        ranking[:k_bin], read_saved_list(source_paths["saved_ig_list"]),
        score_indices(ranking[:k_bin], correlations, n_bins)["mSCF1"], saved_ig_mscf1)
    reproduction["max_relative_attribution_difference"] = max_relative_attribution_difference(
        np.load(source_paths["n12_attributions"]),
        np.load(source_paths["production_attributions"]))

    result = {
        "status": PASSED if reproduction["passed"] else REPRODUCTION_FAILED,
        "provenance": expected,
        "K_bin": k_bin,
        "n12_reproduction": reproduction,
        "actual_attribution_pixels": counts,
        "run_signature": signature,
        "gmm_label_alignment": {key: alignment.get(key) for key in (
            "permutation", "identity", "max_posterior_diff", "production_reference")},
        "ig_runtime_seconds": run_summary.get("runtime_seconds"),
        "runtime_seconds": time.perf_counter() - started,
    }
    atomic_write_json(summary_path, result)
    if not reproduction["passed"]:
        print(f"REPRODUCTION FAILED: {reproduction['error']}", file=sys.stderr)
        raise SystemExit(4)
    print("n=12 REPRODUCTION PASSED")


if __name__ == "__main__":
    main()
