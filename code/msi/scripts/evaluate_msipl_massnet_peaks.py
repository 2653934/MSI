#!/usr/bin/env python
"""Score legacy msiPL peaks with the S3PL PCC-threshold mSCF1 protocol."""

from __future__ import print_function

import argparse
import json
import os

import h5py
import numpy as np


THRESHOLDS = (0.3, 0.4, 0.5, 0.6)


def nearest_unique_indices(mz_axis, picked_mz):
    positions = np.searchsorted(mz_axis, picked_mz)
    positions = np.clip(positions, 0, len(mz_axis) - 1)
    left = np.maximum(positions - 1, 0)
    use_left = np.abs(mz_axis[left] - picked_mz) <= np.abs(
        mz_axis[positions] - picked_mz
    )
    positions[use_left] = left[use_left]
    return np.unique(positions.astype(np.int64))


def pearson_by_feature(data, mask, pixels_first, chunk_size):
    centred_mask = np.asarray(mask, dtype=np.float64)
    centred_mask -= centred_mask.mean()
    mask_norm = np.sqrt(np.dot(centred_mask, centred_mask))
    n_features = data.shape[1] if pixels_first else data.shape[0]
    correlations = np.zeros(n_features, dtype=np.float64)
    if mask_norm == 0:
        return correlations

    for start in range(0, n_features, chunk_size):
        stop = min(start + chunk_size, n_features)
        if pixels_first:
            values = np.asarray(data[:, start:stop], dtype=np.float64)
        else:
            values = np.asarray(data[start:stop, :], dtype=np.float64).T
        values -= values.mean(axis=0, keepdims=True)
        denominator = mask_norm * np.sqrt(np.sum(values * values, axis=0))
        numerator = np.dot(centred_mask, values)
        np.divide(
            numerator,
            denominator,
            out=correlations[start:stop],
            where=denominator != 0,
        )
    return correlations


def true_indices_at_threshold(correlations, threshold):
    ranking = np.argsort(correlations)[::-1]
    # This deliberately matches S3PL PeakEvaluation: find the ranked value
    # closest to the PCC threshold, then treat all preceding bins as positive.
    count = int(np.argmin(np.abs(correlations[ranking] - threshold)))
    return set(ranking[:count].tolist())


def classification_metrics(picked, positive, total_features):
    picked = set(picked)
    positive = set(positive)
    true_positive = len(picked & positive)
    false_positive = len(picked - positive)
    false_negative = len(positive - picked)
    true_negative = total_features - true_positive - false_positive - false_negative
    recall = (
        float(true_positive) / (true_positive + false_negative)
        if true_positive + false_negative
        else 0.0
    )
    precision = (
        float(true_positive) / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0
    )
    denominator = 2 * true_positive + false_positive + false_negative
    f1 = float(2 * true_positive) / denominator if denominator else 0.0
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
        "recall": recall,
        "precision": precision,
        "F1": f1,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--peaks", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--chunk-size", type=int, default=2048)
    args = parser.parse_args()

    if args.chunk_size < 1:
        raise ValueError("chunk size must be positive")
    if not os.path.isdir(args.output):
        os.makedirs(args.output)

    picked_mz = np.genfromtxt(args.peaks, delimiter=",", names=True)
    if picked_mz.dtype.names:
        picked_mz = np.asarray(picked_mz[picked_mz.dtype.names[0]]).reshape(-1)
    else:
        picked_mz = np.asarray(picked_mz).reshape(-1)

    with h5py.File(args.input, "r") as handle:
        required = ("Data", "mzArray", "Class_Label")
        missing = [name for name in required if name not in handle]
        if missing:
            raise KeyError("missing HDF5 datasets: {}".format(missing))
        mz_axis = np.asarray(handle["mzArray"], dtype=np.float64).reshape(-1)
        raw_labels = np.asarray(handle["Class_Label"], dtype=np.int64).reshape(-1)
        data = handle["Data"]
        pixels_first = data.shape == (len(raw_labels), len(mz_axis))
        mz_first = data.shape == (len(mz_axis), len(raw_labels))
        if not pixels_first and not mz_first:
            raise ValueError("cannot orient Data shape {}".format(data.shape))
        if set(np.unique(raw_labels).tolist()) != set((1, 2)):
            raise ValueError("expected MassNet labels 1 normal and 2 tumour")

        correlations = {}
        for class_id in (0, 1):
            binary_mask = (raw_labels == class_id + 1).astype(np.uint8)
            correlations[class_id] = pearson_by_feature(
                data, binary_mask, pixels_first, args.chunk_size
            )

    picked_indices = nearest_unique_indices(mz_axis, picked_mz)
    threshold_results = {}
    mixed_f1 = []
    for threshold in THRESHOLDS:
        class_true = {
            class_id: true_indices_at_threshold(correlations[class_id], threshold)
            for class_id in (0, 1)
        }
        mixed_true = class_true[0] | class_true[1]
        mixed = classification_metrics(picked_indices, mixed_true, len(mz_axis))
        mixed_f1.append(mixed["F1"])
        threshold_results[str(threshold)] = {
            "class_metrics": {
                "normal": classification_metrics(
                    picked_indices, class_true[0], len(mz_axis)
                ),
                "tumour": classification_metrics(
                    picked_indices, class_true[1], len(mz_axis)
                ),
            },
            "mixed_classes": mixed,
            "true_bins_mixed": len(mixed_true),
        }

    result = {
        "dataset": os.path.splitext(os.path.basename(args.input))[0],
        "method": "legacy msiPL VAE-BN plus LearnPeaks",
        "evaluation": "S3PL-compatible PCC-threshold peak classification",
        "thresholds": list(THRESHOLDS),
        "spectral_bins": len(mz_axis),
        "reported_peaks": int(len(picked_mz)),
        "unique_nearest_bins": int(len(picked_indices)),
        "threshold_results": threshold_results,
        "mixed_f1": {
            str(threshold): score
            for threshold, score in zip(THRESHOLDS, mixed_f1)
        },
        "mSCF1": float(np.mean(mixed_f1)),
        "status": "complete",
    }
    metrics_path = os.path.join(args.output, "peak_metrics.json")
    with open(metrics_path, "w") as handle:
        json.dump(result, handle, indent=2)

    text_path = os.path.join(args.output, "peak_evaluation.txt")
    with open(text_path, "w") as handle:
        handle.write("legacy msiPL peak evaluation\n")
        handle.write("picked peaks = {}\n".format(len(picked_indices)))
        for threshold, score in zip(THRESHOLDS, mixed_f1):
            handle.write("F1 {} = {:.6f}\n".format(threshold, score))
        handle.write("mSCF1 = {:.6f}\n".format(result["mSCF1"]))

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
