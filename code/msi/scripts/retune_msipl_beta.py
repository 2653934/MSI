#!/usr/bin/env python
"""msiPL Beta re-tune (protocol 18 Section 6.8; supervisor chat 2026-10-30 12:58
item 2 and 17:33 ruling). Runs in the msipl_legacy environment (Python 3.6).

From the saved legacy msiPL weights (no retraining), one pass of LearnPeaks over
Beta -2.0 to 2.5 in steps of 0.01 (the existing tuner's beta_grid), then, for each
budget multiplier m, the list whose raw learned-peak count is closest to
target = int(round(K_bin * m)) (the expression of simple_baselines.budgets), ties
to the larger Beta, tolerance 50 (the existing tuner's rule). A target above the
grid's maximum count takes the maximum count (ties to the larger Beta) and is
labelled msipl_cap.

GBM/CAC (--saved-beta and --saved-peaks given): m = 1 is the saved list, which
defines K_bin. LearnPeaks is recomputed at the saved Beta and must reproduce the
saved learned_peaks.csv exactly; otherwise nothing but the check record is written
and the script exits 5. RCC (no saved list): m = 1 is re-selected like the others.

Outputs, in a new folder (refused if it holds a summary; exit 3): sweep.csv,
m<label>/learned_peaks.csv and m<label>/selection.json per multiplier, and
summary.json last.
"""
from __future__ import print_function

import argparse
import csv
import json
import os
import sys

import numpy as np

MULTIPLIERS = (0.5, 0.75, 1.0, 1.5, 2.0)
TOLERANCE = 50
GRID = (-2.0, 2.5, 0.01)
REPRODUCTION_EXIT = 5
EXISTS_EXIT = 3


def target_for(k_bin, multiplier):
    """Same expression as spatial_msipl.simple_baselines.budgets."""
    return int(round(k_bin * multiplier))


def select(records, target, tolerance=TOLERANCE):
    """The existing tuner's rule, plus the msipl_cap label (Section 6.8).

    records: dicts with "beta" and "selected_peaks". Returns (record, status).
    """
    if not records:
        raise ValueError("no sweep records")
    closest = min(records, key=lambda item: (abs(item["selected_peaks"] - target),
                                             -item["beta"]))
    if abs(closest["selected_peaks"] - target) <= tolerance:
        return closest, "within_tolerance"
    maximum = max(item["selected_peaks"] for item in records)
    if target > maximum:
        capped = max((item for item in records if item["selected_peaks"] == maximum),
                     key=lambda item: item["beta"])
        return capped, "msipl_cap"
    return closest, "closest_outside_tolerance"


def label(multiplier):
    return "m" + str(float(multiplier))


def save_json(path, value):
    with open(path, "w") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def save_peaks(path, peaks):
    # Same format as tune_msipl_massnet_beta.py.
    np.savetxt(path, peaks, delimiter=",", header="mz_peak", comments="")


def read_peaks(path):
    values = np.genfromtxt(path, delimiter=",", names=True)
    return np.asarray(values[values.dtype.names[0]], dtype=np.float64).reshape(-1)


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--k-bin", required=True, type=int)
    parser.add_argument("--saved-beta", type=float, default=None,
                        help="GBM/CAC: the saved chosen Beta (m = 1 is the saved list)")
    parser.add_argument("--saved-peaks", default=None,
                        help="GBM/CAC: the saved learned_peaks.csv")
    parser.add_argument("--latent-dim", type=int, default=5)
    parser.add_argument("--intermediate-dim", type=int, default=512)
    args = parser.parse_args()
    if (args.saved_beta is None) != (args.saved_peaks is None):
        parser.error("--saved-beta and --saved-peaks go together")
    if args.k_bin < 1:
        parser.error("--k-bin must be positive")
    return args


def main():
    args = parse_arguments()
    if os.path.exists(os.path.join(args.output, "summary.json")) or \
            os.path.exists(os.path.join(args.output, "sweep.csv")):
        print("Output exists: {} (never overwritten)".format(args.output), file=sys.stderr)
        return EXISTS_EXIT
    if not os.path.isfile(args.weights):
        raise IOError("Checkpoint weights not found: {}".format(args.weights))
    # Heavy imports here (TensorFlow via the legacy model), so select() is testable alone.
    from run_msipl_legacy_gbm import VAE_BN, LearnPeaks, load_dataset, tic_normalise
    from tune_msipl_massnet_beta import beta_grid

    if not os.path.isdir(args.output):
        os.makedirs(args.output)
    spectra_raw, mz, _, _ = load_dataset(args.input)
    spectra = tic_normalise(spectra_raw)
    standard_deviation = np.std(spectra, axis=0)
    mean_spectrum = np.mean(spectra, axis=0)
    builder = VAE_BN(nSpecFeatures=spectra.shape[1], intermediate_dim=args.intermediate_dim,
                     latent_dim=args.latent_dim)
    model, encoder = builder.get_architecture()
    model.load_weights(args.weights)
    encoder_weights = encoder.get_weights()

    def learn(beta):
        _, peaks, _, _ = LearnPeaks(mz, encoder_weights, standard_deviation, args.latent_dim,
                                    beta, mean_spectrum)
        return np.asarray(peaks, dtype=np.float64).reshape(-1)

    reproduction = None
    if args.saved_beta is not None:
        recomputed = learn(args.saved_beta)
        saved = read_peaks(args.saved_peaks)
        same_shape = recomputed.shape == saved.shape
        reproduction = {
            "saved_beta": args.saved_beta,
            "saved_peaks": os.path.abspath(args.saved_peaks),
            "saved_count": int(saved.size),
            "recomputed_count": int(recomputed.size),
            "identical": bool(same_shape and np.array_equal(recomputed, saved)),
            "max_abs_mz_difference": (float(np.max(np.abs(recomputed - saved)))
                                      if same_shape and saved.size else None),
        }
        if not reproduction["identical"]:
            save_json(os.path.join(args.output, "m1_reproduction.json"), reproduction)
            print("m = 1 does not reproduce the saved list: stop and post", file=sys.stderr)
            return REPRODUCTION_EXIT

    records, candidates = [], {}
    for beta in beta_grid(GRID[0], GRID[1], GRID[2]):
        peaks = learn(beta)
        records.append({"beta": float(beta), "selected_peaks": int(peaks.size)})
        candidates[float(beta)] = peaks
    with open(os.path.join(args.output, "sweep.csv"), "w") as stream:
        writer = csv.DictWriter(stream, fieldnames=("beta", "selected_peaks"))
        writer.writeheader()
        writer.writerows(records)

    selections = {}
    for multiplier in MULTIPLIERS:
        target = target_for(args.k_bin, multiplier)
        folder = os.path.join(args.output, label(multiplier))
        os.makedirs(folder)
        if multiplier == 1.0 and reproduction is not None:
            chosen = {"beta": args.saved_beta, "selected_peaks": reproduction["saved_count"]}
            status, peaks = "saved_list_reproduced", recomputed
        else:
            chosen, status = select(records, target)
            peaks = candidates[chosen["beta"]]
        save_peaks(os.path.join(folder, "learned_peaks.csv"), peaks)
        selection = {"multiplier": multiplier, "target_peaks": target, "K_bin": args.k_bin,
                     "beta": chosen["beta"], "selected_peaks": chosen["selected_peaks"],
                     "difference": chosen["selected_peaks"] - target,
                     "tolerance": TOLERANCE, "status": status}
        save_json(os.path.join(folder, "selection.json"), selection)
        selections[label(multiplier)] = selection
        print("{}: target {} -> Beta {} with {} peaks ({})".format(
            label(multiplier), target, chosen["beta"], chosen["selected_peaks"], status))

    counts = [item["selected_peaks"] for item in records]
    summary = {
        "status": "complete",
        "protocol": "protocol 18 Section 6.8 (msiPL Beta re-tune)",
        "dataset": os.path.splitext(os.path.basename(args.input))[0],
        "input": os.path.abspath(args.input),
        "weights": os.path.abspath(args.weights),
        "training_reused": True,
        "K_bin": args.k_bin,
        "grid": {"minimum": GRID[0], "maximum": GRID[1], "step": GRID[2],
                 "values": len(records)},
        "count_range_on_grid": {"minimum": min(counts), "maximum": max(counts)},
        "selection_rule": ("closest raw learned-peak count, ties to the larger Beta, "
                           "tolerance 50; target above the grid maximum -> maximum count, "
                           "msipl_cap"),
        "m1_reproduction": reproduction,
        "selections": selections,
    }
    save_json(os.path.join(args.output, "summary.json"), summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
