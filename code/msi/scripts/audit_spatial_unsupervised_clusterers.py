#!/usr/bin/env python3
"""Compare predeclared clusterers on frozen spatial-msiPL latent vectors.

GMM covariance types are selected by BIC alone. Expert labels are read only
after fitting and selection, for post-hoc interpretation. K-means is a
geometry check, not a drop-in replacement for posterior-based attribution.
"""

import argparse
import json
from itertools import combinations
from pathlib import Path

import h5py
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler


GMM_COVARIANCES = ("full", "tied", "diag", "spherical")
SEEDS = (1, 2, 3)


def fit_candidates(latent, components, seeds=SEEDS, n_init=20):
    """Fit/select without expert labels; return records with predictions."""
    standardized = StandardScaler().fit_transform(np.asarray(latent))
    if standardized.ndim != 2 or not np.all(np.isfinite(standardized)):
        raise ValueError("latent matrix must be finite and two-dimensional")
    if components < 2 or components > len(standardized):
        raise ValueError("invalid predeclared component count")
    records = []
    for covariance in GMM_COVARIANCES:
        for seed in seeds:
            model = GaussianMixture(
                n_components=components, covariance_type=covariance,
                n_init=n_init, random_state=int(seed),
            ).fit(standardized)
            records.append({
                "method": f"gmm_{covariance}",
                "seed": int(seed),
                "bic": float(model.bic(standardized)),
                "component_counts": np.bincount(
                    model.predict(standardized), minlength=components
                ).astype(int).tolist(),
                "predicted": model.predict(standardized),
            })
    for seed in seeds:
        model = KMeans(
            n_clusters=components, n_init=n_init, random_state=int(seed)
        ).fit(standardized)
        records.append({
            "method": "kmeans",
            "seed": int(seed),
            "inertia": float(model.inertia_),
            "component_counts": np.bincount(
                model.labels_, minlength=components
            ).astype(int).tolist(),
            "predicted": model.labels_,
        })
    gmm_records = [record for record in records if record["method"].startswith("gmm_")]
    selected = min(gmm_records, key=lambda record: record["bic"])
    return records, selected


def summarize_records(records, selected, labels, saved_components):
    """Attach label diagnostics only after unsupervised fitting and selection."""
    labels = np.asarray(labels).reshape(-1)
    saved_components = np.asarray(saved_components).reshape(-1)
    if any(len(record["predicted"]) != len(labels) for record in records):
        raise ValueError("predictions and labels differ in length")
    output = []
    for record in records:
        public = {key: value for key, value in record.items() if key != "predicted"}
        public["expert_class_ari_posthoc"] = float(
            adjusted_rand_score(labels, record["predicted"])
        )
        public["agreement_with_saved_gmm_ari"] = float(
            adjusted_rand_score(saved_components, record["predicted"])
        )
        output.append(public)
    methods = sorted({record["method"] for record in records})
    stability = {}
    for method in methods:
        predictions = [
            record["predicted"] for record in records if record["method"] == method
        ]
        stability[method] = float(np.mean([
            adjusted_rand_score(left, right)
            for left, right in combinations(predictions, 2)
        ])) if len(predictions) > 1 else None
    return {
        "selected_gmm_by_bic": {
            "method": selected["method"],
            "seed": selected["seed"],
            "bic": selected["bic"],
            "expert_class_ari_posthoc": float(
                adjusted_rand_score(labels, selected["predicted"])
            ),
        },
        "saved_full_gmm_expert_class_ari": float(
            adjusted_rand_score(labels, saved_components)
        ),
        "seed_stability_mean_pairwise_ari": stability,
        "candidates": output,
    }


def audit(input_path, attribution_dirs, output_path):
    with h5py.File(input_path, "r") as handle:
        x = np.asarray(handle["xLocation"][:]).reshape(-1)
        y = np.asarray(handle["yLocation"][:]).reshape(-1)
        expert_labels = np.asarray(handle["Class_Label"][:]).reshape(-1)
    results = {}
    for condition, directory in attribution_dirs.items():
        summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
        if summary.get("status") not in ("valid", "valid_pilot"):
            raise ValueError(f"attribution is not valid: {directory}")
        latent = np.load(directory / "latent_mean.npy", allow_pickle=False)
        with np.load(directory / "coordinates_and_gmm.npz", allow_pickle=False) as saved:
            if not np.array_equal(saved["x"], x) or not np.array_equal(saved["y"], y):
                raise ValueError(f"coordinates differ from source HDF5: {directory}")
            saved_components = saved["component"].copy()
        component_count = int(summary["gmm"]["components"])
        records, selected = fit_candidates(latent, component_count)
        results[condition] = summarize_records(
            records, selected, expert_labels, saved_components
        )
        results[condition]["component_count"] = component_count
        results[condition]["attribution_dir"] = str(directory)
        results[condition]["model_state_sha256"] = summary["model_state_sha256"]
    result = {
        "status": "valid",
        "dataset": input_path.stem,
        "source_h5": str(input_path),
        "selection_rule": "minimum BIC over predeclared full/tied/diag/spherical GMMs and seeds 1-3; no expert labels used",
        "kmeans_role": "geometry diagnostic only; inertia is not compared with GMM BIC",
        "interpretation_limit": (
            "Expert-class ARI is post hoc on training sections, not a model "
            "selection criterion or patient-independent validation. Changing "
            "the GMM would require a fresh attribution and peak evaluation."
        ),
        "conditions": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--real-attribution", type=Path, required=True)
    parser.add_argument("--shuffled-attribution", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.input, {
        "real": args.real_attribution,
        "shuffled": args.shuffled_attribution,
    }, args.output)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
