#!/usr/bin/env python
"""Tune legacy msiPL's post-training Beta to a target peak count.

This script loads an existing trained checkpoint. It does not retrain the VAE.
Beta controls only the LearnPeaks weight threshold:

    mean(weight) + Beta * standard_deviation(weight)

The selected Beta is the tested value whose peak count is closest to the
section-specific target used by the released S3PL evaluation configuration.
"""

from __future__ import print_function

import argparse
import csv
import json
import os

import numpy as np

from run_msipl_legacy_gbm import VAE_BN, LearnPeaks, load_dataset, tic_normalise


def beta_grid(start, stop, step):
    """Return an inclusive, numerically stable descending Beta grid."""
    if step <= 0:
        raise ValueError("Beta step must be positive")
    if start > stop:
        raise ValueError("Beta minimum must not exceed Beta maximum")
    count = int(round((stop - start) / step))
    values = [start + index * step for index in range(count + 1)]
    if values[-1] < stop - 1e-9:
        values.append(stop)
    return sorted(set(round(value, 10) for value in values), reverse=True)


def save_json(path, value):
    with open(path, "w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target-peaks", required=True, type=int)
    parser.add_argument("--tolerance", type=int, default=50)
    parser.add_argument("--beta-min", type=float, default=1.0)
    parser.add_argument("--beta-max", type=float, default=2.5)
    parser.add_argument("--beta-step", type=float, default=0.05)
    parser.add_argument("--latent-dim", type=int, default=5)
    parser.add_argument("--intermediate-dim", type=int, default=512)
    args = parser.parse_args()

    if args.target_peaks < 1:
        raise ValueError("Target peak count must be positive")
    if args.tolerance < 0:
        raise ValueError("Tolerance must be non-negative")
    if not os.path.isfile(args.weights):
        raise IOError("Checkpoint weights not found: {}".format(args.weights))
    if not os.path.isdir(args.output):
        os.makedirs(args.output)

    spectra_raw, mz, _, _ = load_dataset(args.input)
    spectra = tic_normalise(spectra_raw)
    standard_deviation = np.std(spectra, axis=0)
    mean_spectrum = np.mean(spectra, axis=0)

    builder = VAE_BN(
        nSpecFeatures=spectra.shape[1],
        intermediate_dim=args.intermediate_dim,
        latent_dim=args.latent_dim,
    )
    model, encoder = builder.get_architecture()
    model.load_weights(args.weights)
    encoder_weights = encoder.get_weights()

    records = []
    candidates = {}
    for beta in beta_grid(args.beta_min, args.beta_max, args.beta_step):
        _, learned_peaks, _, _ = LearnPeaks(
            mz,
            encoder_weights,
            standard_deviation,
            args.latent_dim,
            beta,
            mean_spectrum,
        )
        learned_peaks = np.asarray(learned_peaks, dtype=np.float64).reshape(-1)
        count = int(len(learned_peaks))
        difference = count - args.target_peaks
        records.append(
            {
                "beta": float(beta),
                "selected_peaks": count,
                "target_peaks": int(args.target_peaks),
                "difference": difference,
                "absolute_difference": abs(difference),
                "within_tolerance": abs(difference) <= args.tolerance,
            }
        )
        candidates[float(beta)] = learned_peaks
        print(
            "Beta {:.2f}: {} peaks (target {}, difference {:+d})".format(
                beta, count, args.target_peaks, difference
            )
        )

    # Prefer the closest count. If two values tie, prefer the larger Beta and
    # therefore the more conservative (higher) threshold.
    chosen = min(
        records,
        key=lambda item: (item["absolute_difference"], -item["beta"]),
    )
    chosen_peaks = candidates[chosen["beta"]]
    peaks_path = os.path.join(args.output, "learned_peaks.csv")
    np.savetxt(
        peaks_path,
        chosen_peaks,
        delimiter=",",
        header="mz_peak",
        comments="",
    )

    with open(os.path.join(args.output, "beta_sweep.csv"), "w") as stream:
        fieldnames = [
            "beta",
            "selected_peaks",
            "target_peaks",
            "difference",
            "absolute_difference",
            "within_tolerance",
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    summary = {
        "dataset": os.path.splitext(os.path.basename(args.input))[0],
        "purpose": "paper-aligned post-training msiPL peak-count tuning",
        "training_reused": True,
        "weights": os.path.abspath(args.weights),
        "target_peaks": int(args.target_peaks),
        "tolerance": int(args.tolerance),
        "tested_beta": {
            "minimum": float(args.beta_min),
            "maximum": float(args.beta_max),
            "step": float(args.beta_step),
        },
        "chosen": chosen,
        "status": "within_tolerance" if chosen["within_tolerance"] else "closest_outside_tolerance",
    }
    save_json(os.path.join(args.output, "beta_selection.json"), summary)
    print(json.dumps(summary, indent=2))
    print("Selected peaks saved to {}".format(peaks_path))


if __name__ == "__main__":
    main()
