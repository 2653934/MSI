#!/usr/bin/env python3
"""Distinguish latent class separability from GMM fitting instability.

This is a post-hoc diagnostic. Expert labels are never used to fit the VAE or
the unsupervised GMM. The label-trained linear probe is NOT a peak method or a
generalization estimate: random pixel folds share the same tissue section.
"""

import argparse
import json
from pathlib import Path

import h5py
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import adjusted_rand_score, balanced_accuracy_score
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def neighbour_label_purity(standardized, labels, neighbours=10):
    count = min(neighbours + 1, len(labels))
    indices = NearestNeighbors(n_neighbors=count).fit(standardized).kneighbors(
        standardized, return_distance=False
    )
    other = indices[:, 1:]
    if other.size == 0:
        return None
    return float(np.mean(labels[other] == labels[:, None]))


def evaluate_latent(latent, labels, saved_components, seeds=(1, 2, 3, 4, 5),
                    gmm_n_init=20):
    latent = np.asarray(latent)
    labels = np.asarray(labels).reshape(-1)
    saved_components = np.asarray(saved_components).reshape(-1)
    if (latent.ndim != 2 or len(latent) != len(labels)
            or len(saved_components) != len(labels)
            or not np.all(np.isfinite(latent))):
        raise ValueError("latent, class labels, and saved components do not align")
    classes, counts = np.unique(labels, return_counts=True)
    if len(classes) < 2 or int(counts.min()) < 5:
        raise ValueError("five-fold probe needs at least five pixels per class")
    standardized = StandardScaler().fit_transform(latent)
    saved_ari = float(adjusted_rand_score(labels, saved_components))
    gmm_refits = []
    for seed in seeds:
        gmm = GaussianMixture(
            n_components=len(classes), covariance_type="full",
            n_init=gmm_n_init, random_state=int(seed),
        ).fit(standardized)
        predicted = gmm.predict(standardized)
        gmm_refits.append({
            "seed": int(seed),
            "class_ari": float(adjusted_rand_score(labels, predicted)),
            "agreement_ari_with_saved_components": float(
                adjusted_rand_score(saved_components, predicted)
            ),
            "bic": float(gmm.bic(standardized)),
            "component_counts": np.bincount(
                predicted, minlength=len(classes)
            ).astype(int).tolist(),
        })
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=23)
    probe = make_pipeline(
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=2000),
    )
    held_out_predictions = cross_val_predict(probe, latent, labels, cv=folds)
    return {
        "pixels": int(len(labels)),
        "latent_dimensions": int(latent.shape[1]),
        "class_counts": {
            str(int(value)): int(count)
            for value, count in zip(classes, counts)
        },
        "saved_gmm_class_ari": saved_ari,
        "gmm_refits": gmm_refits,
        "linear_probe": {
            "method": "balanced multinomial logistic regression, five stratified random pixel folds",
            "balanced_accuracy": float(balanced_accuracy_score(
                labels, held_out_predictions
            )),
            "class_ari": float(adjusted_rand_score(labels, held_out_predictions)),
        },
        "ten_nearest_latent_neighbours_same_class_fraction": neighbour_label_purity(
            standardized, labels
        ),
    }


def audit(input_path, attribution_dirs, output_path):
    with h5py.File(input_path, "r") as handle:
        labels = np.asarray(handle["Class_Label"][:]).reshape(-1)
        x = np.asarray(handle["xLocation"][:]).reshape(-1)
        y = np.asarray(handle["yLocation"][:]).reshape(-1)
    results = {}
    for condition, directory in attribution_dirs.items():
        summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
        if summary.get("status") not in ("valid", "valid_pilot"):
            raise ValueError(f"attribution is not valid: {directory}")
        latent = np.load(directory / "latent_mean.npy", allow_pickle=False)
        with np.load(directory / "coordinates_and_gmm.npz", allow_pickle=False) as saved:
            if not np.array_equal(saved["x"], x) or not np.array_equal(saved["y"], y):
                raise ValueError(f"coordinates differ from source HDF5: {directory}")
            components = saved["component"].copy()
        results[condition] = evaluate_latent(latent, labels, components)
        results[condition]["attribution_dir"] = str(directory)
        results[condition]["model_state_sha256"] = summary["model_state_sha256"]

    result = {
        "status": "valid",
        "dataset": input_path.stem,
        "source_h5": str(input_path),
        "interpretation_limit": (
            "In-sample section diagnostics, not patient-independent validation. "
            "The probe uses expert labels only post hoc and cannot be called "
            "an unsupervised method or a peak-picking result."
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
