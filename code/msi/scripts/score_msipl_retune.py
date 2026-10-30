#!/usr/bin/env python3
"""Count-matched scoring of the re-tuned msiPL lists (protocol 18 Section 6.8;
supervisor chat 2026-10-30 12:58 item 2 and the 17:33 ruling).

For one section and one frozen IG arm (seed 1), this script:
1. rebuilds every ranking with the fair evaluator's own functions, over all bins,
   and stops unless it reproduces the saved GMM posterior, the saved IG and L2
   lists at K_bin (exact ties only), their mSCF1 at K_bin (1e-12), and the first
   2 x K_bin entries of every ranking in the saved fair-scoring rankings_prefix.npz;
2. on GBM/CAC (--legacy-metrics given), requires the m = 1 re-tune list to be the
   reproduced saved list and rescores it with the evaluator's strict check_legacy
   (integer TP/FP/FN, mSCF1 to 1e-12);
3. for every multiplier, snaps the re-tuned list to its unique bins (n_m) and
   scores legacy msiPL and every ranking at exactly n_m, at bin level, all classes.
The production evaluator is imported, never changed. Exit 3: output exists.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from evaluate_fair_scoring_baselines import (
    SCORE_TOLERANCE,
    check_legacy,
    code_paths,
    read_saved_list,
    tic_statistics,
)
from evaluate_msipl_massnet_peaks import nearest_unique_indices
from evaluate_spatial_msipl_attributed_peaks import (
    load_correlations,
    read_h5_metadata,
    score_indices,
)
from spatial_msipl.provenance import atomic_write_json, code_record, file_record, require_slurm
from spatial_msipl.simple_baselines import (
    balanced_ranking_from_component_scores,
    check_posterior_against_saved,
    gmm_posterior_numpy,
    moore_edges,
    nan_to_lowest,
    one_hot_maps,
    posterior_pcc_rankings,
    production_ig_scores,
    production_l2_ranking,
    rank_descending,
    supervised_oracle_ranking,
    tie_permuted_positions,
)

MULTIPLIER_LABELS = ("m0.5", "m0.75", "m1.0", "m1.5", "m2.0")
IG = "integrated_gradients"


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--attribution-dir", required=True, type=Path)
    parser.add_argument("--saved-evaluation-dir", required=True, type=Path)
    parser.add_argument("--saved-fair-dir", required=True, type=Path,
                        help="seed-1 bin-level fair-scoring output (summary.json, rankings_prefix.npz)")
    parser.add_argument("--retune-dir", required=True, type=Path,
                        help="retune_msipl_beta.py output for this section")
    parser.add_argument("--legacy-metrics", type=Path, default=None,
                        help="GBM/CAC: the saved legacy peak_metrics.json (m = 1 check)")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--allow-outside-slurm", action="store_true",
                        help="tests only")
    return parser.parse_args()


def check_prefixes(rankings, saved_prefix):
    """Every saved prefix must be the start of the rebuilt ranking."""
    checked = {}
    for name in saved_prefix.files:
        prefix = np.asarray(saved_prefix[name], dtype=np.int64)
        if name not in rankings:
            raise ValueError(f"saved prefix {name} has no rebuilt ranking")
        if not np.array_equal(np.asarray(rankings[name][:len(prefix)], dtype=np.int64), prefix):
            raise ValueError(f"{name}: rebuilt ranking differs from the saved prefix")
        checked[name] = int(len(prefix))
    return checked


def read_peaks(path):
    values = np.genfromtxt(path, delimiter=",", names=True)
    return np.asarray(values[values.dtype.names[0]], dtype=np.float64).reshape(-1)


def count_matched(rankings, legacy_indices, correlations, n_bins):
    """Legacy and every ranking at exactly the legacy list's unique-bin count."""
    n = int(len(legacy_indices))
    legacy = score_indices(legacy_indices, correlations, n_bins)
    scores = {name: score_indices(ranking[:n], correlations, n_bins)["mSCF1"]
              for name, ranking in rankings.items()}
    return {"n_unique_bins": n, "legacy_msipl": legacy["mSCF1"],
            "legacy_threshold_results": legacy["threshold_results"],
            "rankings": scores,
            "ig_minus_legacy": scores[IG] - legacy["mSCF1"]}


def main():
    args = parse_arguments()
    require_slurm(args.allow_outside_slurm)
    summary_path = args.output / "summary.json"
    if summary_path.exists():
        print(f"Output exists: {summary_path} (never overwritten)", file=sys.stderr)
        return 3
    started = time.perf_counter()

    retune = json.loads((args.retune_dir / "summary.json").read_text(encoding="utf-8"))
    if retune.get("status") != "complete":
        raise ValueError("re-tune summary is not complete")
    saved_summary = json.loads((args.saved_evaluation_dir / "summary.json").read_text(
        encoding="utf-8"))
    k_bin = int(saved_summary["matched_peak_evaluation"]["count"])
    fair = json.loads((args.saved_fair_dir / "summary.json").read_text(encoding="utf-8"))
    if fair.get("status") != "complete" or int(fair["K_bin"]) != k_bin:
        raise ValueError("saved fair-scoring summary is incomplete or has another K_bin")
    if int(retune["K_bin"]) != k_bin:
        raise ValueError(f"re-tune K_bin {retune['K_bin']} differs from K_bin {k_bin}")
    gbm_cac = args.legacy_metrics is not None
    if gbm_cac:
        reproduction = retune.get("m1_reproduction") or {}
        if not reproduction.get("identical") or \
                retune["selections"]["m1.0"]["status"] != "saved_list_reproduced":
            raise ValueError("GBM/CAC m = 1 is not the reproduced saved list")

    mz, raw_labels, x, y, pixels_first = read_h5_metadata(args.input)
    n_bins = len(mz)
    attributions = np.load(args.attribution_dir / "attributions.npz")
    saved_gmm = np.load(args.attribution_dir / "coordinates_and_gmm.npz")
    gmm_parameters = dict(np.load(args.attribution_dir / "gmm_parameters.npz"))
    latent = np.load(args.attribution_dir / "latent_mean.npy")
    if not (np.array_equal(x, saved_gmm["x"]) and np.array_equal(y, saved_gmm["y"])):
        raise ValueError("attribution coordinates do not match the HDF5 input")

    # --- Gate 1: the evaluator's own reproduction checks. ---
    posterior = gmm_posterior_numpy(latent, **gmm_parameters)
    posterior_difference = check_posterior_against_saved(
        posterior, saved_gmm["component"], saved_gmm["assigned_posterior"])
    ig_scores = production_ig_scores(attributions)
    ig_ranking, ig_sources = balanced_ranking_from_component_scores(ig_scores, with_sources=True)
    l2_scores = np.asarray(attributions["first_layer_combined_l2"], dtype=np.float64)
    rankings = {IG: ig_ranking, "first_layer_l2": production_l2_ranking(attributions)}
    score_at = {IG: lambda i, b: ig_scores[int(ig_sources[i])][b],
                "first_layer_l2": lambda i, b: l2_scores[b]}
    for name, file_name in ((IG, f"ig_matched_{k_bin}_bins.csv"),
                            ("first_layer_l2", f"first_layer_l2_matched_{k_bin}_bins.csv")):
        tie_permuted_positions(rankings[name][:k_bin],
                               read_saved_list(args.saved_evaluation_dir / file_name),
                               score_at[name])
    correlations = load_correlations(args.input, raw_labels, n_bins, pixels_first,
                                     args.chunk_size)
    for name in (IG, "first_layer_l2"):
        rescored = score_indices(rankings[name][:k_bin], correlations, n_bins)["mSCF1"]
        saved = float(saved_summary["matched_peak_evaluation"]["methods"][name]["mSCF1"])
        if abs(rescored - saved) > SCORE_TOLERANCE:
            raise ValueError(f"{name}: rescored mSCF1 {rescored} != saved {saved}")

    components = saved_gmm["component"].astype(np.int64)
    sources, targets = moore_edges(x, y)
    maps = {"soft": posterior, "hard": one_hot_maps(components, posterior.shape[1])}
    stats, pcc, _ = tic_statistics(args.input, pixels_first, n_bins, args.chunk_size,
                                   maps, sources, targets)
    rankings.update(posterior_pcc_rankings(pcc["soft"], pcc["hard"]))
    rankings["mean_intensity"] = rank_descending(stats["mean_intensity"])
    rankings["variance"] = rank_descending(stats["variance"])
    rankings["morans_i"] = rank_descending(nan_to_lowest(stats["morans_i"]))
    rankings["oracle"] = supervised_oracle_ranking(correlations)

    # --- Gate 2: the saved fair-scoring prefixes and its IG score at K_bin. ---
    prefix_lengths = check_prefixes(rankings, np.load(args.saved_fair_dir / "rankings_prefix.npz"))
    fair_ig = float(fair["bin_level"][IG]["1.0"]["mSCF1"])
    ig_at_k_bin = score_indices(rankings[IG][:k_bin], correlations, n_bins)["mSCF1"]
    if abs(ig_at_k_bin - fair_ig) > SCORE_TOLERANCE:
        raise ValueError(f"IG at K_bin {ig_at_k_bin} != saved fair-scoring {fair_ig}")

    # --- Gate 3 (GBM/CAC): m = 1 rescores like the saved legacy metrics. ---
    legacy_check = None
    if gbm_cac:
        legacy_metrics = json.loads(args.legacy_metrics.read_text(encoding="utf-8"))
        m1_indices = nearest_unique_indices(
            mz, read_peaks(args.retune_dir / "m1.0" / "learned_peaks.csv"))
        _, difference = check_legacy(m1_indices, legacy_metrics, correlations, n_bins, k_bin)
        legacy_check = {"legacy_rescore_minus_saved": difference,
                        "unique_bins": int(len(m1_indices))}

    # --- Count-matched scores at every multiplier. ---
    per_multiplier = {}
    for name in MULTIPLIER_LABELS:
        selection = json.loads((args.retune_dir / name / "selection.json").read_text(
            encoding="utf-8"))
        indices = nearest_unique_indices(
            mz, read_peaks(args.retune_dir / name / "learned_peaks.csv"))
        record = count_matched(rankings, indices, correlations, n_bins)
        record["selection"] = selection
        per_multiplier[name] = record

    summary = {
        "status": "complete",
        "protocol": "protocol 18 Section 6.8 (msiPL Beta re-tune; count-matched)",
        "dataset": args.input.stem,
        "K_bin": k_bin,
        "provenance": {
            "input": file_record(args.input),
            "attribution_summary": file_record(args.attribution_dir / "summary.json"),
            "saved_evaluation_summary": file_record(args.saved_evaluation_dir / "summary.json"),
            "saved_fair_summary": file_record(args.saved_fair_dir / "summary.json"),
            "retune_summary": file_record(args.retune_dir / "summary.json"),
            "legacy_metrics": (file_record(args.legacy_metrics) if gbm_cac else None),
            "code": code_record(code_paths() + [Path(__file__).resolve()]),
        },
        "checks": {"posterior_max_abs_difference": posterior_difference,
                   "saved_prefix_lengths": prefix_lengths,
                   "ig_mSCF1_at_K_bin": ig_at_k_bin,
                   "gbm_cac_m1_legacy_check": legacy_check},
        "scoring": "bin level, all classes; legacy and every ranking at the legacy list's "
                   "unique-bin count n_m",
        "per_multiplier": per_multiplier,
        "runtime_seconds": time.perf_counter() - started,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    atomic_write_json(summary_path, summary)
    print(json.dumps({m: {"n": r["n_unique_bins"], "status": r["selection"]["status"],
                          "ig_minus_legacy": round(r["ig_minus_legacy"], 4)}
                      for m, r in per_multiplier.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
