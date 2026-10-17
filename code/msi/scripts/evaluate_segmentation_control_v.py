#!/usr/bin/env python3
"""Test V, one section/run (protocol 18 Section 6.4; supervisor chat 2026-10-17 12:42).

CPU only, on saved data; no retraining and no IG. The VAE's own centre input
(src/spatial_msipl/segmentation_control.py) is reduced by PCA to 5 components
(primary) and 20 (descriptive), each clustered by the production segmentation
step (StandardScaler, full-covariance GMM, production K, reg_covar 1e-6, n_init
20, seed 1), and bins are ranked by posterior-|PCC| (balanced) from that
posterior: ``pca5_posterior_abs_pcc_balanced`` and ``pca20_...``. The comparator
is the saved seed-1 VAE ``central_only`` posterior-|PCC|.

Scored with the fair-scoring functions (the evaluator itself is not edited), at
K_bin and, when the central_only fair-scoring summary has an approved P1, at the
P1 matched K_peak. Refuses, before anything is scored, unless:
- every input file has the sha256 recorded by the fair-scoring summary;
- the production GMM refit on the saved VAE latents gives ARI 1.0;
- plain VAE posterior-|PCC| and Moran's I reproduce the saved mSCF1 to 1e-12
  at every scale scored.
Descriptive values read from the saved summaries: IG, and VAE uniform_mean
posterior-|PCC| (None where that arm has no result). No verdict here;
summarise_segmentation_control_v.py applies the rule.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score

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
from spatial_msipl import (peak_groups, preprocessing, provenance, segmentation_control,
                           simple_baselines)
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
from spatial_msipl.segmentation_control import (
    GMM_N_INIT, GMM_SEED, PREPROCESSING_RECORD, PRIMARY_COMPONENTS, REG_COVAR,
    SENSITIVITY_COMPONENTS, fit_gmm, pca_segmentation, vae_centre_inputs,
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

TEST_V_VERSION = 1
PROTOCOL = "docs/research/18 Fair Scoring and Simple Baselines Protocol.md, Section 6.4 (Test V)"
SCORE_TOLERANCE = 1e-12
COMPLETE = "complete"
PLAIN = "posterior_abs_pcc_balanced"
MORANS = "morans_i"
IG = "integrated_gradients"
PCA_NAMES = {PRIMARY_COMPONENTS: f"pca{PRIMARY_COMPONENTS}_{PLAIN}",
             SENSITIVITY_COMPONENTS: f"pca{SENSITIVITY_COMPONENTS}_{PLAIN}"}
UNIFORM = f"vae_uniform_mean_{PLAIN}"
ATTRIBUTION_FILES = {"latent_mean": "latent_mean.npy",
                     "coordinates_and_gmm": "coordinates_and_gmm.npz",
                     "gmm_parameters": "gmm_parameters.npz",
                     "attribution_summary": "summary.json"}


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--attribution-dir", required=True, type=Path,
                        help="the seed-1 central_only attribution folder")
    parser.add_argument("--fair-scoring-summary", required=True, type=Path,
                        help="the saved seed-1 central_only fair-scoring summary.json")
    parser.add_argument("--uniform-fair-scoring-summary", type=Path,
                        help="the saved seed-1 uniform_mean fair-scoring summary.json "
                             "(descriptive; omitted where that arm has no result)")
    parser.add_argument("--partition-dir", type=Path,
                        help="peak-partition audit folder; required when the summary has P1")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=1024,
                        help="as the fair-scoring evaluation (its default)")
    parser.add_argument("--allow-outside-slurm", action="store_true",
                        help="tests only; real sections must run inside Slurm")
    return parser.parse_args()


def code_paths():
    modules = (peak_groups, preprocessing, provenance, segmentation_control, simple_baselines,
               evaluate_fair_scoring_baselines, evaluate_msipl_massnet_peaks,
               evaluate_spatial_msipl_attributed_peaks)
    return [Path(__file__).resolve()] + [Path(m.__file__).resolve() for m in modules]


def refuse(message):
    raise SystemExit(f"Test V refused: {message}")


def check_hash(name, path, recorded):
    actual = file_record(path)
    if recorded is None or actual["sha256"] != recorded.get("sha256"):
        refuse(f"{name} differs from the file the fair-scoring summary used ({path})")
    return actual


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


def saved_value(summary, scale, name):
    if summary is None:
        return None
    if scale == "bin":
        return float(summary["bin_level"][name]["1.0"]["mSCF1"])
    return float(summary["peak_level"]["P1"]["methods"][name]["matched_K_peak"]["mSCF1"])


def main():
    args = parse_arguments()
    require_slurm(args.allow_outside_slurm)
    dataset = args.input.stem
    fair = json.loads(args.fair_scoring_summary.read_text(encoding="utf-8"))
    if fair.get("status") != COMPLETE or fair.get("dataset") != dataset:
        refuse("fair-scoring summary is not complete or is for another section")
    if fair.get("class_subset") is not None:
        refuse("fair-scoring summary is a class-subset analysis")
    uniform = None
    if args.uniform_fair_scoring_summary is not None:
        uniform = json.loads(args.uniform_fair_scoring_summary.read_text(encoding="utf-8"))
        if uniform.get("status") != COMPLETE or uniform.get("dataset") != dataset:
            refuse("uniform_mean fair-scoring summary is not complete or is for another section")
    recorded = fair["provenance"]["source_artifacts"]
    approved = fair["provenance"].get("approved_partition_hashes") or {}
    use_p1 = "P1" in approved
    if use_p1 and args.partition_dir is None:
        refuse("the fair-scoring summary has an approved P1; --partition-dir is required")
    if not use_p1 and args.partition_dir is not None:
        refuse("--partition-dir given, but the fair-scoring summary has no approved P1")

    sources = {"input": check_hash("input", args.input, fair["provenance"]["input"]),
               "fair_scoring_summary": file_record(args.fair_scoring_summary)}
    if args.uniform_fair_scoring_summary is not None:
        sources["uniform_fair_scoring_summary"] = file_record(args.uniform_fair_scoring_summary)
    for name, filename in ATTRIBUTION_FILES.items():
        sources[name] = check_hash(name, args.attribution_dir / filename, recorded.get(name))
    if use_p1:
        sources["partitions"] = check_hash("partitions", args.partition_dir / "partitions.npz",
                                           recorded.get("partitions"))
    attribution = json.loads((args.attribution_dir / "summary.json").read_text(encoding="utf-8"))
    production = attribution.get("gmm", {})
    k = int(production["components"])
    scales = ["bin"] + (["P1"] if use_p1 else [])
    expected = {
        "test_v_version": TEST_V_VERSION,
        "protocol": PROTOCOL,
        "dataset": dataset,
        "parameters": {"gmm_components": k, "pca_components": [PRIMARY_COMPONENTS,
                                                               SENSITIVITY_COMPONENTS],
                       "pca_solver": "randomized", "pca_random_state": 1,
                       "gmm_n_init": GMM_N_INIT, "gmm_seed": GMM_SEED, "reg_covar": REG_COVAR,
                       "preprocessing": PREPROCESSING_RECORD, "scales": scales,
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

    # --- Validity checks before anything PCA-based is scored. ---
    refit, refit_standardized = fit_gmm(latent, k, int(production["n_init"]),
                                        int(production["seed"]))
    refit_ari = float(adjusted_rand_score(production_component,
                                          refit.predict(refit_standardized)))
    if refit_ari != 1.0:
        refuse(f"production GMM refit on the saved VAE latents gives ARI {refit_ari}, not 1.0")
    production_posterior = gmm_posterior_numpy(latent, **gmm_parameters)
    posterior_difference = check_posterior_against_saved(
        production_posterior, production_component, saved_gmm["assigned_posterior"])

    # --- PCA segmentations of the VAE's centre input. ---
    inputs = vae_centre_inputs(args.input)
    if inputs.shape != (len(x), n_bins):
        refuse(f"centre inputs have shape {inputs.shape}, expected {(len(x), n_bins)}")
    pca_records, maps, components = {}, {"soft": production_posterior,
                                         "hard": one_hot_maps(production_component, k)}, {}
    for n_components in (PRIMARY_COMPONENTS, SENSITIVITY_COMPONENTS):
        posterior, component, record = pca_segmentation(inputs, n_components, k)
        key = f"pca{n_components}"
        pca_records[key] = record
        components[key] = component
        maps[f"{key}_soft"] = posterior
        maps[f"{key}_hard"] = one_hot_maps(component, k)
    del inputs

    sources_m, targets_m = moore_edges(x, y)
    stats, pcc, zero_tic = tic_statistics(args.input, pixels_first, n_bins, args.chunk_size,
                                          maps, sources_m, targets_m)
    correlations = load_correlations(args.input, labels, n_bins, pixels_first, args.chunk_size)
    rankings = {PLAIN: posterior_pcc_rankings(pcc["soft"], pcc["hard"])[PLAIN],
                MORANS: rank_descending(nan_to_lowest(stats["morans_i"]))}
    for n_components, name in PCA_NAMES.items():
        key = f"pca{n_components}"
        rankings[name] = posterior_pcc_rankings(pcc[f"{key}_soft"], pcc[f"{key}_hard"])[PLAIN]

    scores = {"bin": {name: score_indices(r[:k_bin], correlations, n_bins)["mSCF1"]
                      for name, r in rankings.items()}}
    reproduced = {}
    for name in (PLAIN, MORANS):
        saved = saved_value(fair, "bin", name)
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
        scores["P1"], consumed = {}, {}
        for name, ranking in rankings.items():
            matched, consumed[name] = first_k_distinct_groups(ranking, group_of_bin, k_peak)
            scores["P1"][name] = score_groups(matched.tolist(), reference_groups,
                                              n_groups)["mSCF1"]
        for name in (PLAIN, MORANS):
            saved = saved_value(fair, "P1", name)
            if abs(scores["P1"][name] - saved) > SCORE_TOLERANCE:
                refuse(f"{name}: P1 rescore {scores['P1'][name]} != saved {saved}")
            reproduced[f"P1:{name}"] = saved
        peak_record = {"partition_sha256": approved["P1"], "groups": n_groups,
                       "K_peak": k_peak, "bins_consumed": consumed}

    primary = PCA_NAMES[PRIMARY_COMPONENTS]
    prefix = 2 * k_bin
    np.savez_compressed(args.output / "rankings_prefix.npz",
                        **{name: r[:prefix] for name, r in rankings.items()})
    summary = {
        "status": COMPLETE,
        "provenance": expected,
        "dataset": dataset,
        "K_bin": k_bin,
        "label": "Test V (protocol 18 Section 6.4); per section scores, no verdict",
        "checks": {"production_refit_ari_to_saved": refit_ari,
                   "production_posterior_max_abs_difference": posterior_difference,
                   "reproduced_mSCF1": reproduced},
        "pca": pca_records,
        "mSCF1": scores,
        "vae_minus_pca5": {scale: float(v[PLAIN] - v[primary]) for scale, v in scores.items()},
        "saved_descriptive": {scale: {IG: saved_value(fair, scale, IG),
                                      UNIFORM: saved_value(uniform, scale, PLAIN)}
                              for scale in scores},
        "segmentation_vs_expert": {
            "vae_central_only": segmentation_agreement(production_component, labels),
            **{key: segmentation_agreement(c, labels) for key, c in components.items()},
            "ari_pca5_vs_vae": float(adjusted_rand_score(production_component,
                                                         components["pca5"])),
            "note": "descriptive; expert labels did not fit any GMM or rank any bin",
        },
        "peak_level_P1": peak_record,
        "zero_tic_pixels": zero_tic,
        "rankings": {name: {"full_ranking_sha256": array_sha256(r),
                            "saved_prefix_length": int(min(prefix, len(r)))}
                     for name, r in rankings.items()},
    }
    atomic_write_json(summary_path, summary)
    print(f"Test V complete for {dataset}: VAE - PCA-5 = "
          + ", ".join(f"{s} {v:+.4f}" for s, v in summary["vae_minus_pca5"].items()))


if __name__ == "__main__":
    main()
