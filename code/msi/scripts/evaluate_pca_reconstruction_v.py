#!/usr/bin/env python3
"""Predeclared Test V addendum: PCA reconstruction error for one section.

Uses Test V's exact measured pixels, float32 TIC preprocessing and PCA settings.
Primary metrics use the raw PCA inverse transform. Secondary metrics clip at
zero and apply the saved VAE evaluator's decoder-TIC convention. No labels,
segmentation, ranking, or mSCF1 scoring are performed here.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from spatial_msipl.provenance import (
    StaleResultError, atomic_write_json, check_existing, code_record, file_record,
    require_slurm,
)
from spatial_msipl.segmentation_control import (
    PCA_SEED, PREPROCESSING_RECORD, PRIMARY_COMPONENTS, SENSITIVITY_COMPONENTS,
    pca_transform, vae_centre_inputs,
)

VERSION = 1
COMPONENTS = (PRIMARY_COMPONENTS, SENSITIVITY_COMPONENTS)
EV_TOLERANCE = 1e-6
COMPLETE = "complete"
NOT_DONE = "not_done"
PROTOCOL = ("docs/research/18 Fair Scoring and Simple Baselines Protocol.md, "
            "Section 6.4 Test V addendum; supervisor chat 2026-10-17 20:17")


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--test-v-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--metric-chunk-size", type=int, default=256)
    parser.add_argument("--allow-outside-slurm", action="store_true", help="tests only")
    return parser.parse_args(argv)


def decoder_tic_normalize(values):
    """Match evaluate_spatial_reconstruction.py after its decoder call."""
    values = np.asarray(values)
    epsilon = np.finfo(np.float32).eps
    denominator = np.maximum(values.sum(axis=1, keepdims=True), epsilon)
    return np.clip(values / denominator, epsilon, 1.0 - epsilon)


def reconstruction_metrics(target, reconstruction, postprocess=False, chunk_size=256):
    """VAE-compatible averages: feature mean per pixel, then pixel mean."""
    target = np.asarray(target)
    reconstruction = np.asarray(reconstruction)
    if target.shape != reconstruction.shape or target.ndim != 2:
        raise ValueError("target and reconstruction must be equally shaped 2-D arrays")
    if chunk_size < 1:
        raise ValueError("metric chunk size must be positive")
    totals = {"mean_squared_error": 0.0, "mean_absolute_error": 0.0,
              "cosine_similarity": 0.0}
    epsilon = 1e-8  # torch.nn.functional.cosine_similarity default
    for start in range(0, len(target), chunk_size):
        stop = min(start + chunk_size, len(target))
        truth = target[start:stop]
        estimate = reconstruction[start:stop]
        if postprocess:
            estimate = decoder_tic_normalize(np.maximum(estimate, 0.0))
        difference = truth - estimate
        totals["mean_squared_error"] += float(np.square(difference).mean(axis=1).sum())
        totals["mean_absolute_error"] += float(np.abs(difference).mean(axis=1).sum())
        numerator = np.sum(truth * estimate, axis=1)
        denominator = np.maximum(np.linalg.norm(truth, axis=1), epsilon) * np.maximum(
            np.linalg.norm(estimate, axis=1), epsilon)
        totals["cosine_similarity"] += float(np.sum(numerator / denominator))
    return {name: value / len(target) for name, value in totals.items()}


def pca_reconstruction(inputs, n_components, metric_chunk_size=256):
    pca, scores = pca_transform(inputs, n_components)
    reconstruction = pca.inverse_transform(scores)
    ratio_sum = float(np.sum(pca.explained_variance_ratio_))
    metrics = {
        "primary_raw_inverse_transform": reconstruction_metrics(
            inputs, reconstruction, chunk_size=metric_chunk_size),
        "secondary_clip_zero_then_tic": reconstruction_metrics(
            inputs, reconstruction, postprocess=True, chunk_size=metric_chunk_size),
    }
    return metrics, ratio_sum


def main(argv=None):
    args = parse_arguments(argv)
    require_slurm(args.allow_outside_slurm)
    saved = json.loads(args.test_v_summary.read_text(encoding="utf-8"))
    dataset = args.input.stem
    if saved.get("status") != COMPLETE or saved.get("dataset") != dataset:
        raise SystemExit("PCA reconstruction refused: Test V summary is incomplete or mismatched")
    actual_input = file_record(args.input)
    saved_input = saved.get("provenance", {}).get("source_artifacts", {}).get("input", {})
    if actual_input["sha256"] != saved_input.get("sha256"):
        raise SystemExit("PCA reconstruction refused: input differs from saved Test V input")
    source = {"input": actual_input, "test_v_summary": file_record(args.test_v_summary)}
    expected = {
        "version": VERSION, "protocol": PROTOCOL, "dataset": dataset,
        "parameters": {"components": list(COMPONENTS), "pca_solver": "randomized",
                       "pca_random_state": PCA_SEED, "preprocessing": PREPROCESSING_RECORD,
                       "explained_variance_tolerance": EV_TOLERANCE,
                       "metric_chunk_size": args.metric_chunk_size,
                       "primary": "raw inverse_transform",
                       "secondary": "clip at zero, then decoder-style TIC normalisation"},
        "source_artifacts": source,
        "code": code_record([Path(__file__).resolve(),
                             Path(sys.modules["spatial_msipl.segmentation_control"].__file__).resolve()]),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    summary_path = args.output / "summary.json"
    try:
        if check_existing(summary_path, expected, COMPLETE) == "valid":
            print(f"Existing result matches current provenance; skipped: {summary_path}")
            return
    except StaleResultError as error:
        print(f"STALE: {error}", file=sys.stderr)
        raise SystemExit(3)

    inputs = vae_centre_inputs(args.input)
    results, checks = {}, {}
    gate_passed = True
    for n_components in COMPONENTS:
        metrics, ratio_sum = pca_reconstruction(inputs, n_components, args.metric_chunk_size)
        saved_sum = float(saved["pca"][f"pca{n_components}"]["explained_variance_ratio_sum"])
        difference = abs(ratio_sum - saved_sum)
        checks[f"pca{n_components}"] = {
            "actual": ratio_sum, "saved_test_v": saved_sum,
            "absolute_difference": difference, "tolerance": EV_TOLERANCE,
            "passed": bool(difference <= EV_TOLERANCE),
        }
        results[f"pca{n_components}"] = metrics
        gate_passed &= difference <= EV_TOLERANCE
    record = {"status": COMPLETE if gate_passed else NOT_DONE,
              "provenance": expected, "dataset": dataset, "pixels": int(inputs.shape[0]),
              "spectral_bins": int(inputs.shape[1]), "explained_variance_gate": checks}
    if gate_passed:
        record["metrics"] = results
    else:
        record["not_done_reason"] = (
            "explained-variance-ratio sum did not reproduce saved Test V within 1e-6")
    atomic_write_json(summary_path, record)
    print(f"PCA reconstruction {record['status']} for {dataset}")


if __name__ == "__main__":
    main()
