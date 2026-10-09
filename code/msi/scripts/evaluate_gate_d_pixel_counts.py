#!/usr/bin/env python3
"""Gate (d) pixel-count evaluation for one development section and one IG arm.

CPU only; it reads the three gate-(d) IG runs (n = 12, 48, 192) written by
slurm_jobs/run_gate_d_pixel_count_ig.sh. Protocol 18 Section 6
("Pixel-count run specification"):

1. Every run must use the production GMM assignment, so that the pixel count
   is the only variable changed; otherwise the script stops.
2. Reproduction gate: the n = 12 rerun must select the identical bin set at
   K_bin as the saved production IG list and reproduce the saved mSCF1 to
   1e-12. Order differences within the top K_bin and the maximum relative
   attribution difference are recorded but do not gate, because GPU
   nondeterminism can swap near-equal bins and mSCF1 at K_bin depends only on
   the set. On failure a 'reproduction_failed' summary is written, 48 and 192
   are not scored, and the script exits with code 4.
3. Each IG(n) ranking is scored at K_bin and the Section 2 budget multipliers
   with the existing scorer. The change is mSCF1(n) - mSCF1(n=12, saved).
   Budget-multiplier scores depend on order and are descriptive only.
4. IG(n) - posterior-|PCC| (from the gate (a)/(b) bin-level summary) is
   reported descriptively, not as a verdict.

The rule itself (>= +0.02 on both sections, per arm) is applied by
summarise_gate_d_pixel_counts.py. Restart rule as in Section 8.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from evaluate_fair_scoring_baselines import SCORE_TOLERANCE, read_saved_list
from evaluate_spatial_msipl_attributed_peaks import (
    load_correlations,
    read_h5_metadata,
    score_indices,
)
import evaluate_fair_scoring_baselines
import evaluate_spatial_msipl_attributed_peaks
from spatial_msipl import gate_d_helpers, provenance, simple_baselines
from spatial_msipl.gate_d_helpers import PIXEL_COUNTS, mark_distinct_arms
from spatial_msipl.provenance import (
    StaleResultError,
    atomic_write_json,
    check_existing,
    code_record,
    file_record,
    require_slurm,
)
from spatial_msipl.simple_baselines import (
    BUDGET_MULTIPLIERS,
    balanced_ranking_from_component_scores,
    budgets,
    production_ig_scores,
)

EVALUATION_VERSION = 1
PROTOCOL = ("docs/research/18 Fair Scoring and Simple Baselines Protocol.md (v3.2), "
            "Section 6 pixel-count run specification")
COMPLETE = "complete"
REPRODUCTION_FAILED = "reproduction_failed"


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path,
                        help="gate_d_pixel_counts/<section>_seed1/<arm> holding n12, n48, n192")
    parser.add_argument("--production-attribution-dir", required=True, type=Path)
    parser.add_argument("--saved-evaluation-dir", required=True, type=Path)
    parser.add_argument("--fair-scoring-summary", required=True, type=Path,
                        help="bin_level_only/<section>_seed1/<arm>/summary.json")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--allow-outside-slurm", action="store_true",
                        help="tests only; real sections must run inside Slurm")
    return parser.parse_args()


def code_paths():
    modules = (gate_d_helpers, provenance, simple_baselines,
               evaluate_fair_scoring_baselines, evaluate_spatial_msipl_attributed_peaks)
    return [Path(__file__).resolve()] + [Path(m.__file__).resolve() for m in modules]


def ig_ranking(attributions):
    return balanced_ranking_from_component_scores(production_ig_scores(attributions))


def max_relative_attribution_difference(new, saved):
    """Per numeric array: max |new - saved| / max |saved|; plus the largest over arrays."""
    per_array = {}
    for key in sorted(set(new.files) & set(saved.files)):
        a, b = np.asarray(new[key], dtype=np.float64), np.asarray(saved[key], dtype=np.float64)
        if a.shape != b.shape or not np.issubdtype(b.dtype, np.number):
            continue
        scale = float(np.max(np.abs(b))) if b.size else 0.0
        difference = float(np.max(np.abs(a - b))) if b.size else 0.0
        per_array[key] = difference / scale if scale > 0 else difference
    return {"per_array": per_array,
            "maximum": max(per_array.values()) if per_array else None}


def reproduction_check(new_prefix, saved_list, rescored, saved_mscf1):
    """Gate: identical bin set at K_bin and saved mSCF1 to 1e-12 (order not gating)."""
    new_prefix, saved_list = np.asarray(new_prefix), np.asarray(saved_list)
    same_set = set(new_prefix.tolist()) == set(saved_list.tolist())
    record = {
        "identical_bin_set": bool(same_set),
        "bins_only_in_rerun": int(len(set(new_prefix.tolist()) - set(saved_list.tolist()))),
        "order_differing_positions": int(np.sum(new_prefix != saved_list))
        if len(new_prefix) == len(saved_list) else None,
        "saved_mSCF1": saved_mscf1,
        "rescored_mSCF1": rescored,
        "mSCF1_difference": rescored - saved_mscf1,
    }
    if not same_set:
        record["error"] = "selected bin set at K_bin differs from the saved production list"
    elif abs(rescored - saved_mscf1) > SCORE_TOLERANCE:
        record["error"] = f"rescored mSCF1 {rescored} != saved {saved_mscf1}"
    record["passed"] = "error" not in record
    return record


def sample_counts(run_summary, n):
    """Actual attribution pixels per component, checked against the request."""
    record = run_summary["integrated_gradients"].get("nested_attribution_samples")
    if not record:
        raise ValueError(f"n={n}: run was not made with --attribution-total")
    counts = {}
    for component, split in sorted(record.items()):
        if int(split["requested_attribution"]) != n:
            raise ValueError(f"n={n}: component {component} requested "
                             f"{split['requested_attribution']}")
        counts[component] = int(split["actual_attribution"])
    return counts


def run_signature(run_summary):
    """Fields that must stay fixed while only the attribution count changes."""
    ig = run_summary["integrated_gradients"]
    return {
        "attribution_version": run_summary["attribution_version"],
        "variant": run_summary["variant"],
        "dataset": run_summary["dataset"],
        "model_state_sha256": run_summary["model_state_sha256"],
        "model_configuration": run_summary["model_configuration"],
        "input_specification": run_summary["input_specification"],
        "pixels": run_summary["pixels"],
        "spectral_bins": run_summary["spectral_bins"],
        "gmm": run_summary["gmm"],
        "integrated_gradients": {
            key: ig[key] for key in (
                "baseline", "target", "steps", "integration",
                "attribution_pixels_per_component", "central_context_combination",
                "sampling_seed", "selection_seed",
            )
        },
    }


def main():
    args = parse_arguments()
    require_slurm(args.allow_outside_slurm)
    started = time.perf_counter()
    args.output.mkdir(parents=True, exist_ok=True)
    dataset = args.input.stem
    arm = args.run_root.name

    saved_summary_path = args.saved_evaluation_dir / "summary.json"
    saved_summary = json.loads(saved_summary_path.read_text(encoding="utf-8"))
    k_bin = int(saved_summary["matched_peak_evaluation"]["count"])
    saved_ig_mscf1 = float(saved_summary["matched_peak_evaluation"]["methods"]
                           ["integrated_gradients"]["mSCF1"])
    run_dirs = {n: args.run_root / f"n{n}" for n in PIXEL_COUNTS}
    source_paths = {
        "saved_evaluation_summary": saved_summary_path,
        "saved_ig_list": args.saved_evaluation_dir / f"ig_matched_{k_bin}_bins.csv",
        "production_coordinates_and_gmm":
            args.production_attribution_dir / "coordinates_and_gmm.npz",
        "production_attributions": args.production_attribution_dir / "attributions.npz",
        "fair_scoring_summary": args.fair_scoring_summary,
    }
    for n, directory in run_dirs.items():
        source_paths[f"n{n}_attributions"] = directory / "attributions.npz"
        source_paths[f"n{n}_coordinates_and_gmm"] = directory / "coordinates_and_gmm.npz"
        source_paths[f"n{n}_summary"] = directory / "summary.json"
    expected = {
        "evaluation_version": EVALUATION_VERSION,
        "protocol": PROTOCOL,
        "dataset": dataset,
        "arm": arm,
        "parameters": {"pixel_counts": list(PIXEL_COUNTS),
                       "budget_multipliers": list(BUDGET_MULTIPLIERS),
                       "score_tolerance": SCORE_TOLERANCE},
        "input": file_record(args.input),
        "source_artifacts": {name: file_record(path) for name, path in source_paths.items()},
        "code": code_record(code_paths()),
    }
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

    # 1. Same GMM assignment as production in every run.
    production_gmm = np.load(source_paths["production_coordinates_and_gmm"])
    run_summaries, rankings, counts = {}, {}, {}
    signature = None
    for n in PIXEL_COUNTS:
        run_summaries[n] = json.loads(source_paths[f"n{n}_summary"].read_text(encoding="utf-8"))
        if run_summaries[n].get("status") != "valid":
            raise ValueError(f"n={n}: IG run status is {run_summaries[n].get('status')!r}, "
                             "not 'valid'; refusing to score incomplete attributions")
        current_signature = run_signature(run_summaries[n])
        if current_signature["variant"] != arm or Path(current_signature["dataset"]).stem != dataset:
            raise ValueError(f"n={n}: run summary dataset or arm does not match the request")
        if signature is None:
            signature = current_signature
        elif current_signature != signature:
            raise ValueError(f"n={n}: run configuration differs from n=12; attribution "
                             "pixel count is not the only variable changed")
        gmm = np.load(source_paths[f"n{n}_coordinates_and_gmm"])
        if not (np.array_equal(gmm["x"], x) and np.array_equal(gmm["y"], y)):
            raise ValueError(f"n={n}: coordinates do not match the HDF5 input")
        if not np.array_equal(gmm["component"], production_gmm["component"]):
            raise ValueError(f"n={n}: GMM assignment differs from production; the pixel "
                             "count would not be the only variable changed")
        counts[n] = sample_counts(run_summaries[n], n)
        rankings[n] = ig_ranking(np.load(source_paths[f"n{n}_attributions"]))
    distinct = mark_distinct_arms(counts)

    correlations = load_correlations(args.input, raw_labels, n_bins, pixels_first,
                                     args.chunk_size)

    # 2. Reproduction gate at n = 12 (set and mSCF1 gate; order and arrays recorded).
    reproduction = reproduction_check(
        rankings[12][:k_bin], read_saved_list(source_paths["saved_ig_list"]),
        score_indices(rankings[12][:k_bin], correlations, n_bins)["mSCF1"], saved_ig_mscf1)
    reproduction["max_relative_attribution_difference"] = max_relative_attribution_difference(
        np.load(source_paths["n12_attributions"]),
        np.load(source_paths["production_attributions"]))

    result = {
        "status": COMPLETE if reproduction["passed"] else REPRODUCTION_FAILED,
        "provenance": expected,
        "K_bin": k_bin,
        "n12_reproduction": reproduction,
        "actual_attribution_pixels": {str(n): c for n, c in counts.items()},
        "distinct_from_next_smaller": {str(n): bool(f) for n, f in distinct.items()},
    }
    if not reproduction["passed"]:
        result["note"] = ("n=12 rerun did not reproduce the saved production IG list; "
                          "48 and 192 are not scored (protocol Section 6).")
        result["runtime_seconds"] = time.perf_counter() - started
        atomic_write_json(summary_path, result)
        print(f"REPRODUCTION FAILED: {reproduction['error']}", file=sys.stderr)
        raise SystemExit(4)

    # 3. Score every n at K_bin and the budget multipliers.
    budget_values = budgets(k_bin, n_bins)
    fair = json.loads(args.fair_scoring_summary.read_text(encoding="utf-8"))["bin_level"]
    posterior = {m: float(fair["posterior_abs_pcc_balanced"][m]["mSCF1"]) for m in budget_values}
    scores = {str(n): {m: score_indices(rankings[n][:b], correlations, n_bins)["mSCF1"]
                       for m, b in budget_values.items()}
              for n in PIXEL_COUNTS}
    reference = set(rankings[12][:k_bin].tolist())
    result.update({
        "mSCF1": scores,
        "change_vs_saved_n12_at_K_bin": {
            str(n): scores[str(n)]["1.0"] - saved_ig_mscf1 for n in PIXEL_COUNTS},
        "descriptive_ig_minus_posterior_abs_pcc": {
            str(n): {m: scores[str(n)][m] - posterior[m] for m in budget_values}
            for n in PIXEL_COUNTS},
        "jaccard_vs_n12_at_K_bin": {
            str(n): len(reference & set(rankings[n][:k_bin].tolist()))
            / len(reference | set(rankings[n][:k_bin].tolist())) for n in PIXEL_COUNTS},
        "ig_runtime_seconds": {str(n): run_summaries[n].get("runtime_seconds")
                               for n in PIXEL_COUNTS},
        "runtime_seconds": time.perf_counter() - started,
    })
    atomic_write_json(summary_path, result)
    print(json.dumps(result["change_vs_saved_n12_at_K_bin"], indent=2))


if __name__ == "__main__":
    main()
