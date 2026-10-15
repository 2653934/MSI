#!/usr/bin/env python3
"""Decision table for the 15 October round: extra arms beside the existing two.

Reads per-section fair-scoring summaries for the existing arms (central_only,
uniform_mean; runs 66053/66114+66179) and the extra arms written by
run_fair_scoring_extra_arm.sh (attention; G1-G3 centre-masked arms). Every
summary must come from the same evaluator code, parameters and approval within
its scope, or the table is refused. Rules (supervisor chat 2026-10-15 13:00
item A and 10:00 item G; protocol 18 Section 6.1), never chosen from outcomes:

* paired arm comparisons (A: attention vs uniform_mean; G2: G1 vs attention,
  G1 vs G2), per collection, IG mSCF1 at production K_bin at bin level AND
  under P1: "improves" if mean >= +0.02 and positive in >= 6/8 at both scales;
  "equivalent" if |mean| < 0.02 at both; otherwise "mixed";
* each extra arm's IG vs its own posterior-|PCC| under Section 7 (Section 7.1
  wording applies to the fall-through label);
* G3: G1 minus G3 >= 0.02 on both 160TopL and GBM22_2, bin level, descriptive;
* G mechanism: G1 median normalised attention entropy < 0.95 on both
  exploratory sections;
* E (13:00 item E; supervisor entry 15 October 19:37): a larger uniform window
  "helps" if its IG mSCF1 at K_bin beats real 3x3 (uniform_mean) by >= 0.02 in
  mean and is positive in >= 6/8 sections of a collection, at bin level AND
  under P1; "equivalent" if |mean| < 0.02 at both scales; otherwise "mixed".
  The verdict uses all 8 sections; the 7 confirmation sections and the window
  campaign's development section are also reported separately at both scales.
  p7 and p9 get the verdict; p5 is reported descriptively.
No collection with fewer than 8 sections gets a verdict.
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from summarise_fair_scoring_baselines import GBM_PATIENT, PRACTICAL, paired

ROOT = Path(__file__).resolve().parents[1]
FAIR = ROOT / "results" / "diagnostics" / "fair_scoring_baselines"
CENTREMASK = ROOT / "results" / "experiments" / "spatial_centremask_p50"
SCOPES = {
    "bin_level_only": (FAIR / "bin_level_only", FAIR / "extra_arms" / "bin_level_only"),
    "with_approved_partitions": (FAIR / "with_approved_partitions",
                                 FAIR / "extra_arms" / "with_approved_partitions"),
}
EXISTING_ARMS = ("central_only", "uniform_mean")
EXTRA_ARMS = ("attention", "attention_centremask_p50", "uniform_centremask_p50",
              "shuffled_attention_centremask_p50", "uniform_p5", "uniform_p7", "uniform_p9")
POSTERIOR_ARMS = ("attention", "attention_centremask_p50", "uniform_centremask_p50",
                  "uniform_p5", "uniform_p7", "uniform_p9")
E_ARMS = ("uniform_p7", "uniform_p9")
WINDOW_DEVELOPMENT = {"40TopL", "GBM108_positive"}
COMPARISONS = (
    ("A: attention vs uniform_mean", "attention", "uniform_mean"),
    ("G rule 2: G1 vs standard attention", "attention_centremask_p50", "attention"),
    ("G rule 2: G1 vs G2", "attention_centremask_p50", "uniform_centremask_p50"),
)
EXPLORATORY = ("160TopL", "GBM22_2")
ENTROPY_THRESHOLD = 0.95


def collection_of(section):
    return "GBM" if section.startswith("GBM") else "CAC"


def load_scope(scope):
    """{(section, arm): summary} plus the provenance key of each, for one scope."""
    results = {}
    keys = {}
    for root in SCOPES[scope]:
        for path in sorted(root.glob("*_seed1/*/summary.json")):
            arm = path.parent.name
            if arm not in EXISTING_ARMS + EXTRA_ARMS:
                continue
            if root == SCOPES[scope][0] and arm not in EXISTING_ARMS:
                continue
            summary = json.loads(path.read_text(encoding="utf-8"))
            if summary.get("status") != "complete" or "provenance" not in summary:
                raise SystemExit(f"{path}: not a complete result")
            section = path.parent.parent.name.replace("_seed1", "")
            prov = summary["provenance"]
            parameters = dict(prov["parameters"])
            partitions = parameters.pop("approved_partition_parameters", {})
            keys.setdefault(json.dumps({
                "evaluation_version": prov["evaluation_version"], "protocol": prov["protocol"],
                "parameters": parameters,
                "approval": (prov["partition_approval"] or {}).get("sha256"),
                "code": prov["code"]}, sort_keys=True), set()).add(f"{section}/{arm}")
            keys.setdefault(f"partitions:{collection_of(section)}:" + json.dumps(
                partitions, sort_keys=True), set()).add(f"{section}/{arm}")
            results[(section, arm)] = summary
    shared = [k for k in keys if not k.startswith("partitions:")]
    if len(shared) > 1:
        raise SystemExit(f"{scope}: results come from different evaluator code, parameters or "
                         "approvals; refusing to mix them in one table")
    for collection in ("GBM", "CAC"):
        if len([k for k in keys if k.startswith(f"partitions:{collection}:")]) > 1:
            raise SystemExit(f"{scope}: approved partitions differ within {collection}")
    return results, (json.loads(shared[0]) if shared else None)


def ig_bin(summary):
    return summary["bin_level"]["integrated_gradients"]["1.0"]["mSCF1"]


def ig_partition(summary, partition):
    return summary["peak_level"][partition]["methods"]["integrated_gradients"]["matched_K_peak"]["mSCF1"]


def method_partition(summary, partition, name):
    return summary["peak_level"][partition]["methods"][name]["matched_K_peak"]["mSCF1"]


def sections_of(results, arm, collection):
    return sorted(s for (s, a) in results if a == arm and collection_of(s) == collection)


def arm_comparison(bins, parts, arm_a, arm_b, collection):
    common = [s for s in sections_of(bins, arm_a, collection)
              if (s, arm_b) in bins and (s, arm_a) in parts and (s, arm_b) in parts]
    if len(common) != 8:
        return {"sections": common, "verdict": f"incomplete collection ({len(common)}/8 "
                                               "sections); no verdict"}
    scales = {
        "bin_level": paired([ig_bin(bins[(s, arm_a)]) for s in common],
                            [ig_bin(bins[(s, arm_b)]) for s in common]),
        "P1": paired([ig_partition(parts[(s, arm_a)], "P1") for s in common],
                     [ig_partition(parts[(s, arm_b)], "P1") for s in common]),
    }
    if all(v["mean_difference"] >= PRACTICAL and v["positive_sections"] >= 6
           for v in scales.values()):
        verdict = f"{arm_a} improves on {arm_b}"
    elif all(abs(v["mean_difference"]) < PRACTICAL for v in scales.values()):
        verdict = f"{arm_a} equivalent to {arm_b}"
    else:
        verdict = "mixed"
    return {"sections": common, **scales, "verdict": verdict}


def ig_vs_posterior(bins, parts, arm, collection):
    sections = [s for s in sections_of(bins, arm, collection) if (s, arm) in parts]
    if len(sections) != 8:
        return {"sections": sections,
                "ig_vs_posterior_verdict": f"incomplete collection ({len(sections)}/8 "
                                           "sections); no verdict"}
    record = {"sections": sections, "ig_minus_posterior_bin": paired(
        [ig_bin(bins[(s, arm)]) for s in sections],
        [bins[(s, arm)]["bin_level"]["posterior_abs_pcc_balanced"]["1.0"]["mSCF1"]
         for s in sections])}
    partitions = sorted(set.intersection(*(set(parts[(s, arm)]["peak_level"]) for s in sections)))
    for partition in partitions:
        record[f"ig_minus_posterior_{partition}"] = paired(
            [ig_partition(parts[(s, arm)], partition) for s in sections],
            [method_partition(parts[(s, arm)], partition, "posterior_abs_pcc_balanced")
             for s in sections])
    if collection == "GBM":
        record["patient_ig_minus_posterior_bin"] = {
            p: float(np.mean([ig_bin(bins[(s, arm)])
                              - bins[(s, arm)]["bin_level"]["posterior_abs_pcc_balanced"]["1.0"]["mSCF1"]
                              for s in sections if GBM_PATIENT[s] == p]))
            for p in sorted({GBM_PATIENT[s] for s in sections})}
    scales = [v for k, v in record.items() if k.startswith("ig_minus_posterior_")]
    if all(s["mean_difference"] >= PRACTICAL and s["positive_sections"] >= 6 for s in scales):
        verdict = "IG adds value beyond its segmentation target"
    elif all(abs(s["mean_difference"]) < PRACTICAL for s in scales):
        verdict = "IG equivalent to segment-then-correlate"
    else:
        verdict = ("mixed / not resolved by the predeclared rule (a fall-through label; "
                   "report with the Section 7.1 wording)")
    record["partitions_used"] = partitions
    record["ig_vs_posterior_verdict"] = verdict
    return record


def g3_rule(bins):
    rows = {}
    for section in EXPLORATORY:
        real, shuffled = ((section, "attention_centremask_p50"),
                          (section, "shuffled_attention_centremask_p50"))
        if real in bins and shuffled in bins:
            rows[section] = ig_bin(bins[real]) - ig_bin(bins[shuffled])
    if len(rows) != 2:
        return {"differences": rows, "result": "incomplete; not assessed"}
    met = all(d >= PRACTICAL for d in rows.values())
    return {"differences": rows, "result": (
        "real-context masked attention beats shuffled-context masked attention by >= 0.02 "
        "on both exploratory sections" if met else
        "real-context masked attention does not beat shuffled by >= 0.02 on both sections"),
        "label": "descriptive, two development sections"}


def window_rule(bins, parts, arm, collection):
    common = [s for s in sections_of(bins, arm, collection)
              if (s, "uniform_mean") in bins and (s, arm) in parts and (s, "uniform_mean") in parts]
    if len(common) != 8:
        return {"sections": common,
                "verdict": f"incomplete collection ({len(common)}/8 sections); no verdict"}

    def compare(sections):
        return {
            "bin_level": paired([ig_bin(bins[(s, arm)]) for s in sections],
                                [ig_bin(bins[(s, "uniform_mean")]) for s in sections]),
            "P1": paired([ig_partition(parts[(s, arm)], "P1") for s in sections],
                         [ig_partition(parts[(s, "uniform_mean")], "P1") for s in sections]),
        }

    all_sections = compare(common)
    record = {"sections": common, "all_8": all_sections,
              "confirmation": compare([s for s in common if s not in WINDOW_DEVELOPMENT]),
              "development": compare([s for s in common if s in WINDOW_DEVELOPMENT])}
    if arm in E_ARMS:
        if all(v["mean_difference"] >= PRACTICAL and v["positive_sections"] >= 6
               for v in all_sections.values()):
            record["verdict"] = f"{arm} helps over real 3x3"
        elif all(abs(v["mean_difference"]) < PRACTICAL for v in all_sections.values()):
            record["verdict"] = f"{arm} equivalent to real 3x3"
        else:
            record["verdict"] = "mixed (does not meet the 'helps' rule)"
    else:
        record["verdict"] = "descriptive only (existing arm)"
    return record


def mechanism_rule():
    medians = {}
    for section in EXPLORATORY:
        path = CENTREMASK / f"{section}_seed1" / "attention_centremask_p50" / "mechanism" / "attention_weights.json"
        if path.is_file():
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") == "valid":
                medians[section] = {
                    "masked": record["centremask_p50"]["normalized_entropy"]["median"],
                    "unmasked_seed1_same_centres":
                        record["unmasked_seed1_same_centres"]["normalized_entropy"]["median"]}
    if len(medians) != 2:
        return {"median_normalized_entropy": medians, "result": "incomplete; not assessed"}
    selective = all(v["masked"] < ENTROPY_THRESHOLD for v in medians.values())
    return {"median_normalized_entropy": medians, "threshold": ENTROPY_THRESHOLD,
            "result": "masking made attention selective" if selective
            else "attention stayed near-uniform"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    bins, bin_campaign = load_scope("bin_level_only")
    parts, part_campaign = load_scope("with_approved_partitions")
    decisions = {"comparisons": {}, "ig_vs_posterior": {}}
    for label, arm_a, arm_b in COMPARISONS:
        if any(a == arm_a for (_, a) in bins):
            decisions["comparisons"][label] = {
                c: arm_comparison(bins, parts, arm_a, arm_b, c) for c in ("GBM", "CAC")}
    for arm in POSTERIOR_ARMS:
        if any(a == arm for (_, a) in bins):
            decisions["ig_vs_posterior"][arm] = {
                c: ig_vs_posterior(bins, parts, arm, c) for c in ("GBM", "CAC")}
    decisions["e_windows_vs_real_3x3"] = {
        arm: {c: window_rule(bins, parts, arm, c) for c in ("GBM", "CAC")}
        for arm in ("uniform_p5",) + E_ARMS if any(a == arm for (_, a) in bins)}
    decisions["g3_spatial_specificity"] = g3_rule(bins)
    decisions["g_mechanism"] = mechanism_rule()
    decisions["_campaign_provenance"] = {"bin_level_only": bin_campaign,
                                         "with_approved_partitions": part_campaign}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "decisions.json").write_text(json.dumps(decisions, indent=2) + "\n",
                                                encoding="utf-8")
    rows = []
    for (section, arm), summary in sorted(bins.items()):
        row = {"section": section, "collection": collection_of(section), "arm": arm,
               "patient": GBM_PATIENT.get(section, section), "K_bin": summary["K_bin"],
               "bin:integrated_gradients": ig_bin(summary),
               "bin:posterior_abs_pcc_balanced":
                   summary["bin_level"]["posterior_abs_pcc_balanced"]["1.0"]["mSCF1"]}
        if (section, arm) in parts:
            for partition in sorted(parts[(section, arm)]["peak_level"]):
                row[f"{partition}:integrated_gradients"] = ig_partition(parts[(section, arm)], partition)
                row[f"{partition}:posterior_abs_pcc_balanced"] = method_partition(
                    parts[(section, arm)], partition, "posterior_abs_pcc_balanced")
        rows.append(row)
    fields = sorted({k for r in rows for k in r})
    with open(args.output / "section_table.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"decision table written: {args.output / 'decisions.json'}")


if __name__ == "__main__":
    main()
