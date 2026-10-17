#!/usr/bin/env python3
"""Test S decision table (protocol 18 Section 6.2; supervisor chat 2026-10-17 08:04).

Reads <root>/<collection>/<section>_seed1/<arm>/summary.json written by
evaluate_spatial_segmentation_s.py and applies the predeclared rule per
collection x arm, S1 (sa_posterior_abs_pcc_balanced) against plain
posterior-|PCC|:
- "spatial segmentation helps": mean difference >= +0.02 and positive in >= 6/8
  sections, at bin level and P1 for GBM/CAC, at bin level for RCC;
- "equivalent": |mean| < 0.02 at every applicable scale;
- otherwise "mixed (does not meet the 'helps' rule)";
- fewer than 8 sections: "incomplete; no verdict (n/8 sections)".
S2 (fusion, S1 vs Moran's I, segmentation agreement) is tabulated, never decided.
Refuses mixed code or settings, non-production smoothing, a wrong scale set for
the collection, unknown sections and folder/dataset mismatches. Local files only.
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from summarise_fair_scoring_baselines import paired

PRACTICAL = 0.02
MIN_POSITIVE = 6
N_SECTIONS = 8
SIGMA = 0.75
SECTIONS = {
    "GBM": ("GBM108_negative", "GBM108_positive", "GBM12_1", "GBM12_2", "GBM22_1",
            "GBM22_2", "GBM39_1", "GBM39_2"),
    "CAC": ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL", "400TopL",
            "520TopL"),
    "RCC": ("RCC_MH0204_33", "RCC_UH0505_12", "RCC_UH0710_33", "RCC_UH9610_15",
            "RCC_UH9812_03", "RCC_UH9905_18", "RCC_UH9911_05", "RCC_UH9912_01"),
}
SCALES = {"GBM": ("bin", "P1"), "CAC": ("bin", "P1"), "RCC": ("bin",)}
ARMS = ("central_only", "uniform_mean")
PLAIN, SMOOTHED = "posterior_abs_pcc_balanced", "sa_posterior_abs_pcc_balanced"
MORANS, FUSION = "morans_i", "rank_fusion_posterior_morans_i"
HELPS = "spatial segmentation helps"
EQUIVALENT = "equivalent"
MIXED = "mixed (does not meet the 'helps' rule)"
NOTES = {
    "GBM": "8 sections from 4 patients; sections are not independent patients",
    # Wording from the supervisor chat, 2026-10-17 08:37.
    "CAC": ("CAC P1 is singleton groups (1,481 for 1,481 bins), so its peak-level score is "
            "the bin-level score at the K_peak budget; requiring both is a two-budget check, "
            "not an independent partition check"),
    "RCC": ("bin level only (protocol 18 Section 6.1 amendment, 17 October); unannotated "
            "class, 45-78% of pixels; the dataset's own Cardinal workflow treats these "
            "pixels as background (rcc_nobg), but this was not independently verified; "
            "GMM K = 3 is class-informed; uniform_mean UH0505_12 not done (IG completeness "
            "failed at 64 steps)"),
}


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path,
                        help="results/diagnostics/spatial_segmentation_S")
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def decide(by_scale, sections, expected=N_SECTIONS):
    """The 08:04 rule on the paired S1 - plain records of every applicable scale."""
    if sections != expected:
        return f"incomplete; no verdict ({sections}/{expected} sections)"
    if all(r["mean_difference"] >= PRACTICAL and r["positive_sections"] >= MIN_POSITIVE
           for r in by_scale.values()):
        return HELPS
    if all(abs(r["mean_difference"]) < PRACTICAL for r in by_scale.values()):
        return EQUIVALENT
    return MIXED


def load(root):
    records, keys = [], set()
    for path in sorted(root.glob("*/*_seed1/*/summary.json")):
        collection, section = path.parents[2].name, path.parents[1].name[:-len("_seed1")]
        arm = path.parent.name
        if collection not in SECTIONS or section not in SECTIONS[collection]:
            raise SystemExit(f"{path}: {section} is not a {collection} section")
        if arm not in ARMS:
            raise SystemExit(f"{path}: unknown arm {arm}")
        summary = json.loads(path.read_text(encoding="utf-8"))
        if summary.get("status") != "complete" or summary.get("dataset") != section:
            raise SystemExit(f"{path}: not a complete Test S result for {section}")
        parameters = summary["provenance"]["parameters"]
        if parameters.get("sigma") != SIGMA or parameters.get("adaptive") is not True:
            raise SystemExit(f"{path}: not the predeclared smoothing (sigma {SIGMA}, adaptive)")
        if tuple(parameters.get("scales", ())) != SCALES[collection]:
            raise SystemExit(f"{path}: scales {parameters.get('scales')} but {collection} "
                             f"needs {list(SCALES[collection])}")
        shared = {k: v for k, v in parameters.items() if k not in ("gmm_components", "scales")}
        keys.add(json.dumps({"version": summary["provenance"]["test_s_version"],
                             "parameters": shared, "code": summary["provenance"]["code"]},
                            sort_keys=True))
        records.append((collection, section, arm, summary))
    if not records:
        raise SystemExit(f"no Test S summaries under {root}")
    if len(keys) != 1:
        raise SystemExit("Test S results come from different code or settings; "
                         "refusing to mix them in one table")
    return records


def main():
    args = parse_arguments()
    records = load(args.root)
    rows = []
    for collection, section, arm, summary in records:
        row = {"collection": collection, "section": section, "arm": arm,
               "K_bin": summary["K_bin"],
               "smoothed_empty_components": summary["smoothed_gmm"]["empty_components"]}
        for scale, values in summary["mSCF1"].items():
            for name, value in values.items():
                row[f"{scale}:{name}"] = value
        segmentation = summary["S2"]["c_segmentation"]
        row["ari_smoothed_vs_production"] = segmentation["ari_smoothed_vs_production"]
        row["balanced_accuracy_production"] = segmentation["production_vs_expert"][
            "balanced_accuracy"]
        row["balanced_accuracy_smoothed"] = segmentation["smoothed_vs_expert"][
            "balanced_accuracy"]
        rows.append(row)

    decisions = {}
    for collection in SECTIONS:
        for arm in ARMS:
            subset = sorted((r for r in rows if r["collection"] == collection
                             and r["arm"] == arm),
                            key=lambda r: SECTIONS[collection].index(r["section"]))
            if not subset:
                continue
            record = {"sections": [r["section"] for r in subset],
                      "scales": list(SCALES[collection]), "S1_minus_plain": {},
                      "S2a_S1_minus_morans_i": {}, "S2b_fusion_minus_plain": {},
                      "mean_mSCF1": {}}
            for scale in SCALES[collection]:
                column = lambda name: [r[f"{scale}:{name}"] for r in subset]
                record["S1_minus_plain"][scale] = paired(column(SMOOTHED), column(PLAIN))
                record["S2a_S1_minus_morans_i"][scale] = paired(column(SMOOTHED),
                                                                column(MORANS))
                record["S2b_fusion_minus_plain"][scale] = paired(column(FUSION), column(PLAIN))
                record["mean_mSCF1"][scale] = {name: float(np.mean(column(name)))
                                               for name in (PLAIN, SMOOTHED, MORANS, FUSION)}
            record["verdict"] = decide(record["S1_minus_plain"], len(subset))
            accuracy = {name: [r[name] for r in subset if r[name] is not None]
                        for name in ("balanced_accuracy_production",
                                     "balanced_accuracy_smoothed")}
            record["S2c_segmentation"] = {
                "mean_ari_smoothed_vs_production": float(np.mean(
                    [r["ari_smoothed_vs_production"] for r in subset])),
                **{f"mean_{k}": (float(np.mean(v)) if v else None) for k, v in accuracy.items()},
                "balanced_accuracy_sections": {k: len(v) for k, v in accuracy.items()},
            }
            record["smoothed_runs_with_empty_components"] = sum(
                r["smoothed_empty_components"] > 0 for r in subset)
            record["note"] = NOTES[collection]
            record["S2_status"] = "descriptive; no verdict"
            decisions[f"{collection}/{arm}"] = record

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "decisions.json").write_text(json.dumps(decisions, indent=2) + "\n",
                                                encoding="utf-8")
    fields = sorted({k for r in rows for k in r})
    with open(args.output / "section_table.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    for key, record in decisions.items():
        bits = ", ".join(f"{s} {v['mean_difference']:+.3f} ({v['positive_sections']}/"
                         f"{v['sections']})" for s, v in record["S1_minus_plain"].items())
        print(f"{key}: {record['verdict']}; S1 - plain {bits}")


if __name__ == "__main__":
    main()
