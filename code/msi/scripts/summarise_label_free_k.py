#!/usr/bin/env python3
"""Label-free K decision table (protocol 18 Section 6.10; decision log D56). Local only.

Reads, for the 48 seed-1 section-arms, the label-free-K runs
(results/experiments/label_free_k_20261104/) and their bin-level fair scoring
(results/diagnostics/fair_scoring_baselines/label_free_k_20261104/bin_level_only/),
and the production-K seed-1 fair scoring from the composite root the report uses.

Per section-arm the decisive step count is the first of 64, 128, 256, 512, 1024 whose
IG is valid (as run_label_free_k_fair_scoring.sh). "Not done" is a component under
44 px or IG still needs_more_ig_steps at 1024. A run still waiting for an escalation
or for fair scoring stops the summary (exit 1): nothing is labelled early.

Gate (stop, exit 5, nothing written but gate_failure.json): the K-independent
rankings (mean intensity, variance, Moran's I, oracle; GBM/CAC legacy msiPL) must
reproduce the production seed-1 bin-level mSCF1 at K_bin within 1e-6, with the same
K_bin.

Rule per collection x arm: "IG < posterior correlation is label-independent" holds
if posterior-|PCC| (balanced, soft) > IG at K_bin in >= 7/8 sections. Not-done
sections count against; "incomplete; no verdict" only when they decide the outcome.
Everything else is descriptive. Refuses to overwrite its output (exit 3).
"""

import argparse
import csv
import hashlib
import json
import statistics
import sys
from pathlib import Path

SECTIONS = {
    "GBM": ["GBM108_negative", "GBM108_positive", "GBM12_1", "GBM12_2",
            "GBM22_1", "GBM22_2", "GBM39_1", "GBM39_2"],
    "CAC": ["40TopL", "160TopL", "200TopL", "240TopL",
            "280TopL", "360TopL", "400TopL", "520TopL"],
    "RCC": ["RCC_MH0204_33", "RCC_UH0505_12", "RCC_UH0710_33", "RCC_UH9610_15",
            "RCC_UH9812_03", "RCC_UH9905_18", "RCC_UH9911_05", "RCC_UH9912_01"],
}
ARMS = ("central_only", "uniform_mean")
STEPS = (64, 128, 256, 512, 1024)
IG, CORRELATION = "integrated_gradients", "posterior_abs_pcc_balanced"
K_INDEPENDENT = ("mean_intensity", "variance", "morans_i", "oracle", "legacy_msipl")
LABEL_FREE_REFERENCES = ("mean_intensity", "variance", "morans_i", "legacy_msipl")
GATE_TOLERANCE = 1e-6
RULE_COUNT = 7
RULE_NAME = "IG < posterior correlation is label-independent"
RCC_LEGACY = "not rescored at the label-free K"
BOUNDARY_WORDING = "BIC's choice at the boundary of the tested range (K <= 6)"


class Pending(RuntimeError):
    """A run is not finished; no table is written."""


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def mscf1(summary, method):
    entry = summary["bin_level"].get(method)
    return None if entry is None else float(entry["1.0"]["mSCF1"])


def decisive_run(experiments, section, arm):
    """(steps, root) of the first valid step count, or (None, not-done reason)."""
    trajectory = []
    for steps in STEPS:
        root = experiments / f"{section}_seed1" / arm / f"steps{steps}"
        if (root / "not_done.json").exists():
            return None, load(root / "not_done.json")["reason"], trajectory
        summary_path = root / "attribution" / "summary.json"
        if not summary_path.exists():
            raise Pending(f"{section} {arm}: no run at {steps} steps yet ({root})")
        attribution = load(summary_path)
        completeness = attribution["integrated_gradients"]["completeness"]
        trajectory.append({
            "steps": steps,
            "median_normalized_residual": completeness["median_normalized_residual"],
            "p95_normalized_residual": completeness["percentile_95_normalized_residual"],
        })
        if attribution["status"] == "needs_more_ig_steps":
            continue
        if attribution["status"] != "valid":
            raise ValueError(f"{section} {arm}: unexpected IG status {attribution['status']}")
        if not load(root / "identity_check.json")["passed"]:
            raise ValueError(f"{section} {arm}: identity check failed at {steps} steps")
        if steps != 64 and not load(root / "gmm_gate_v2.json")["passed"]:
            raise ValueError(f"{section} {arm}: gate v2 failed at {steps} steps")
        return steps, root, trajectory
    return None, "IG completeness not reached at 1024 steps", trajectory


def production_summary(composite, collection, section, arm):
    scope = "rcc/bin_level_only" if collection == "RCC" else "bin_level_only"
    return (composite / "results/diagnostics/fair_scoring_baselines" / scope
            / f"{section}_seed1" / arm / "summary.json")


def rule_label(beats, not_done):
    """The predeclared label from the counts (P18 Section 6.10)."""
    if beats >= RULE_COUNT:
        return "holds"
    if beats + not_done < RULE_COUNT:
        return "does not hold"
    return "incomplete; no verdict"


def mean(values):
    values = [value for value in values if value is not None]
    return statistics.fmean(values) if values else None


def section_record(paths, collection, section, arm):
    experiments, fair, composite = paths
    steps, root_or_reason, trajectory = decisive_run(experiments, section, arm)
    first = experiments / f"{section}_seed1" / arm / "steps64"
    k_record = load(first / "label_free_k.json")
    record = {"collection": collection, "section": section, "arm": arm,
              "label_free_k": k_record["label_free_k"],
              "bic_selected_k": k_record["bic_selected_k"],
              "k_flag": k_record["flag"],
              "k_at_boundary": k_record["at_boundary_of_tested_range"],
              "production_k": k_record["production_k"],
              "ig_residual_trajectory": trajectory}
    reference_path = production_summary(composite, collection, section, arm)
    reference = load(reference_path)
    record["production_reference"] = str(reference_path)
    record["production_reference_sha256"] = hashlib.sha256(
        reference_path.read_bytes()).hexdigest()
    record["production"] = {IG: mscf1(reference, IG), CORRELATION: mscf1(reference, CORRELATION)}
    if steps is None:
        record.update({"status": "not done", "reason": root_or_reason})
        return record
    root = root_or_reason
    summary_path = fair / f"{section}_seed1" / arm / f"steps{steps}" / "summary.json"
    if not summary_path.exists():
        raise Pending(f"{section} {arm}: fair scoring missing ({summary_path})")
    summary = load(summary_path)
    if summary.get("status") != "complete":
        raise ValueError(f"{section} {arm}: fair scoring not complete")
    record.update({"status": "scored", "steps": steps, "K_bin": summary["K_bin"],
                   "fair_summary": str(summary_path)})
    record["label_free"] = {method: mscf1(summary, method)
                            for method in (IG, CORRELATION) + K_INDEPENDENT}
    gate = {}
    for method in K_INDEPENDENT:
        new, old = record["label_free"][method], mscf1(reference, method)
        if new is None and old is None:
            continue
        difference = None if new is None or old is None else new - old
        gate[method] = {"difference": difference,
                        "passed": difference is not None and abs(difference) <= GATE_TOLERANCE}
    record["k_independent_gate"] = {"K_bin_equal": summary["K_bin"] == reference["K_bin"],
                                    "methods": gate}
    record["k_independent_gate"]["passed"] = (
        record["k_independent_gate"]["K_bin_equal"]
        and all(entry["passed"] for entry in gate.values()))
    evaluation = root / ("peak_evaluation_released_target" if collection == "RCC"
                         else "peak_evaluation")
    agreement = load(evaluation / "summary.json")["cluster_mapping"]
    record["ari"] = agreement["adjusted_rand_index"]
    record["nmi"] = agreement["normalized_mutual_information"]
    record["correlation_minus_ig"] = (record["label_free"][CORRELATION]
                                      - record["label_free"][IG])
    record["production_correlation_minus_ig"] = (record["production"][CORRELATION]
                                                 - record["production"][IG])
    return record


def bic_cross_check(bic_roots, section, arm, record):
    """Descriptive: October posterior-|PCC| at the BIC K on the saved latent."""
    for root in bic_roots:
        path = root / f"{section}_seed1" / arm / "bic_k_sensitivity" / "summary.json"
        if path.exists() and record.get("status") == "scored":
            october = load(path)
            if int(october["tested_k"]) != record["label_free_k"]:
                return {"source": str(path), "note": "different K; not compared"}
            value = float(october["mSCF1_at_K_bin"][CORRELATION]["tested_k_mSCF1"])
            return {"source": str(path), "october_mSCF1": value,
                    "this_run_minus_october": record["label_free"][CORRELATION] - value}
    return None


def cell_summary(records, collection, arm):
    rows = [r for r in records if r["collection"] == collection and r["arm"] == arm]
    scored = [r for r in rows if r["status"] == "scored"]
    beats = sum(r["correlation_minus_ig"] > 0 for r in scored)
    not_done = len(rows) - len(scored)
    cell = {
        "collection": collection, "arm": arm, "sections": len(rows),
        "scored": len(scored), "not_done": not_done,
        "correlation_beats_ig": beats,
        "rule": RULE_NAME, "label": rule_label(beats, not_done),
        "label_free_k_values": sorted({r["label_free_k"] for r in rows}),
        "mean_correlation_minus_ig": mean(r["correlation_minus_ig"] for r in scored),
        "production_beats": sum(r["production_correlation_minus_ig"] > 0 for r in scored),
        "production_mean_correlation_minus_ig": mean(
            r["production_correlation_minus_ig"] for r in scored),
        "descriptive_means_label_free_k": {
            method: mean(r["label_free"][method] for r in scored)
            for method in (IG, CORRELATION) + LABEL_FREE_REFERENCES},
        "descriptive_means_production_k": {
            method: mean(r["production"][method] for r in scored) for method in (IG, CORRELATION)},
        "mean_ari": mean(r["ari"] for r in scored),
        "mean_nmi": mean(r["nmi"] for r in scored),
    }
    if collection == "RCC":
        cell["descriptive_means_label_free_k"]["legacy_msipl"] = RCC_LEGACY
    return cell


def arm_difference(records, collection):
    """Descriptive: uniform_mean - central_only at the label-free K, no label."""
    by_key = {(r["section"], r["arm"]): r for r in records
              if r["collection"] == collection and r["status"] == "scored"}
    result = {}
    for method in (IG, CORRELATION):
        differences = [by_key[(s, "uniform_mean")]["label_free"][method]
                       - by_key[(s, "central_only")]["label_free"][method]
                       for s in SECTIONS[collection]
                       if (s, "uniform_mean") in by_key and (s, "central_only") in by_key]
        result[method] = {"mean": mean(differences), "positive": sum(d > 0 for d in differences),
                          "n": len(differences)}
    return result


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True,
                        help="the code/msi/results folder (tests pass a temporary root)")
    parser.add_argument("--composite-root", type=Path, required=True,
                        help="composite root holding the production seed-1 fair scoring")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main():
    args = parse_arguments()
    if args.output.exists():
        print(f"Output already exists: {args.output}", file=sys.stderr)
        raise SystemExit(3)
    results = args.results_root
    paths = (results / "experiments/label_free_k_20261104",
             results / "diagnostics/fair_scoring_baselines/label_free_k_20261104/bin_level_only",
             args.composite_root)
    bic_roots = [results / "diagnostics" / name for name in
                 ("gate_d_bic", "gate_d_bic_rcc", "gate_d_bic_rcc_ig_steps_20261030")]
    try:
        records = []
        for collection, sections in SECTIONS.items():
            for section in sections:
                for arm in ARMS:
                    record = section_record(paths, collection, section, arm)
                    record["bic_cross_check"] = bic_cross_check(bic_roots, section, arm, record)
                    records.append(record)
    except Pending as error:
        print(f"Not finished: {error}", file=sys.stderr)
        raise SystemExit(1)

    failures = [{"section": r["section"], "arm": r["arm"], "gate": r["k_independent_gate"]}
                for r in records if r["status"] == "scored" and not r["k_independent_gate"]["passed"]]
    if failures:
        args.output.mkdir(parents=True)
        (args.output / "gate_failure.json").write_text(json.dumps(failures, indent=2),
                                                       encoding="utf-8")
        print(f"K-independent gate failed in {len(failures)} section-arms (stop and post)",
              file=sys.stderr)
        raise SystemExit(5)

    cells = [cell_summary(records, collection, arm) for collection in SECTIONS for arm in ARMS]
    all_hold = all(cell["label"] == "holds" for cell in cells)
    boundary = all(r["k_at_boundary"] for r in records)
    decisions = {
        "analysis": "label-free K (protocol 18 Section 6.10; decision log D56)",
        "seed": 1,
        "scale": "bin level, all classes, mSCF1 at K_bin",
        "label_free_k_wording": BOUNDARY_WORDING if boundary else None,
        "cells": cells,
        "overall": ("The IG < correlation result does not depend on the class-informed K."
                    if all_hold else
                    "Not all cells hold: " + "; ".join(
                        f"{c['collection']} {c['arm']}: {c['label']} ({c['correlation_beats_ig']}/8)"
                        for c in cells if c["label"] != "holds")),
        "arm_difference_descriptive": {c: arm_difference(records, c) for c in SECTIONS},
        "rcc_legacy_msipl": RCC_LEGACY,
        "sections": records,
    }
    args.output.mkdir(parents=True)
    (args.output / "decisions.json").write_text(json.dumps(decisions, indent=2),
                                                encoding="utf-8")
    columns = ["collection", "section", "arm", "status", "steps", "label_free_k",
               "production_k", "K_bin", "ig", "correlation", "correlation_minus_ig",
               "production_ig", "production_correlation", "mean_intensity", "variance",
               "morans_i", "legacy_msipl", "ari", "nmi"]
    with open(args.output / "per_section.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for r in records:
            label_free = r.get("label_free", {})
            writer.writerow({
                "collection": r["collection"], "section": r["section"], "arm": r["arm"],
                "status": r["status"], "steps": r.get("steps"),
                "label_free_k": r["label_free_k"], "production_k": r["production_k"],
                "K_bin": r.get("K_bin"), "ig": label_free.get(IG),
                "correlation": label_free.get(CORRELATION),
                "correlation_minus_ig": r.get("correlation_minus_ig"),
                "production_ig": r["production"][IG],
                "production_correlation": r["production"][CORRELATION],
                "mean_intensity": label_free.get("mean_intensity"),
                "variance": label_free.get("variance"), "morans_i": label_free.get("morans_i"),
                "legacy_msipl": (label_free.get("legacy_msipl") if r["collection"] != "RCC"
                                 else RCC_LEGACY),
                "ari": r.get("ari"), "nmi": r.get("nmi")})
    for cell in cells:
        print(f"{cell['collection']} {cell['arm']}: {cell['label']} "
              f"({cell['correlation_beats_ig']}/8; not done {cell['not_done']})")


if __name__ == "__main__":
    main()
