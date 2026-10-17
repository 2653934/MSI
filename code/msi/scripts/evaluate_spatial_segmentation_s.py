#!/usr/bin/env python3
"""Test S, one section-arm (protocol 18 Section 6.2; supervisor chat 2026-10-17 08:04).

CPU only, on saved artifacts; no retraining and no new IG. S1: smooth the
production-standardised latent means with Cardinal's structure-adaptive weights
(src/spatial_msipl/spatial_segmentation.py), refit StandardScaler + GMM with the
production settings, and rank bins by posterior-|PCC| (balanced) from the
smoothed posterior: ``sa_posterior_abs_pcc_balanced``. S2 (descriptive): rank
fusion of plain posterior-|PCC| and Moran's I, and segmentation agreement.

Scored with the fair-scoring functions (the evaluator itself is not edited), at
K_bin and, when the fair-scoring summary has an approved P1, at the P1 matched
K_peak. Refuses, before S is scored, unless:
- every input file has the sha256 recorded by the fair-scoring summary;
- the production GMM refit on the unsmoothed latents gives ARI 1.0 to the saved
  labels;
- the neighbourhoods give exactly the Moore edges used for Moran's I;
- plain posterior-|PCC| and Moran's I reproduce the saved fair-scoring mSCF1 to
  1e-12 at every scale scored.
No verdict here; summarise_spatial_segmentation_s.py applies the rule.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from evaluate_fair_scoring_baselines import tic_statistics
from evaluate_msipl_massnet_peaks import THRESHOLDS, true_indices_at_threshold
from evaluate_spatial_msipl_attributed_peaks import (
    best_component_mapping,
    load_correlations,
    read_h5_metadata,
    score_indices,
)
import evaluate_fair_scoring_baselines
import evaluate_msipl_massnet_peaks
import evaluate_spatial_msipl_attributed_peaks
from spatial_msipl import peak_groups, provenance, simple_baselines, spatial_segmentation
from spatial_msipl.peak_groups import (
    first_k_distinct_groups,
    group_reference_sets,
    partition_hash,
    score_groups,
)
from spatial_msipl.provenance import (
    StaleResultError, array_sha256, atomic_write_json, check_existing, code_record,
    file_record, require_slurm,
)
from spatial_msipl.simple_baselines import (
    check_posterior_against_saved,
    gmm_posterior_numpy,
    moore_edges,
    nan_to_lowest,
    one_hot_maps,
    posterior_pcc_rankings,
    rank_descending,
)
from spatial_msipl.spatial_segmentation import (
    measured_neighbourhoods,
    neighbourhood_edges,
    rank_fusion,
    structure_adaptive_smoothing,
)

TEST_S_VERSION = 1
PROTOCOL = "docs/research/18 Fair Scoring and Simple Baselines Protocol.md, Section 6.2 (Test S)"
SCORE_TOLERANCE = 1e-12
COMPLETE = "complete"
PLAIN = "posterior_abs_pcc_balanced"
SMOOTHED = "sa_posterior_abs_pcc_balanced"
FUSION = "rank_fusion_posterior_morans_i"
MORANS = "morans_i"
ATTRIBUTION_FILES = {"latent_mean": "latent_mean.npy",
                     "coordinates_and_gmm": "coordinates_and_gmm.npz",
                     "gmm_parameters": "gmm_parameters.npz",
                     "attribution_summary": "summary.json"}


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--attribution-dir", required=True, type=Path)
    parser.add_argument("--fair-scoring-summary", required=True, type=Path,
                        help="the saved fair-scoring summary.json for this section-arm")
    parser.add_argument("--partition-dir", type=Path,
                        help="peak-partition audit folder; required when the summary has P1")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=1024,
                        help="as the fair-scoring evaluation (its default)")
    parser.add_argument("--allow-outside-slurm", action="store_true",
                        help="tests only; real sections must run inside Slurm")
    # Test-only switch for the identity check (sigma -> 0, beta = 1).
    parser.add_argument("--identity-smoothing", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def code_paths():
    modules = (peak_groups, provenance, simple_baselines, spatial_segmentation,
               evaluate_fair_scoring_baselines, evaluate_msipl_massnet_peaks,
               evaluate_spatial_msipl_attributed_peaks)
    return [Path(__file__).resolve()] + [Path(m.__file__).resolve() for m in modules]


def refuse(message):
    raise SystemExit(f"Test S refused: {message}")


def check_hash(name, path, recorded):
    actual = file_record(path)
    if recorded is None or actual["sha256"] != recorded.get("sha256"):
        refuse(f"{name} differs from the file the fair-scoring summary used ({path})")
    return actual


def fit_gmm(features, k, n_init, seed):
    """Production settings: StandardScaler, full covariance, sklearn defaults otherwise."""
    standardized = StandardScaler().fit_transform(np.asarray(features, dtype=np.float64))
    model = GaussianMixture(n_components=k, covariance_type="full", n_init=n_init,
                            random_state=seed).fit(standardized)
    return model, standardized


def segmentation_agreement(component, labels):
    try:
        mapping = best_component_mapping(component, labels)
    except ValueError as error:
        return {"balanced_accuracy": None, "not_computed": str(error)}
    return {"balanced_accuracy": mapping["balanced_accuracy"],
            "accuracy": mapping["accuracy"],
            "mapping": {str(k): int(v) for k, v in mapping["mapping"].items()},
            "mapping_rule": "accuracy-maximising component-to-class permutation "
                            "(best_component_mapping, as the matched evaluation)"}


def main():
    args = parse_arguments()
    require_slurm(args.allow_outside_slurm)
    dataset = args.input.stem
    fair = json.loads(args.fair_scoring_summary.read_text(encoding="utf-8"))
    if fair.get("status") != COMPLETE or fair.get("dataset") != dataset:
        refuse("fair-scoring summary is not complete or is for another section")
    if fair.get("class_subset") is not None:
        refuse("fair-scoring summary is a class-subset analysis")
    recorded = fair["provenance"]["source_artifacts"]
    approved = fair["provenance"].get("approved_partition_hashes") or {}
    use_p1 = "P1" in approved
    if use_p1 and args.partition_dir is None:
        refuse("the fair-scoring summary has an approved P1; --partition-dir is required")
    if not use_p1 and args.partition_dir is not None:
        refuse("--partition-dir given, but the fair-scoring summary has no approved P1")

    sources = {"input": check_hash("input", args.input, fair["provenance"]["input"]),
               "fair_scoring_summary": file_record(args.fair_scoring_summary)}
    for name, filename in ATTRIBUTION_FILES.items():
        sources[name] = check_hash(name, args.attribution_dir / filename, recorded.get(name))
    if use_p1:
        sources["partitions"] = check_hash("partitions", args.partition_dir / "partitions.npz",
                                           recorded.get("partitions"))
    attribution = json.loads((args.attribution_dir / "summary.json").read_text(encoding="utf-8"))
    gmm_settings = attribution.get("gmm", {})
    k = int(gmm_settings["components"])
    n_init, seed = int(gmm_settings["n_init"]), int(gmm_settings["seed"])
    smoothing = ({"sigma": 1e-6, "adaptive": False} if args.identity_smoothing
                 else {"sigma": spatial_segmentation.SIGMA, "adaptive": True})
    expected = {
        "test_s_version": TEST_S_VERSION,
        "protocol": PROTOCOL,
        "dataset": dataset,
        "parameters": {"gmm_components": k, "gmm_n_init": n_init, "gmm_seed": seed,
                       "radius": spatial_segmentation.RADIUS, **smoothing,
                       "adaptive_weight": "Cardinal 3.12.1 per-pixel scale "
                                          "s_i = max_j ||z_i - z_j|| / 2 + sqrt(eps)",
                       "scales": ["bin"] + (["P1"] if use_p1 else []),
                       "chunk_size": args.chunk_size, "score_tolerance": SCORE_TOLERANCE},
        "source_artifacts": sources,
        "approved_partition_hashes": {"P1": approved["P1"]} if use_p1 else {},
        "code": code_record(code_paths()),
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

    k_bin = int(fair["K_bin"])
    mz, labels, x, y, pixels_first = read_h5_metadata(args.input)
    n_bins = len(mz)
    saved_gmm = np.load(args.attribution_dir / "coordinates_and_gmm.npz")
    if not (np.array_equal(x, saved_gmm["x"]) and np.array_equal(y, saved_gmm["y"])):
        refuse("attribution coordinates do not match the HDF5 input")
    latent = np.load(args.attribution_dir / "latent_mean.npy")
    gmm_parameters = dict(np.load(args.attribution_dir / "gmm_parameters.npz"))
    if len(gmm_parameters["mixture_weights"]) != k:
        refuse("saved GMM component count differs from the attribution summary")
    production_component = saved_gmm["component"].astype(np.int64)

    # --- Validity checks before anything smoothed is scored. ---
    refit, refit_standardized = fit_gmm(latent, k, n_init, seed)
    refit_ari = float(adjusted_rand_score(production_component,
                                          refit.predict(refit_standardized)))
    if refit_ari != 1.0:
        refuse(f"production GMM refit on the unsmoothed latents gives ARI {refit_ari}, not 1.0")
    production_posterior = gmm_posterior_numpy(latent, **gmm_parameters)
    posterior_difference = check_posterior_against_saved(
        production_posterior, production_component, saved_gmm["assigned_posterior"])
    neighbourhoods = measured_neighbourhoods(x, y)
    sources_s, targets_s = neighbourhood_edges(neighbourhoods)
    sources_m, targets_m = moore_edges(x, y)
    if (set(zip(sources_s.tolist(), targets_s.tolist()))
            != set(zip(sources_m.tolist(), targets_m.tolist()))
            or len(sources_s) != len(sources_m)):
        refuse("smoothing neighbourhoods differ from the Moore edges used for Moran's I")

    # --- S1: smooth the production-standardised latents, refit the same GMM. ---
    standardized = ((np.asarray(latent, dtype=np.float64) - gmm_parameters["scaler_mean"])
                    / gmm_parameters["scaler_scale"])
    smoothed, smoothing_record = structure_adaptive_smoothing(standardized, x, y, **smoothing)
    model, smoothed_standardized = fit_gmm(smoothed, k, n_init, seed)
    smoothed_posterior = model.predict_proba(smoothed_standardized)
    smoothed_component = np.argmax(smoothed_posterior, axis=1)
    counts = np.bincount(smoothed_component, minlength=k)

    maps = {"soft": production_posterior, "hard": one_hot_maps(production_component, k),
            "sa_soft": smoothed_posterior, "sa_hard": one_hot_maps(smoothed_component, k)}
    stats, pcc, zero_tic = tic_statistics(args.input, pixels_first, n_bins, args.chunk_size,
                                          maps, sources_m, targets_m)
    correlations = load_correlations(args.input, labels, n_bins, pixels_first, args.chunk_size)
    rankings = {PLAIN: posterior_pcc_rankings(pcc["soft"], pcc["hard"])[PLAIN],
                MORANS: rank_descending(nan_to_lowest(stats["morans_i"]))}
    rankings[SMOOTHED] = posterior_pcc_rankings(pcc["sa_soft"], pcc["sa_hard"])[PLAIN]
    rankings[FUSION] = rank_fusion(rankings[PLAIN], rankings[MORANS])

    scores = {"bin": {name: score_indices(r[:k_bin], correlations, n_bins)["mSCF1"]
                      for name, r in rankings.items()}}
    reproduced = {}
    for name in (PLAIN, MORANS):
        saved = float(fair["bin_level"][name]["1.0"]["mSCF1"])
        if abs(scores["bin"][name] - saved) > SCORE_TOLERANCE:
            refuse(f"{name}: bin-level rescore {scores['bin'][name]} != saved {saved}")
        reproduced[f"bin:{name}"] = saved

    peak_record = None
    if use_p1:
        arrays = np.load(args.partition_dir / "partitions.npz")
        if not np.array_equal(arrays["mz"], mz):
            refuse("partition m/z axis differs from the HDF5 input")
        group_of_bin, apex = arrays["P1_group_of_bin"], arrays["P1_apex"]
        if partition_hash(group_of_bin) != approved["P1"]:
            refuse("P1 partition hash differs from the approved hash")
        n_groups = int(group_of_bin.max()) + 1
        reference_bins = {t: set().union(*(true_indices_at_threshold(correlations[c], t)
                                          for c in sorted(correlations)))
                          for t in THRESHOLDS}
        reference_groups = group_reference_sets(reference_bins, apex)
        k_peak = len(reference_groups[0.4])
        if k_peak != int(fair["peak_level"]["P1"]["K_peak"]):
            refuse(f"P1 K_peak {k_peak} differs from the saved {fair['peak_level']['P1']['K_peak']}")
        scores["P1"] = {}
        consumed = {}
        for name, ranking in rankings.items():
            matched, consumed[name] = first_k_distinct_groups(ranking, group_of_bin, k_peak)
            scores["P1"][name] = score_groups(matched.tolist(), reference_groups,
                                              n_groups)["mSCF1"]
        for name in (PLAIN, MORANS):
            saved = float(fair["peak_level"]["P1"]["methods"][name]["matched_K_peak"]["mSCF1"])
            if abs(scores["P1"][name] - saved) > SCORE_TOLERANCE:
                refuse(f"{name}: P1 rescore {scores['P1'][name]} != saved {saved}")
            reproduced[f"P1:{name}"] = saved
        peak_record = {"partition_sha256": approved["P1"], "groups": n_groups,
                       "K_peak": k_peak, "bins_consumed": consumed}

    prefix = 2 * k_bin
    np.savez_compressed(args.output / "rankings_prefix.npz",
                        **{name: r[:prefix] for name, r in rankings.items()})
    summary = {
        "status": COMPLETE,
        "provenance": expected,
        "dataset": dataset,
        "K_bin": k_bin,
        "label": "Test S (protocol 18 Section 6.2); per section-arm scores, no verdict",
        "checks": {"production_refit_ari_to_saved": refit_ari,
                   "production_posterior_max_abs_difference": posterior_difference,
                   "neighbourhood_edges_equal_morans_i_edges": True,
                   "moore_edges": int(len(sources_m)),
                   "reproduced_mSCF1": reproduced},
        "smoothing": smoothing_record,
        "smoothed_gmm": {"converged": bool(model.converged_), "n_iter": int(model.n_iter_),
                         "component_counts": counts.tolist(),
                         "empty_components": int(np.count_nonzero(counts == 0))},
        "mSCF1": scores,
        "S1_minus_plain": {scale: float(v[SMOOTHED] - v[PLAIN]) for scale, v in scores.items()},
        "S2": {
            "a_S1_minus_morans_i": {scale: float(v[SMOOTHED] - v[MORANS])
                                    for scale, v in scores.items()},
            "b_fusion_minus_plain": {scale: float(v[FUSION] - v[PLAIN])
                                     for scale, v in scores.items()},
            "b_fusion_rule": "mean of the per-bin ranks of posterior-|PCC| (balanced order) "
                             "and Moran's I; ties broken by the posterior rank",
            "c_segmentation": {
                "ari_smoothed_vs_production": float(adjusted_rand_score(
                    production_component, smoothed_component)),
                "production_vs_expert": segmentation_agreement(production_component, labels),
                "smoothed_vs_expert": segmentation_agreement(smoothed_component, labels),
                "note": "descriptive; expert labels did not fit any GMM or rank any bin",
            },
        },
        "peak_level_P1": peak_record,
        "zero_tic_pixels": zero_tic,
        "rankings": {name: {"full_ranking_sha256": array_sha256(r),
                            "saved_prefix_length": int(min(prefix, len(r)))}
                     for name, r in rankings.items()},
    }
    atomic_write_json(summary_path, summary)
    print(f"Test S complete for {dataset}: S1 - plain = "
          + ", ".join(f"{s} {v:+.4f}" for s, v in summary["S1_minus_plain"].items()))


if __name__ == "__main__":
    main()
