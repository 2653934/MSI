#!/usr/bin/env python3
"""Collection-level decision table for the fair-scoring/baseline gate.

Applies the predeclared rules in protocol Section 7 to per-section summaries
written by evaluate_fair_scoring_baselines.py. It never chooses a partition,
method or threshold from the outcomes; it only reports them.
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

PRACTICAL = 0.02
GBM_PATIENT = {
    "GBM108_positive": "108", "GBM108_negative": "108", "GBM12_1": "12",
    "GBM12_2": "12", "GBM22_1": "22", "GBM22_2": "22", "GBM39_1": "39", "GBM39_2": "39",
}


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path,
                        help="folder containing <section>_seed1/<arm>/summary.json")
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def paired(values_a, values_b):
    differences = np.asarray(values_a) - np.asarray(values_b)
    return {
        "sections": int(len(differences)),
        "mean_difference": float(differences.mean()),
        "median_difference": float(np.median(differences)),
        "positive_sections": int(np.sum(differences > 0)),
        "per_section": differences.tolist(),
    }


def main():
    args = parse_arguments()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    campaign = set()
    for path in sorted(args.root.glob("*_seed1/*/summary.json")):
        summary = json.loads(path.read_text(encoding="utf-8"))
        if summary.get("status") != "complete" or "provenance" not in summary:
            raise SystemExit(f"{path}: not a complete version-2 result")
        prov = summary["provenance"]
        campaign.add(json.dumps({
            "evaluation_version": prov["evaluation_version"],
            "protocol": prov["protocol"],
            "parameters": prov["parameters"],
            "approval": (prov["partition_approval"] or {}).get("sha256"),
            "code": prov["code"],
        }, sort_keys=True))
        section, arm = path.parent.parent.name.replace("_seed1", ""), path.parent.name
        collection = "GBM" if section.startswith("GBM") else "CAC"
        bin_level = summary["bin_level"]
        row = {"collection": collection, "section": section, "arm": arm,
               "patient": GBM_PATIENT.get(section, section)}
        for name, record in bin_level.items():
            if "1.0" in record and "mSCF1" in record["1.0"]:
                row[f"bin:{name}"] = record["1.0"]["mSCF1"]
        row["bin:random_mean"] = bin_level["random"]["1.0"]["mSCF1_mean"]
        multipliers = sorted(bin_level["integrated_gradients"])
        row["ig_above_posterior_all_budgets"] = all(
            bin_level["integrated_gradients"][m]["mSCF1"]
            > bin_level["posterior_abs_pcc_balanced"][m]["mSCF1"] for m in multipliers)
        for partition, record in summary.get("peak_level", {}).items():
            for name, method in record["methods"].items():
                matched = method.get("matched_K_peak")
                if isinstance(matched, dict) and "mSCF1" in matched:
                    row[f"{partition}:{name}"] = matched["mSCF1"]
                row[f"{partition}:collapse:{name}"] = method["collapse_K_bin"]["mSCF1"] \
                    if "collapse_K_bin" in method else None
        rows.append(row)

    if len(campaign) != 1:
        raise SystemExit("section results come from different code, parameters or approvals; "
                         "refusing to mix them in one decision table")

    decisions = {}
    for collection in ("GBM", "CAC"):
        for arm in sorted({r["arm"] for r in rows}):
            subset = [r for r in rows if r["collection"] == collection and r["arm"] == arm]
            if not subset:
                continue
            key = f"{collection}/{arm}"
            record = {
                "ig_minus_posterior_bin": paired(
                    [r["bin:integrated_gradients"] for r in subset],
                    [r["bin:posterior_abs_pcc_balanced"] for r in subset]),
                "ig_minus_legacy_bin": paired(
                    [r["bin:integrated_gradients"] for r in subset],
                    [r["bin:legacy_msipl"] for r in subset]),
                "ig_above_posterior_all_budgets_sections": int(
                    sum(r["ig_above_posterior_all_budgets"] for r in subset)),
            }
            partitions = sorted({k.split(":")[0] for r in subset for k in r
                                 if k.startswith("P") and ":" in k})
            for partition in partitions:
                if all(f"{partition}:integrated_gradients" in r for r in subset):
                    record[f"ig_minus_posterior_{partition}"] = paired(
                        [r[f"{partition}:integrated_gradients"] for r in subset],
                        [r[f"{partition}:posterior_abs_pcc_balanced"] for r in subset])
                    record[f"ig_minus_legacy_collapse_diagnostic_{partition}"] = paired(
                        [r[f"{partition}:collapse:integrated_gradients"] for r in subset],
                        [r[f"{partition}:collapse:legacy_msipl"] for r in subset])
            if collection == "GBM":
                patients = sorted({r["patient"] for r in subset})
                record["patient_ig_minus_posterior_bin"] = {
                    p: float(np.mean([r["bin:integrated_gradients"]
                                      - r["bin:posterior_abs_pcc_balanced"]
                                      for r in subset if r["patient"] == p]))
                    for p in patients}

            scales = [record["ig_minus_posterior_bin"]] + [
                record[k] for k in record if k.startswith("ig_minus_posterior_P")]
            n = len(subset)
            if n != 8:
                verdict = f"incomplete collection ({n}/8 sections); no verdict"
            elif all(s["mean_difference"] >= PRACTICAL and s["positive_sections"] >= 6
                     for s in scales):
                verdict = "IG adds value beyond its segmentation target"
            elif all(abs(s["mean_difference"]) < PRACTICAL for s in scales):
                verdict = "IG equivalent to segment-then-correlate"
            else:
                verdict = "mixed / not resolved by the predeclared rule"
            record["ig_vs_posterior_verdict"] = verdict
            record["legacy_note"] = (
                "Legacy msiPL is not K_peak-matched (fixed list; Beta re-tune pending). "
                "IG-versus-legacy peak-level values are the K_bin collapse diagnostic only, "
                "not a matched peak-level comparison.")
            record["peak_level_partitions_used"] = partitions
            decisions[key] = record

    decisions["_campaign_provenance"] = json.loads(next(iter(campaign)))
    (args.output / "decisions.json").write_text(json.dumps(decisions, indent=2) + "\n",
                                                encoding="utf-8")
    fields = sorted({k for r in rows for k in r})
    with open(args.output / "section_table.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    for key, record in decisions.items():
        if not key.startswith("_"):
            print(key, record["ig_vs_posterior_verdict"])


if __name__ == "__main__":
    main()
