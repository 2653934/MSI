#!/usr/bin/env python3
"""Gate (a)/(b): fair bin/peak scoring and simple saved-artifact baselines.

No retraining and no GPU. For one section and one frozen IG arm this script:

1. reproduces the saved production IG and first-layer-L2 lists and their
   mSCF1 exactly, and the saved legacy msiPL scores under a strict rule
   (otherwise it stops);
2. scores label-free baselines (GMM-posterior PCC variants, mean intensity,
   variance, Moran's I, random) and the labelled supervised oracle ceiling at
   K_bin and at the predeclared budget multipliers;
3. reports partition-free collapse diagnostics (rule A runs);
4. only with a reviewer-approved partition file, adds matched peak-level
   scoring at K_peak and the K_bin collapse under each approved partition.

Every reported peak-level number can be reconstructed from the saved
selections, ranking prefixes and hashes. An existing result is reused only if
its provenance block is identical; otherwise the script stops.
Protocol: docs/research/18 Fair Scoring and Simple Baselines Protocol.md.
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

from evaluate_msipl_massnet_peaks import (
    THRESHOLDS,
    nearest_unique_indices,
    true_indices_at_threshold,
)
from evaluate_spatial_msipl_attributed_peaks import (
    load_correlations,
    read_h5_metadata,
    score_indices,
)
import evaluate_msipl_massnet_peaks
import evaluate_spatial_msipl_attributed_peaks
from spatial_msipl import peak_groups, peak_selection, provenance, simple_baselines
from spatial_msipl.peak_groups import (
    P1_DEFAULTS,
    P3_DEFAULTS,
    contiguous_runs,
    first_k_distinct_groups,
    group_reference_sets,
    groups_of_selection,
    max_attainable_f1,
    partition_hash,
    score_groups,
)
from spatial_msipl.provenance import (
    StaleResultError,
    array_sha256,
    atomic_write_json,
    check_existing,
    code_record,
    file_record,
    require_slurm,
)
from spatial_msipl.simple_baselines import (
    BUDGET_MULTIPLIERS,
    RANDOM_SEED,
    budgets,
    check_posterior_against_saved,
    gmm_posterior_numpy,
    moore_edges,
    morans_i_per_feature,
    nan_to_lowest,
    one_hot_maps,
    pearson_features_vs_maps,
    posterior_pcc_rankings,
    production_ig_ranking,
    production_l2_ranking,
    random_rankings,
    rank_descending,
    supervised_oracle_ranking,
)

EVALUATION_VERSION = 2
PROTOCOL = "docs/research/18 Fair Scoring and Simple Baselines Protocol.md (v3)"
PARTITION_PARAMETERS = {"P1": P1_DEFAULTS, "P3": P3_DEFAULTS}
# IG/L2/legacy are rescored with the same rule, data and scorer functions that
# produced the saved values; only floating summation order can differ, which
# cannot change integer confusion counts unless a PCC sits within ~1e-12 of a
# decision boundary. Integer counts must therefore match exactly and mSCF1 to
# 1e-12; any difference stops the run for documentation rather than continuing.
SCORE_TOLERANCE = 1e-12
ORACLE_LABEL = ("supervised oracle ceiling: maximum signed expert-class PCC, the same "
                "convention as the reference set; not deployable")
COMPLETE = "complete"


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--attribution-dir", required=True, type=Path)
    parser.add_argument("--saved-evaluation-dir", required=True, type=Path,
                        help="existing matched evaluation folder for this arm")
    parser.add_argument("--legacy-peaks", required=True, type=Path)
    parser.add_argument("--legacy-metrics", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--partition-dir", type=Path,
                        help="audit_peak_partitions.py output for this section")
    parser.add_argument("--partition-approval", type=Path,
                        help="reviewer-written partition_approval.json")
    parser.add_argument("--random-draws", type=int, default=100)
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--allow-outside-slurm", action="store_true",
                        help="tests only; real sections must run inside Slurm")
    return parser.parse_args()


def code_paths():
    modules = (peak_groups, peak_selection, provenance, simple_baselines,
               evaluate_msipl_massnet_peaks, evaluate_spatial_msipl_attributed_peaks)
    return [Path(__file__).resolve()] + [Path(m.__file__).resolve() for m in modules]


def read_saved_list(path):
    with open(path, newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    rows.sort(key=lambda row: int(row["rank"]))
    return np.asarray([int(row["bin_index"]) for row in rows], dtype=np.int64)


def load_approval(args, dataset):
    """Return ({name: expected_hash}, approval_record) without loading arrays."""
    if args.partition_approval is None:
        return {}, None
    if args.partition_dir is None:
        raise ValueError("--partition-approval requires --partition-dir")
    approval = json.loads(args.partition_approval.read_text(encoding="utf-8"))
    expected = {}
    for name, record in approval.get("partitions", {}).items():
        if name not in PARTITION_PARAMETERS:
            raise ValueError(f"unknown partition in approval: {name}")
        if record.get("parameters") != PARTITION_PARAMETERS[name]:
            raise ValueError(f"{name}: approved parameters differ from the protocol")
        if dataset in record.get("sections", {}):
            expected[name] = record["sections"][dataset]
    return expected, file_record(args.partition_approval)


def expected_provenance(args, dataset, approved_hashes, approval_record, source_paths):
    parameters = {
        "thresholds": list(THRESHOLDS),
        "budget_multipliers": list(BUDGET_MULTIPLIERS),
        "random_draws": args.random_draws,
        "random_seed": RANDOM_SEED,
        "score_tolerance": SCORE_TOLERANCE,
        "approved_partition_parameters": {
            name: PARTITION_PARAMETERS[name] for name in sorted(approved_hashes)},
    }
    return {
        "evaluation_version": EVALUATION_VERSION,
        "protocol": PROTOCOL,
        "dataset": dataset,
        "parameters": parameters,
        "input": file_record(args.input),
        "source_artifacts": {name: file_record(path) for name, path in source_paths.items()},
        "partition_approval": approval_record,
        "approved_partition_hashes": approved_hashes,
        "code": code_record(code_paths()),
    }


def tic_statistics(path, pixels_first, n_bins, chunk_size, maps, sources, targets):
    """One chunked pass over TIC-normalised spectra (the VAE's input representation)."""
    import h5py

    with h5py.File(path, "r") as handle:
        data = handle["Data"]

        def block(start, stop):
            if pixels_first:
                return np.asarray(data[:, start:stop], dtype=np.float64)
            return np.asarray(data[start:stop, :], dtype=np.float64).T

        n_pixels = data.shape[0] if pixels_first else data.shape[1]
        tic = np.zeros(n_pixels)
        for start in range(0, n_bins, chunk_size):
            tic += block(start, min(start + chunk_size, n_bins)).sum(axis=1)
        scale = np.zeros_like(tic)
        np.divide(1.0, tic, out=scale, where=tic > 0)

        stats = {name: np.zeros(n_bins) for name in ("mean_intensity", "variance", "morans_i")}
        pcc = {name: np.zeros((n_bins, value.shape[1])) for name, value in maps.items()}
        for start in range(0, n_bins, chunk_size):
            stop = min(start + chunk_size, n_bins)
            values = block(start, stop) * scale[:, None]
            stats["mean_intensity"][start:stop] = values.mean(axis=0)
            stats["variance"][start:stop] = values.var(axis=0)
            stats["morans_i"][start:stop] = morans_i_per_feature(values, sources, targets)
            for name, value in maps.items():
                pcc[name][start:stop] = pearson_features_vs_maps(values, value)
    return stats, pcc, int(np.count_nonzero(tic == 0))


def runs_summary(indices):
    unique, run_id = contiguous_runs(indices)
    runs = int(run_id[-1]) + 1 if len(run_id) else 0
    return {"bins": int(len(unique)), "contiguous_runs": runs,
            "bins_per_run": float(len(unique) / runs) if runs else 0.0}


def check_legacy(legacy_indices, legacy_metrics, correlations, n_bins, k_bin):
    """Strict legacy reproduction; any difference stops the run."""
    if int(legacy_metrics["unique_nearest_bins"]) != k_bin:
        raise ValueError("legacy unique_nearest_bins differs from K_bin")
    if len(legacy_indices) != k_bin:
        raise ValueError(f"snapped legacy list has {len(legacy_indices)} unique bins, "
                         f"expected K_bin={k_bin}")
    rescored = score_indices(legacy_indices, correlations, n_bins)
    for threshold in map(str, THRESHOLDS):
        saved = legacy_metrics["threshold_results"][threshold]["mixed_classes"]
        new = rescored["threshold_results"][threshold]["mixed_classes"]
        for key in ("true_positive", "false_positive", "false_negative"):
            if int(saved[key]) != int(new[key]):
                raise ValueError(
                    f"legacy rescore differs at PCC {threshold} ({key}: saved "
                    f"{saved[key]}, rescored {new[key]}); stop and document the scorer "
                    "difference before continuing")
    difference = rescored["mSCF1"] - float(legacy_metrics["mSCF1"])
    if abs(difference) > SCORE_TOLERANCE:
        raise ValueError(f"legacy mSCF1 rescore differs by {difference}")
    return rescored, difference


def main():
    args = parse_arguments()
    require_slurm(args.allow_outside_slurm)
    started = time.perf_counter()
    dataset = args.input.stem
    args.output.mkdir(parents=True, exist_ok=True)

    saved_summary_path = args.saved_evaluation_dir / "summary.json"
    saved_summary = json.loads(saved_summary_path.read_text(encoding="utf-8"))
    k_bin = int(saved_summary["matched_peak_evaluation"]["count"])
    source_paths = {
        "attributions": args.attribution_dir / "attributions.npz",
        "coordinates_and_gmm": args.attribution_dir / "coordinates_and_gmm.npz",
        "gmm_parameters": args.attribution_dir / "gmm_parameters.npz",
        "latent_mean": args.attribution_dir / "latent_mean.npy",
        "attribution_summary": args.attribution_dir / "summary.json",
        "saved_evaluation_summary": saved_summary_path,
        "saved_ig_list": args.saved_evaluation_dir / f"ig_matched_{k_bin}_bins.csv",
        "saved_l2_list": args.saved_evaluation_dir / f"first_layer_l2_matched_{k_bin}_bins.csv",
        "legacy_peaks": args.legacy_peaks,
        "legacy_metrics": args.legacy_metrics,
    }
    approved_hashes, approval_record = load_approval(args, dataset)
    if approved_hashes:
        source_paths["partitions"] = args.partition_dir / "partitions.npz"
        source_paths["partition_audit_summary"] = args.partition_dir / "summary.json"
    expected = expected_provenance(args, dataset, approved_hashes, approval_record,
                                   source_paths)
    summary_path = args.output / "summary.json"
    try:
        state = check_existing(summary_path, expected, COMPLETE)
    except StaleResultError as error:
        print(f"STALE: {error}", file=sys.stderr)
        raise SystemExit(3)
    if state == "valid":
        print(f"Existing result matches current provenance; skipped: {summary_path}")
        return

    mz, raw_labels, x, y, pixels_first = read_h5_metadata(args.input)
    n_bins = len(mz)
    attributions = np.load(source_paths["attributions"])
    saved_gmm = np.load(source_paths["coordinates_and_gmm"])
    gmm_parameters = dict(np.load(source_paths["gmm_parameters"]))
    latent = np.load(source_paths["latent_mean"])
    if not (np.array_equal(x, saved_gmm["x"]) and np.array_equal(y, saved_gmm["y"])):
        raise ValueError("attribution coordinates do not match the HDF5 input")

    # --- Approved partitions are verified before any scoring. ---
    approved_arrays = {}
    if approved_hashes:
        arrays = np.load(source_paths["partitions"])
        if not np.array_equal(arrays["mz"], mz):
            raise ValueError("partition m/z axis differs from the HDF5 input")
        for partition, expected_hash in approved_hashes.items():
            group_of_bin = arrays[f"{partition}_group_of_bin"]
            if partition_hash(group_of_bin) != expected_hash:
                raise ValueError(f"{partition}: partition hash differs from the approved hash")
            approved_arrays[partition] = (group_of_bin, arrays[f"{partition}_apex"])

    # --- Provenance checks: posterior, IG, L2 and legacy must reproduce. ---
    posterior = gmm_posterior_numpy(latent, **gmm_parameters)
    posterior_difference = check_posterior_against_saved(
        posterior, saved_gmm["component"], saved_gmm["assigned_posterior"])
    rankings = {
        "integrated_gradients": production_ig_ranking(attributions),
        "first_layer_l2": production_l2_ranking(attributions),
    }
    for name, key in (("integrated_gradients", "saved_ig_list"),
                      ("first_layer_l2", "saved_l2_list")):
        if not np.array_equal(rankings[name][:k_bin], read_saved_list(source_paths[key])):
            raise ValueError(f"{name}: reconstructed ranking differs from saved list")

    correlations = load_correlations(args.input, raw_labels, n_bins, pixels_first,
                                     args.chunk_size)
    checks = {"posterior_max_abs_difference": posterior_difference}
    for name in ("integrated_gradients", "first_layer_l2"):
        rescored = score_indices(rankings[name][:k_bin], correlations, n_bins)["mSCF1"]
        saved = float(saved_summary["matched_peak_evaluation"]["methods"][name]["mSCF1"])
        if abs(rescored - saved) > SCORE_TOLERANCE:
            raise ValueError(f"{name}: rescored mSCF1 {rescored} != saved {saved}")
        checks[f"{name}_mSCF1_reproduced"] = saved

    legacy_values = np.genfromtxt(args.legacy_peaks, delimiter=",", names=True)
    legacy_mz = np.asarray(legacy_values[legacy_values.dtype.names[0]]).reshape(-1)
    legacy_indices = nearest_unique_indices(mz, legacy_mz)
    legacy_metrics = json.loads(args.legacy_metrics.read_text(encoding="utf-8"))
    legacy_score, legacy_difference = check_legacy(
        legacy_indices, legacy_metrics, correlations, n_bins, k_bin)
    checks["legacy_rescore_minus_saved"] = legacy_difference
    checks["legacy_unique_snapped_bins"] = int(len(legacy_indices))

    # --- Label-free baselines on TIC-normalised spectra, and the oracle. ---
    components = saved_gmm["component"].astype(np.int64)
    sources, targets = moore_edges(x, y)
    maps = {"soft": posterior, "hard": one_hot_maps(components, posterior.shape[1])}
    stats, pcc, zero_tic = tic_statistics(args.input, pixels_first, n_bins,
                                          args.chunk_size, maps, sources, targets)
    rankings.update(posterior_pcc_rankings(pcc["soft"], pcc["hard"]))
    rankings["mean_intensity"] = rank_descending(stats["mean_intensity"])
    rankings["variance"] = rank_descending(stats["variance"])
    rankings["morans_i"] = rank_descending(nan_to_lowest(stats["morans_i"]))
    rankings["oracle"] = supervised_oracle_ranking(correlations)
    random_draws = random_rankings(n_bins, args.random_draws)

    # --- Bin-level scores at K_bin and budget multipliers. ---
    budget_values = budgets(k_bin, n_bins)
    bin_level = {name: {m: score_indices(r[:b], correlations, n_bins)
                        for m, b in budget_values.items()}
                 for name, r in rankings.items()}
    random_scores = {m: [score_indices(r[:b], correlations, n_bins)["mSCF1"]
                         for r in random_draws]
                     for m, b in budget_values.items()}
    bin_level["random"] = {m: {"mSCF1_mean": float(np.mean(v)),
                               "mSCF1_p05": float(np.percentile(v, 5)),
                               "mSCF1_p95": float(np.percentile(v, 95))}
                           for m, v in random_scores.items()}
    bin_level["legacy_msipl"] = {"1.0": legacy_score}

    reference_bins = {
        t: set().union(*(true_indices_at_threshold(correlations[c], t)
                         for c in sorted(correlations)))
        for t in THRESHOLDS
    }
    ceilings = {m: {str(t): max_attainable_f1(b, len(reference_bins[t])) for t in THRESHOLDS}
                for m, b in budget_values.items()}
    collapse_rule_a = {name: runs_summary(r[:k_bin]) for name, r in rankings.items()}
    collapse_rule_a["legacy_msipl"] = runs_summary(legacy_indices)

    # --- Peak-level scoring only under reviewer-approved partitions. ---
    peak_level = {}
    selections = {}
    prefix_length = 2 * k_bin
    for partition, expected_hash in sorted(approved_hashes.items()):
        group_of_bin, apex = approved_arrays[partition]
        n_groups = int(group_of_bin.max()) + 1
        reference_groups = group_reference_sets(reference_bins, apex)
        k_peak = len(reference_groups[0.4])
        record = {"partition_sha256": expected_hash, "groups": n_groups, "K_peak": k_peak,
                  "reference_groups": {str(t): len(v) for t, v in reference_groups.items()},
                  "methods": {}}
        selections[f"{partition}__reference_groups_0.4"] = np.asarray(
            sorted(reference_groups[0.4]), dtype=np.int64)
        for name, ranking in rankings.items():
            collapsed = np.asarray(sorted(groups_of_selection(ranking[:k_bin], group_of_bin)),
                                   dtype=np.int64)
            matched, consumed = first_k_distinct_groups(ranking, group_of_bin, k_peak)
            prefix_length = max(prefix_length, consumed)
            selections[f"{partition}__{name}__matched_groups"] = matched
            selections[f"{partition}__{name}__matched_apex_bins"] = apex[matched]
            selections[f"{partition}__{name}__collapse_groups"] = collapsed
            record["methods"][name] = {
                "collapse_K_bin": {"distinct_groups": int(len(collapsed)),
                                   **score_groups(collapsed.tolist(), reference_groups, n_groups)},
                "matched_K_peak": {"bins_consumed": int(consumed),
                                   "selected_groups_sha256": array_sha256(matched),
                                   **score_groups(matched.tolist(), reference_groups, n_groups)},
            }
        legacy_groups = np.asarray(sorted(groups_of_selection(legacy_indices, group_of_bin)),
                                   dtype=np.int64)
        selections[f"{partition}__legacy_msipl__collapse_groups"] = legacy_groups
        record["methods"]["legacy_msipl"] = {
            "collapse_K_bin": {"distinct_groups": int(len(legacy_groups)),
                               **score_groups(legacy_groups.tolist(), reference_groups, n_groups)},
            "matched_K_peak": ("not available: fixed list; requires a Beta re-tune to "
                               "K_peak. IG-versus-legacy is therefore not a matched "
                               "peak-level comparison; the collapse diagnostic answers a "
                               "narrower question"),
        }
        random_matched = []
        random_consumed = []
        for draw in random_draws:
            groups, consumed = first_k_distinct_groups(draw, group_of_bin, k_peak)
            random_consumed.append(consumed)
            random_matched.append(score_groups(groups.tolist(), reference_groups,
                                               n_groups)["mSCF1"])
        record["methods"]["random"] = {"matched_K_peak": {
            "mSCF1_mean": float(np.mean(random_matched)),
            "mSCF1_p05": float(np.percentile(random_matched, 5)),
            "mSCF1_p95": float(np.percentile(random_matched, 95)),
            "bins_consumed_max": int(max(random_consumed)),
            "reconstruct_from": f"random seed {RANDOM_SEED}, {args.random_draws} permutations",
        }}
        peak_level[partition] = record

    ranking_record = {name: {"full_ranking_sha256": array_sha256(r),
                             "saved_prefix_length": int(min(prefix_length, len(r)))}
                      for name, r in rankings.items()}
    np.savez_compressed(args.output / "rankings_prefix.npz",
                        **{name: r[:prefix_length] for name, r in rankings.items()},
                        legacy_msipl=legacy_indices)
    if selections:
        np.savez_compressed(args.output / "peak_level_selections.npz", **selections)

    summary = {
        "status": COMPLETE,
        "provenance": expected,
        "dataset": dataset,
        "K_bin": k_bin,
        "budgets": budget_values,
        "provenance_checks": checks,
        "zero_tic_pixels": zero_tic,
        "representation_for_label_free_baselines": "TIC-normalised spectra",
        "evaluation_reference": "raw-intensity PCC, existing nearest-threshold rule",
        "oracle_label": ORACLE_LABEL,
        "asymmetry_note": "PCC baselines use all pixels; IG used 12 sampled pixels per component",
        "rankings": ranking_record,
        "random_draws_full_sha256": array_sha256(np.concatenate(random_draws)),
        "reference_bins": {str(t): len(v) for t, v in reference_bins.items()},
        "max_attainable_f1": ceilings,
        "bin_level": bin_level,
        "collapse_rule_a_first_K_bin": collapse_rule_a,
        "peak_level_status": ("approved partitions scored" if approved_hashes else
                              "not requested: no partition approval supplied"),
        "peak_level": peak_level,
        "outputs": {"rankings_prefix": "rankings_prefix.npz",
                    "peak_level_selections": "peak_level_selections.npz" if selections else None},
        "runtime_seconds": time.perf_counter() - started,
    }
    atomic_write_json(summary_path, summary)
    print(json.dumps({name: v["1.0"]["mSCF1"] for name, v in bin_level.items()
                      if "1.0" in v and "mSCF1" in v["1.0"]}, indent=2))


if __name__ == "__main__":
    main()
