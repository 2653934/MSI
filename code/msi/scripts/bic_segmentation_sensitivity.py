#!/usr/bin/env python3
"""BIC-K segmentation sensitivity, descriptive (protocol 18 Section 6, item b).

CPU only. Runs after ``select_gmm_k_bic.py`` for one section-arm. If the
BIC-selected K (or, after K=1, the recorded best K>=2) equals the production K,
it records "BIC supports the production K" and computes nothing. Otherwise it
refits the GMM at that K on the saved latent with the production settings,
builds the posterior-|PCC| balanced ranking with the existing functions, and
scores mSCF1 at K_bin with the existing scorer, next to the saved gate (a)/(b)
posterior-|PCC| at production K (m = 1).

Before anything at the new K is scored, the same code path must reproduce the
saved production-K posterior-|PCC| mSCF1 from the saved GMM parameters to
1e-12, or the script stops. No trigger and no verdict; no balanced accuracy.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from evaluate_fair_scoring_baselines import tic_statistics
from evaluate_spatial_msipl_attributed_peaks import (
    load_correlations,
    read_h5_metadata,
    score_indices,
)
import evaluate_fair_scoring_baselines
import evaluate_msipl_massnet_peaks
import evaluate_spatial_msipl_attributed_peaks
from spatial_msipl import provenance, simple_baselines
from spatial_msipl.provenance import (
    StaleResultError, atomic_write_json, check_existing, code_record, file_record,
    require_slurm,
)
from spatial_msipl.simple_baselines import (
    check_posterior_against_saved,
    gmm_posterior_numpy,
    moore_edges,
    one_hot_maps,
    posterior_pcc_rankings,
)

SENSITIVITY_VERSION = 1
LABEL = "BIC-K segmentation sensitivity, descriptive"
SCORE_TOLERANCE = 1e-12
COMPLETE = "complete"
COMPARED = ("posterior_abs_pcc_balanced", "hard_assignment_abs_pcc_balanced")


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--attribution-dir", required=True, type=Path)
    parser.add_argument("--bic-selection", required=True, type=Path,
                        help="bic_selection.json for this section-arm")
    parser.add_argument("--fair-scoring-summary", required=True, type=Path,
                        help="gate (a)/(b) bin-level summary.json for this section-arm")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=1024,
                        help="as the gate (a)/(b) evaluation (its default)")
    parser.add_argument("--allow-outside-slurm", action="store_true",
                        help="tests only; real sections must run inside Slurm")
    return parser.parse_args()


def code_paths():
    modules = (provenance, simple_baselines, evaluate_fair_scoring_baselines,
               evaluate_msipl_massnet_peaks, evaluate_spatial_msipl_attributed_peaks)
    return [Path(__file__).resolve()] + [Path(m.__file__).resolve() for m in modules]


def target_k(bic):
    """K to test: the BIC-selected K, or the recorded best K>=2 after K=1."""
    selected = bic.get("selected_k")
    if selected == 1:
        return bic.get("sensitivity_k_ge_2")
    return selected


def label_agreement(labels, assignment):
    return {"ari": float(adjusted_rand_score(labels, assignment)),
            "nmi": float(normalized_mutual_info_score(labels, assignment))}


def main():
    args = parse_arguments()
    require_slurm(args.allow_outside_slurm)
    dataset = args.input.stem
    args.output.mkdir(parents=True, exist_ok=True)
    bic = json.loads(args.bic_selection.read_text(encoding="utf-8"))
    fair = json.loads(args.fair_scoring_summary.read_text(encoding="utf-8"))
    if bic.get("status") != COMPLETE:
        raise SystemExit(f"BIC selection is not complete: {args.bic_selection}")
    if fair.get("status") != COMPLETE or fair.get("dataset") != dataset:
        raise SystemExit("fair-scoring summary is not complete or is for another section")
    sources = {name: file_record(args.attribution_dir / name)
               for name in ("latent_mean.npy", "coordinates_and_gmm.npz",
                            "gmm_parameters.npz")}
    # The BIC run and the gate (a)/(b) run must have read the same saved latent.
    for name in ("latent_mean.npy", "coordinates_and_gmm.npz"):
        if bic["provenance"]["source_artifacts"][name]["sha256"] != sources[name]["sha256"]:
            raise SystemExit(f"BIC selection was made on a different {name}")
    fair_latent = fair["provenance"]["source_artifacts"]["latent_mean"]["sha256"]
    if fair_latent != sources["latent_mean.npy"]["sha256"]:
        raise SystemExit("fair-scoring summary was made on a different latent_mean.npy")

    production_k = int(bic["production_k"])
    k = target_k(bic)
    seed = int(bic["provenance"]["parameters"]["seed"])
    n_init = int(bic["provenance"]["parameters"]["n_init"])
    expected = {
        "sensitivity_version": SENSITIVITY_VERSION,
        "label": LABEL,
        "dataset": dataset,
        "parameters": {"production_k": production_k, "target_k": k, "seed": seed,
                       "n_init": n_init, "chunk_size": args.chunk_size,
                       "score_tolerance": SCORE_TOLERANCE},
        "input": file_record(args.input),
        "source_artifacts": dict(sources, bic_selection=file_record(args.bic_selection),
                                 fair_scoring_summary=file_record(args.fair_scoring_summary)),
        "code": code_record(code_paths()),
    }
    summary_path = args.output / "summary.json"
    try:
        if check_existing(summary_path, expected, COMPLETE) == "valid":
            print(f"Existing result matches current provenance; skipped: {summary_path}")
            return
    except StaleResultError as error:
        print(f"STALE: {error}", file=sys.stderr)
        raise SystemExit(3)

    record = {"status": COMPLETE, "provenance": expected, "label": LABEL,
              "dataset": dataset, "production_k": production_k,
              "bic_selected_k": bic.get("selected_k"), "tested_k": k,
              "verdict": None, "trigger": None}
    if k is None or int(k) == production_k:
        record.update({
            "applicable": False,
            "reason": ("no converged K>=2" if k is None
                       else "BIC supports the production K; nothing computed"),
        })
        atomic_write_json(summary_path, record)
        print(record["reason"])
        return

    k_bin = int(fair["K_bin"])
    mz, labels, x, y, pixels_first = read_h5_metadata(args.input)
    n_bins = len(mz)
    saved_gmm = np.load(args.attribution_dir / "coordinates_and_gmm.npz")
    if not (np.array_equal(x, saved_gmm["x"]) and np.array_equal(y, saved_gmm["y"])):
        raise ValueError("attribution coordinates do not match the HDF5 input")
    latent = np.load(args.attribution_dir / "latent_mean.npy")

    # Production K exactly as gate (a)/(b): saved GMM parameters, NumPy posterior.
    production_posterior = gmm_posterior_numpy(
        latent, **dict(np.load(args.attribution_dir / "gmm_parameters.npz")))
    posterior_difference = check_posterior_against_saved(
        production_posterior, saved_gmm["component"], saved_gmm["assigned_posterior"])
    production_component = saved_gmm["component"].astype(np.int64)

    # Target K: refit with the production settings (as select_gmm_k_bic.py).
    standardized = StandardScaler().fit_transform(np.asarray(latent, dtype=np.float64))
    model = GaussianMixture(n_components=int(k), covariance_type="full",
                            n_init=n_init, random_state=seed).fit(standardized)
    posterior = model.predict_proba(standardized)
    component = np.argmax(posterior, axis=1)
    counts = np.bincount(component, minlength=int(k))

    maps = {"production_soft": production_posterior,
            "production_hard": one_hot_maps(production_component, production_posterior.shape[1]),
            "bic_soft": posterior,
            "bic_hard": one_hot_maps(component, int(k))}
    edges = moore_edges(x, y)
    _, pcc, _ = tic_statistics(args.input, pixels_first, n_bins, args.chunk_size,
                               maps, *edges)
    correlations = load_correlations(args.input, labels, n_bins, pixels_first,
                                     args.chunk_size)

    reproduced = {}
    production_rankings = posterior_pcc_rankings(pcc["production_soft"], pcc["production_hard"])
    for name in COMPARED:
        rescored = score_indices(production_rankings[name][:k_bin], correlations, n_bins)["mSCF1"]
        saved = float(fair["bin_level"][name]["1.0"]["mSCF1"])
        if abs(rescored - saved) > SCORE_TOLERANCE:
            raise ValueError(f"{name}: production-K rescore {rescored} != saved {saved}")
        reproduced[name] = saved

    rankings = posterior_pcc_rankings(pcc["bic_soft"], pcc["bic_hard"])
    comparison = {}
    for name in COMPARED:
        value = score_indices(rankings[name][:k_bin], correlations, n_bins)["mSCF1"]
        comparison[name] = {"production_k_mSCF1": reproduced[name],
                            "tested_k_mSCF1": float(value),
                            "tested_minus_production": float(value - reproduced[name])}
    record.update({
        "applicable": True,
        "K_bin": k_bin,
        "budget_multiplier": "1.0",
        "checks": {"production_posterior_max_abs_difference": posterior_difference,
                   "production_k_mSCF1_reproduced": reproduced},
        "refit": {"converged": bool(model.converged_), "n_iter": int(model.n_iter_),
                  "bic": float(model.bic(standardized)),
                  "component_counts": counts.tolist(),
                  "empty_components": int(np.count_nonzero(counts == 0))},
        "label_agreement": {"tested_k_hard_assignment": label_agreement(labels, component),
                            "production_k_saved_assignment":
                                label_agreement(labels, production_component),
                            "note": "ARI and NMI only; no balanced accuracy when K differs "
                                    "from the class count"},
        "mSCF1_at_K_bin": comparison,
    })
    atomic_write_json(summary_path, record)
    print(f"{LABEL}: complete for {dataset}, tested K={k}")


if __name__ == "__main__":
    main()
