#!/usr/bin/env python3
"""Independently recompute saved window-arm PCC and mSCF1 from raw HDF5.

This reads the spectra once, but does not load a model or rerun attribution.
The expert labels are used only to construct the evaluation reference sets.
"""

import argparse
import csv
import json
from pathlib import Path

import h5py
import numpy as np


THRESHOLDS = (0.3, 0.4, 0.5, 0.6)


def correlations_from_h5(path, chunk_size):
    with h5py.File(path, "r") as handle:
        labels = np.asarray(handle["Class_Label"][:]).reshape(-1)
        mz_count = int(np.asarray(handle["mzArray"]).size)
        data = handle["Data"]
        pixels_first = data.shape == (len(labels), mz_count)
        if not pixels_first and data.shape != (mz_count, len(labels)):
            raise ValueError(f"unexpected Data shape: {data.shape}")
        classes = np.unique(labels)
        centred_masks = np.stack(
            [(labels == value).astype(np.float64) for value in classes], axis=1
        )
        centred_masks -= centred_masks.mean(axis=0, keepdims=True)
        mask_norm = np.sqrt(np.sum(centred_masks**2, axis=0))
        correlations = np.zeros((len(classes), mz_count), dtype=np.float64)
        for start in range(0, mz_count, chunk_size):
            end = min(start + chunk_size, mz_count)
            block = np.asarray(
                data[:, start:end] if pixels_first else data[start:end, :].T,
                dtype=np.float64,
            )
            block -= block.mean(axis=0, keepdims=True)
            numerator = centred_masks.T @ block
            denominator = mask_norm[:, None] * np.sqrt(
                np.sum(block**2, axis=0)
            )[None, :]
            np.divide(
                numerator,
                denominator,
                out=correlations[:, start:end],
                where=denominator > 0,
            )
    return classes, correlations


def threshold_reference_sets(correlations, threshold):
    """Replicate the stated S3PL closest-ranked-value cutoff independently."""
    class_sets = []
    for values in correlations:
        order = np.argsort(values)[::-1]
        boundary = int(np.argmin(np.abs(values[order] - threshold)))
        class_sets.append(set(order[:boundary].tolist()))
    return class_sets, set().union(*class_sets)


def counts_and_f1(selected, positive, spectral_bins):
    tp = len(selected & positive)
    fp = len(selected - positive)
    fn = len(positive - selected)
    tn = spectral_bins - tp - fp - fn
    denominator = 2 * tp + fp + fn
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "F1": 2 * tp / denominator if denominator else 0.0,
    }


def audit_evaluation(directory, classes, correlations):
    summary_path = directory / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    reported = summary["matched_peak_evaluation"]["methods"]["integrated_gradients"]
    csv_paths = list(directory.glob("ig_matched_*_bins.csv"))
    if len(csv_paths) != 1:
        raise ValueError(f"expected one matched IG CSV in {directory}")
    with csv_paths[0].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    selected_indices = [int(row["bin_index"]) for row in rows]
    selected = set(selected_indices)
    if len(selected) != len(rows) or len(selected) != int(reported["selected_bins"]):
        raise ValueError(f"selected peak count or uniqueness mismatch in {directory}")
    if any(index < 0 or index >= correlations.shape[1] for index in selected):
        raise ValueError(f"selected bin outside m/z axis in {directory}")

    pcc_max_error = max(
        abs(float(row[f"pcc_class_{int(label)}"]) - correlations[class_index, index])
        for row, index in zip(rows, selected_indices)
        for class_index, label in enumerate(classes)
    )
    results = {}
    discrepancies = []
    for threshold in THRESHOLDS:
        key = str(threshold)
        class_sets, mixed_set = threshold_reference_sets(correlations, threshold)
        computed = counts_and_f1(selected, mixed_set, correlations.shape[1])
        saved = reported["threshold_results"][key]
        for field, value in computed.items():
            if abs(value - saved["mixed_classes"][field]) > 1e-10:
                discrepancies.append(f"threshold {key} mixed {field}")
        if len(mixed_set) != saved["true_bins_mixed"]:
            discrepancies.append(f"threshold {key} mixed reference size")
        for class_index, label in enumerate(classes):
            class_computed = counts_and_f1(
                selected, class_sets[class_index], correlations.shape[1]
            )
            for field, value in class_computed.items():
                if abs(value - saved["class_metrics"][str(int(label))][field]) > 1e-10:
                    discrepancies.append(f"threshold {key} class {label} {field}")
        results[key] = {"mixed": computed, "true_bins_mixed": len(mixed_set)}
    mscf1 = float(np.mean([results[str(t)]["mixed"]["F1"] for t in THRESHOLDS]))
    if abs(mscf1 - reported["mSCF1"]) > 1e-10:
        discrepancies.append("mSCF1")
    if pcc_max_error > 1e-9:
        discrepancies.append("selected-bin PCC values")
    return {
        "evaluation_dir": str(directory),
        "selected_bins": len(selected),
        "recomputed_mSCF1": mscf1,
        "reported_mSCF1": reported["mSCF1"],
        "max_selected_bin_pcc_error": float(pcc_max_error),
        "thresholds": results,
        "discrepancies": discrepancies,
        "status": "valid" if not discrepancies else "mismatch",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("evaluation_dirs", type=Path, nargs="+")
    args = parser.parse_args()
    if args.chunk_size < 1:
        raise ValueError("chunk-size must be positive")

    classes, correlations = correlations_from_h5(args.input, args.chunk_size)
    evaluations = [
        audit_evaluation(directory, classes, correlations)
        for directory in args.evaluation_dirs
    ]
    result = {
        "source_h5": str(args.input),
        "classes": [int(value) for value in classes],
        "spectral_bins": int(correlations.shape[1]),
        "reference_rule": "rank each signed class PCC; select bins before the value closest to threshold; union classes",
        "evaluations": evaluations,
        "status": "valid" if all(item["status"] == "valid" for item in evaluations) else "mismatch",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "output": str(args.output),
        "evaluations": [
            {"path": item["evaluation_dir"], "status": item["status"],
             "mSCF1": item["recomputed_mSCF1"],
             "discrepancies": item["discrepancies"]}
            for item in evaluations
        ],
    }, indent=2), flush=True)
    if result["status"] != "valid":
        raise SystemExit("independent scoring audit found mismatches")


if __name__ == "__main__":
    main()
