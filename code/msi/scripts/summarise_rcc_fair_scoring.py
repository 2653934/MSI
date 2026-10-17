#!/usr/bin/env python3
"""RCC decision table (protocol 18 Section 6.1, item D step 2).

Applies the Section 7 IG-versus-posterior rule per arm over the 8 RCC runs, at
bin level only. P1, when the RCC partition approval exists, is tabulated as a
budget sensitivity and never enters the verdict (protocol 18 Section 6.1
amendment of 17 October; supervisor chat 2026-10-17 07:16). With
--sensitivity it tabulates the cancer/normal-only analysis, which never gets a
verdict. Refuses mixed provenance, rows from other collections, and a primary
root that contains class-subset results (or the reverse). No legacy rule: legacy
msiPL is not run on RCC.
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from summarise_fair_scoring_baselines import PRACTICAL, campaign_provenance, paired

RCC_SECTIONS = ("RCC_MH0204_33", "RCC_UH0505_12", "RCC_UH0710_33", "RCC_UH9610_15",
                "RCC_UH9812_03", "RCC_UH9905_18", "RCC_UH9911_05", "RCC_UH9912_01")
# CardinalWorkflows 1.44.0, vignettes/MSI-classification.Rmd: "8 matched pairs of
# human kidney tissue" and "each matched pair of tissues belonging to the same
# subject are on the same slide (i.e., the same run)". One subject per run.
RCC_PATIENT = {section: section.replace("RCC_", "") for section in RCC_SECTIONS}
PATIENT_SOURCE = ("CardinalWorkflows 1.44.0 MSI-classification vignette: each matched "
                  "pair from one subject is on its own slide (run); 8 runs, 8 subjects")
# Wording fixed by the supervisor, chat 2026-10-16 18:34 (documentary notes).
NA_CAVEAT = ("unannotated class, 45-78% of pixels; the dataset's own Cardinal workflow "
             "treats these pixels as background (rcc_nobg), but this was not "
             "independently verified")
HETEROGENEITY_LIMITATION = ("per the dataset documentation, UH0505_12 and UH9905_18 "
                            "contain heterogeneous tumour with large normal-looking areas "
                            "(descriptive; no exclusion, no separate analysis)")
SENSITIVITY_CAPTION = ("sensitivity, cancer/normal classes only: the reference sets, mSCF1, "
                       "F1 ceilings, P1 reference groups and the supervised oracle all use "
                       "the cancer and normal PCCs only; rankings and K_bin as the primary")
K_DISCLOSURE = ("GMM K = 3 equals the number of label classes: label-free in training "
                "and ranking, class-informed in its component count")
SENSITIVITY_LABEL = "sensitivity, cancer/normal classes only"
SENSITIVITY_CLASSES = [0, 1]
LEGACY_NOTE = "legacy msiPL not run on RCC (requires count tuning)"
# Supervisor chat 2026-10-17 07:03/07:16 (P1; supersedes 19:27) and 2026-10-16 19:47 (budget).
P1_NOTE = ("P1 on RCC is singleton groups, so its peak-level score is the bin-level score "
           "at the K_peak budget (~|R@0.4|); it is a budget sensitivity, not an independent "
           "partition check; it does not enter the verdict")
BUDGET_RULE = ("K_bin = released S3PL target num_GT_peaks (~|R@0.5|, the paper's RCC "
               "threshold), the GBM/CAC convention")
OTHER_BUDGETS = "GBM K_bin 584-1,028 and CAC K_bin 133-315 bins"
DESCRIPTIVE_METHODS = ("integrated_gradients", "posterior_abs_pcc_balanced", "first_layer_l2",
                       "mean_intensity", "variance", "morans_i", "oracle")


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path,
                        help="folder containing RCC_<run>_seed1/<arm>/summary.json")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sensitivity", action="store_true",
                        help="the cancer/normal-only analysis: tabulated, no verdict")
    return parser.parse_args()


def verdict(bin_level):
    """The Section 7 rule on the bin-level paired record only (P1 never enters)."""
    if bin_level["sections"] != len(RCC_SECTIONS):
        return f"incomplete; no verdict ({bin_level['sections']}/{len(RCC_SECTIONS)} runs)"
    if bin_level["mean_difference"] >= PRACTICAL and bin_level["positive_sections"] >= 6:
        return "IG adds value beyond its segmentation target"
    if abs(bin_level["mean_difference"]) < PRACTICAL:
        return "IG equivalent to segment-then-correlate"
    return "mixed / not resolved by the predeclared rule"


def main():
    args = parse_arguments()
    rows = []
    budget_rows = []
    # Same section_table.csv columns as the GBM/CAC tables (supervisor chat 2026-10-16 20:41).
    collection = "RCC_cancer_normal" if args.sensitivity else "RCC"
    keys = set()
    for path in sorted(args.root.glob("*_seed1/*/summary.json")):
        summary = json.loads(path.read_text(encoding="utf-8"))
        if summary.get("status") != "complete" or "provenance" not in summary:
            raise SystemExit(f"{path}: not a complete fair-scoring result")
        section, arm = path.parent.parent.name.replace("_seed1", ""), path.parent.name
        if section not in RCC_SECTIONS:
            raise SystemExit(f"{path}: {section} is not an RCC run")
        prov = summary["provenance"]
        subset = prov["parameters"].get("class_subset")
        if args.sensitivity and subset != SENSITIVITY_CLASSES:
            raise SystemExit(f"{path}: expected class subset {SENSITIVITY_CLASSES}, "
                             f"found {subset}")
        if not args.sensitivity and subset is not None:
            raise SystemExit(f"{path}: class-subset result in the primary table")
        if summary.get("legacy_msipl") != LEGACY_NOTE:
            raise SystemExit(f"{path}: not a --no-legacy RCC result")
        keys.add(json.dumps({
            "evaluation_version": prov["evaluation_version"],
            "protocol": prov["protocol"],
            "parameters": prov["parameters"],
            "approval": (prov["partition_approval"] or {}).get("sha256"),
            "code": prov["code"],
        }, sort_keys=True))
        row = {"collection": collection, "section": section, "arm": arm,
               "patient": RCC_PATIENT[section], "K_bin": summary["K_bin"]}
        for name, record in summary["bin_level"].items():
            if "1.0" in record and "mSCF1" in record["1.0"]:
                row[f"bin:{name}"] = record["1.0"]["mSCF1"]
        row["bin:random_mean"] = summary["bin_level"]["random"]["1.0"]["mSCF1_mean"]
        multipliers = sorted(summary["bin_level"]["integrated_gradients"], key=float)
        row["ig_above_posterior_all_budgets"] = all(
            summary["bin_level"]["integrated_gradients"][m]["mSCF1"]
            > summary["bin_level"]["posterior_abs_pcc_balanced"][m]["mSCF1"]
            for m in multipliers)
        for name, record in summary["bin_level"].items():
            for multiplier, value in record.items():
                score = value.get("mSCF1", value.get("mSCF1_mean"))
                if score is None:
                    continue
                budget_rows.append({
                    "collection": collection, "section": section, "arm": arm,
                    "method": name, "multiplier": multiplier,
                    "budget": summary["budgets"][multiplier], "mSCF1": score})
        for partition, record in summary.get("peak_level", {}).items():
            for name, method in record["methods"].items():
                matched = method.get("matched_K_peak")
                if isinstance(matched, dict) and "mSCF1" in matched:
                    row[f"{partition}:{name}"] = matched["mSCF1"]
        rows.append(row)
    if not rows:
        raise SystemExit(f"no RCC summaries under {args.root}")

    campaign = campaign_provenance({"RCC": keys})
    decisions = {}
    for arm in sorted({r["arm"] for r in rows}):
        subset = sorted((r for r in rows if r["arm"] == arm), key=lambda r: r["section"])
        record = {
            "sections": [r["section"] for r in subset],
            "ig_minus_posterior_bin": paired(
                [r["bin:integrated_gradients"] for r in subset],
                [r["bin:posterior_abs_pcc_balanced"] for r in subset]),
            "mean_mSCF1_bin": {name: float(np.mean([r[f"bin:{name}"] for r in subset]))
                               for name in DESCRIPTIVE_METHODS + ("random_mean",)},
            "patient_ig_minus_posterior_bin": {
                r["patient"]: r["bin:integrated_gradients"] - r["bin:posterior_abs_pcc_balanced"]
                for r in subset},
        }
        partitions = sorted({k.split(":")[0] for r in subset for k in r
                             if k.startswith("P") and ":" in k})
        for partition in partitions:
            if all(f"{partition}:integrated_gradients" in r for r in subset):
                record[f"ig_minus_posterior_{partition}_budget_sensitivity"] = paired(
                    [r[f"{partition}:integrated_gradients"] for r in subset],
                    [r[f"{partition}:posterior_abs_pcc_balanced"] for r in subset])
        if args.sensitivity:
            record["label"] = SENSITIVITY_LABEL
            record["caption"] = SENSITIVITY_CAPTION
            record["ig_vs_posterior_verdict"] = None
        else:
            record["ig_vs_posterior_verdict"] = verdict(record["ig_minus_posterior_bin"])
            record["verdict_scale"] = "bin level only"
        record["peak_level_partitions_used"] = partitions
        record["disclosures"] = [NA_CAVEAT, K_DISCLOSURE, LEGACY_NOTE]
        record["limitations"] = [HETEROGENEITY_LIMITATION]
        budgets = [r["K_bin"] for r in subset]
        record["budget_note"] = (f"{BUDGET_RULE}: {min(budgets):,}-{max(budgets):,} bins per "
                                 f"run; {OTHER_BUDGETS}")
        if partitions:
            record["p1_note"] = P1_NOTE
        decisions[f"RCC/{arm}"] = record
    decisions["_patients"] = {"mapping": RCC_PATIENT, "source": PATIENT_SOURCE}
    decisions["_campaign_provenance"] = campaign

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "decisions.json").write_text(json.dumps(decisions, indent=2) + "\n",
                                                encoding="utf-8")
    fields = sorted({k for r in rows for k in r})
    with open(args.output / "section_table.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    budget_rows.sort(key=lambda r: (r["section"], r["arm"], r["method"], float(r["multiplier"])))
    with open(args.output / "budget_sensitivity.csv", "w", newline="",
              encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["collection", "section", "arm", "method",
                                                    "multiplier", "budget", "mSCF1"])
        writer.writeheader()
        writer.writerows(budget_rows)
    for key, record in decisions.items():
        if not key.startswith("_"):
            print(key, record.get("label") or record["ig_vs_posterior_verdict"])


if __name__ == "__main__":
    main()
