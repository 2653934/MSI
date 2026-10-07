#!/usr/bin/env python3
"""Recompute saved GMM posteriors and IG peak order without model execution.

Uses NumPy and the saved latent means, full covariances, attribution arrays,
and matched-peak CSVs. It never reads expert masks or modifies model artifacts.
"""

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np


BASELINE_ATTRIBUTION_ROOTS = {
    "spatial_msipl_attributed_peak_evaluation": "spatial_msipl_gmm_integrated_gradients",
    "spatial_msipl_cac_attributed_peak_evaluation": "spatial_msipl_cac_gmm_integrated_gradients",
}


def attribution_path(evaluation_relative):
    parts = list(evaluation_relative.parts)
    if len(parts) < 4 or parts[:2] != ["results", "experiments"] or ".." in parts:
        raise ValueError(f"unexpected evaluation path: {evaluation_relative}")
    if parts[-1] == "peak_evaluation":
        parts[-1] = "attribution"
    elif parts[2] in BASELINE_ATTRIBUTION_ROOTS:
        parts[2] = BASELINE_ATTRIBUTION_ROOTS[parts[2]]
    else:
        raise ValueError(f"cannot locate attribution for {evaluation_relative}")
    return Path(*parts)


def independent_gmm_posterior(latent, parameters):
    """Evaluate full Gaussian densities from covariances, not precision factors."""
    mean = np.asarray(parameters["scaler_mean"], dtype=np.float64)
    scale = np.asarray(parameters["scaler_scale"], dtype=np.float64)
    weights = np.asarray(parameters["mixture_weights"], dtype=np.float64)
    component_means = np.asarray(parameters["component_means"], dtype=np.float64)
    covariances = np.asarray(parameters["covariances"], dtype=np.float64)
    if np.any(scale <= 0) or np.any(weights <= 0) or not np.isclose(weights.sum(), 1.0, atol=1e-5):
        raise ValueError("invalid saved scaler or mixture weights")
    z = (np.asarray(latent, dtype=np.float64) - mean) / scale
    components, dimensions = component_means.shape
    if z.ndim != 2 or z.shape[1] != dimensions or covariances.shape != (components, dimensions, dimensions):
        raise ValueError("GMM parameter dimensions do not match latent means")
    log_density = np.empty((len(z), components), dtype=np.float64)
    for component in range(components):
        covariance = covariances[component]
        sign, log_determinant = np.linalg.slogdet(covariance)
        if sign <= 0:
            raise ValueError(f"component {component} has a non-positive covariance determinant")
        delta = z - component_means[component]
        inverse = np.linalg.inv(covariance)
        distance = np.einsum("ni,ij,nj->n", delta, inverse, delta)
        log_density[:, component] = (
            math.log(weights[component])
            - 0.5 * (dimensions * math.log(2 * math.pi) + log_determinant + distance)
        )
    stabilized = np.exp(log_density - log_density.max(axis=1, keepdims=True))
    return stabilized / stabilized.sum(axis=1, keepdims=True)


def independent_balanced_order(component_scores, count):
    """Interleave descending component lists and skip bins already emitted."""
    order = {component: np.argsort(scores)[::-1]
             for component, scores in component_scores.items()}
    positions = {component: 0 for component in order}
    selected, sources, seen = [], [], set()
    while len(selected) < count:
        added = False
        for component in sorted(order):
            ranking = order[component]
            while positions[component] < len(ranking) and int(ranking[positions[component]]) in seen:
                positions[component] += 1
            if positions[component] == len(ranking):
                continue
            index = int(ranking[positions[component]])
            positions[component] += 1
            seen.add(index)
            selected.append(index)
            sources.append(component)
            added = True
            if len(selected) == count:
                break
        if not added:
            raise ValueError("component rankings do not cover the selected peak count")
    return np.asarray(selected), np.asarray(sources)


def audit_one(project_root, evaluation_relative):
    evaluation = project_root / evaluation_relative
    attribution = project_root / attribution_path(evaluation_relative)
    with np.load(attribution / "gmm_parameters.npz", allow_pickle=False) as parameters:
        latent = np.load(attribution / "latent_mean.npy", allow_pickle=False)
        posterior = independent_gmm_posterior(latent, parameters)
    with np.load(attribution / "coordinates_and_gmm.npz", allow_pickle=False) as saved_gmm:
        labels = saved_gmm["component"].astype(np.int64)
        confidence = saved_gmm["assigned_posterior"].astype(np.float64)
    if len(labels) != len(latent) or np.any(labels < 0) or np.any(labels >= posterior.shape[1]):
        raise ValueError("saved GMM labels do not match the latent array")
    predicted = posterior.argmax(axis=1)
    maximum_posterior_error = float(np.max(np.abs(posterior[np.arange(len(labels)), labels] - confidence)))
    label_disagreements = int(np.count_nonzero(predicted != labels))

    attribution_summary = json.loads((attribution / "summary.json").read_text(encoding="utf-8"))
    diagnostics = attribution_summary["integrated_gradients"]["per_pixel_diagnostics"]
    residuals = np.asarray([abs(float(row["completeness_residual"])) for row in diagnostics])
    normalized = np.asarray([
        abs(float(row["completeness_residual"])) / max(abs(float(row["score_delta"])), 1e-4)
        for row in diagnostics
    ])
    reported_completeness = attribution_summary["integrated_gradients"]["completeness"]
    recomputed_completeness = {
        "median_absolute_residual": float(np.median(residuals)),
        "maximum_absolute_residual": float(np.max(residuals)),
        "median_normalized_residual": float(np.median(normalized)),
        "percentile_95_normalized_residual": float(np.percentile(normalized, 95)),
    }
    diagnostic_identity_error = max(
        abs(float(row["score_delta"]) - (float(row["input_score"]) - float(row["baseline_score"])))
        + abs(float(row["completeness_residual"]) -
              (float(row["score_delta"]) - float(row["attribution_sum"])))
        for row in diagnostics
    )
    completeness_summary_error = max(
        abs(value - float(reported_completeness[key]))
        for key, value in recomputed_completeness.items()
    )

    with np.load(attribution / "attributions.npz", allow_pickle=False) as arrays:
        mz = np.asarray(arrays["mz"], dtype=np.float64)
        component_scores = {
            component: np.asarray(arrays[f"component_{component}_combined_absolute_mean"], dtype=np.float64)
            for component in range(posterior.shape[1])
        }
        combination_error = max(
            float(np.max(np.abs(
                component_scores[component]
                - np.asarray(arrays[f"component_{component}_central_absolute_mean"], dtype=np.float64)
                - np.asarray(arrays[f"component_{component}_context_absolute_mean"], dtype=np.float64)
            )))
            for component in component_scores
        )
    csv_paths = list(evaluation.glob("ig_matched_*_bins.csv"))
    if len(csv_paths) != 1:
        raise ValueError(f"expected one matched IG peak CSV: {evaluation}")
    with csv_paths[0].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    expected_indices, expected_sources = independent_balanced_order(component_scores, len(rows))
    saved_indices = np.asarray([int(row["bin_index"]) for row in rows])
    saved_sources = np.asarray([int(row["source_component"]) for row in rows])
    normalized_scores = np.maximum.reduce([
        scores / max(float(scores.max()), np.finfo(float).eps)
        for scores in component_scores.values()
    ])
    csv_score_error = max(abs(float(row["score"]) - normalized_scores[int(index)])
                          for row, index in zip(rows, saved_indices))
    csv_mz_error = max(abs(float(row["mz"]) - mz[int(index)])
                       for row, index in zip(rows, saved_indices))
    score_summary = json.loads((evaluation / "summary.json").read_text(encoding="utf-8"))
    expected_count = int(score_summary["matched_peak_evaluation"]["count"])
    discrepancies = []
    if label_disagreements:
        discrepancies.append("GMM component labels")
    if maximum_posterior_error > 1e-4:
        discrepancies.append("GMM assigned posterior")
    if diagnostic_identity_error > 1e-5 or completeness_summary_error > 1e-8:
        discrepancies.append("IG completeness arithmetic")
    if not reported_completeness["passed"]:
        discrepancies.append("IG completeness criterion")
    if combination_error > 1e-5:
        discrepancies.append("central/context absolute IG combination")
    if not np.array_equal(expected_indices, saved_indices):
        discrepancies.append("IG balanced peak order")
    if not np.array_equal(expected_sources, saved_sources):
        discrepancies.append("IG source component")
    if csv_score_error > 1e-6 or csv_mz_error > 1e-6:
        discrepancies.append("IG CSV score or m/z")
    if len(rows) != expected_count or len(set(saved_indices)) != len(rows):
        discrepancies.append("matched peak count or uniqueness")
    return {
        "evaluation_dir": evaluation_relative.as_posix(),
        "attribution_dir": attribution_path(evaluation_relative).as_posix(),
        "pixels": len(labels), "selected_peaks": len(rows),
        "gmm_label_disagreements": label_disagreements,
        "maximum_assigned_posterior_error": maximum_posterior_error,
        "maximum_ig_diagnostic_identity_error": diagnostic_identity_error,
        "maximum_ig_completeness_summary_error": completeness_summary_error,
        "maximum_combined_absolute_ig_error": combination_error,
        "ig_peak_order_matches": bool(np.array_equal(expected_indices, saved_indices)),
        "ig_source_components_match": bool(np.array_equal(expected_sources, saved_sources)),
        "maximum_csv_score_error": csv_score_error,
        "maximum_csv_mz_error": csv_mz_error,
        "discrepancies": discrepancies,
        "status": "valid" if not discrepancies else "mismatch",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    project_root = args.project_root.absolute()
    if not project_root.is_dir():
        raise FileNotFoundError(project_root)
    score_root = project_root / "results/diagnostics/spatial_score_foundation"
    reports = sorted(score_root.glob("*.json"))
    if len(reports) != 16:
        raise ValueError(f"expected 16 section scoring reports; found {len(reports)}")
    records = []
    for report in reports:
        scoring = json.loads(report.read_text(encoding="utf-8"))
        if scoring["status"] != "valid":
            raise ValueError(f"scoring audit is not valid: {report}")
        for evaluation in scoring["evaluations"]:
            relative = Path(evaluation["evaluation_dir"])
            records.append(audit_one(project_root, relative))
            print(f"{report.stem}: {relative.name}: {records[-1]['status']}", flush=True)
    result = {
        "status": "valid" if all(row["status"] == "valid" for row in records) else "mismatch",
        "evaluation_count": len(records),
        "records": records,
        "limitations": [
            "Recomputes GMM posteriors from saved latent means and covariances; does not refit the GMM.",
            "Checks saved IG completeness arithmetic and aggregate peak order; does not rerun IG through the trained checkpoint.",
            "Does not validate the biological meaning of GMM components or peak reference labels.",
        ],
    }
    output = args.output or project_root / "results/diagnostics/spatial_ig_ranking_provenance/summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "evaluation_count": len(records),
                      "mismatches": [row["evaluation_dir"] for row in records
                                     if row["status"] != "valid"],
                      "output": str(output)}, indent=2), flush=True)
    if result["status"] != "valid":
        raise SystemExit("saved GMM/IG ranking audit found mismatches")


if __name__ == "__main__":
    main()
