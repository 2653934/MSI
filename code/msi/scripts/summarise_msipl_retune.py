#!/usr/bin/env python3
"""Summary of the msiPL Beta re-tune (protocol 18 Section 6.8; supervisor chat
2026-10-30 12:58 item 2 and 17:33 ruling). Local, saved files only.

1. "IG beats legacy, robust to scoring" on GBM and CAC, per collection x arm (seed 1):
   - clause 1 (bin level at K_bin, >= 7/8 sections) and clause 2 (K_bin collapse
     diagnostic, same direction) are read from the saved partition decision table;
   - clause 3 (Section 6.8 answer 3): IG mSCF1 > legacy mSCF1 in >= 7/8 sections at
     every m in {0.5, 0.75, 1, 1.5, 2}, both at the re-tuned list's unique-bin count
     n_m. Capped (msipl_cap) points are included and flagged.
   The rule is reported as met only if all three clauses are met.
2. RCC, descriptive and outside Holm (answer 4): per run and arm, legacy msiPL and
   every ranking at the m = 1 list's unique-bin count n, and the median n against K_bin.
Refuses a missing or incomplete section, mixed scorer code, and an existing output.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = {
    "GBM": ("GBM108_positive", "GBM108_negative", "GBM12_1", "GBM12_2", "GBM22_1", "GBM22_2",
            "GBM39_1", "GBM39_2"),
    "CAC": ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL", "400TopL",
            "520TopL"),
    "RCC": ("RCC_MH0204_33", "RCC_UH0505_12", "RCC_UH0710_33", "RCC_UH9610_15",
            "RCC_UH9812_03", "RCC_UH9905_18", "RCC_UH9911_05", "RCC_UH9912_01"),
}
ARMS = ("central_only", "uniform_mean")
MULTIPLIERS = ("m0.5", "m0.75", "m1.0", "m1.5", "m2.0")
CLAUSE_MIN_SECTIONS = 7
RCC_METHODS = ("integrated_gradients", "posterior_abs_pcc_balanced", "mean_intensity",
               "variance", "morans_i", "oracle")
PARTITION_DECISIONS = Path("results/diagnostics/fair_scoring_baselines/with_approved_partitions/"
                           "summary_66238/decisions.json")
SCORE_ROOT = Path("results/diagnostics/fair_scoring_baselines/msipl_retune_20261030")


def load_scores(project, rcc_pending=()):
    """rcc_pending (opt-in): named RCC runs whose scoring has not run yet; they are
    reported as not done. Any other missing result still stops the summary."""
    records, code = {}, set()
    for collection, sections in SECTIONS.items():
        for section in sections:
            for arm in ARMS:
                path = project / SCORE_ROOT / f"{section}_seed1" / arm / "summary.json"
                if not path.is_file() and collection == "RCC" and section in rcc_pending:
                    continue
                if not path.is_file():
                    raise SystemExit(f"missing re-tune scoring: {path}")
                summary = json.loads(path.read_text(encoding="utf-8"))
                if summary.get("status") != "complete" or summary.get("dataset") != section:
                    raise SystemExit(f"{path}: not a complete re-tune scoring result")
                if sorted(summary["per_multiplier"]) != sorted(MULTIPLIERS):
                    raise SystemExit(f"{path}: multipliers {sorted(summary['per_multiplier'])}")
                code.add(json.dumps(summary["provenance"]["code"], sort_keys=True))
                records[(collection, section, arm)] = summary
    if len(code) != 1:
        raise SystemExit("re-tune scores come from different scorer code; refusing to mix them")
    return records


def clause_three(records, collection, arm):
    per_m, flags = {}, []
    for m in MULTIPLIERS:
        differences, capped = [], []
        for section in SECTIONS[collection]:
            record = records[(collection, section, arm)]["per_multiplier"][m]
            differences.append(float(record["ig_minus_legacy"]))
            if record["selection"]["status"] != "within_tolerance" and not (
                    m == "m1.0" and record["selection"]["status"] == "saved_list_reproduced"):
                capped.append(f"{section} ({record['selection']['status']}, "
                              f"n={record['n_unique_bins']})")
        positive = int(sum(d > 0 for d in differences))
        per_m[m] = {"sections": len(differences), "ig_above_legacy": positive,
                    "mean_difference": float(np.mean(differences)),
                    "per_section": differences, "flagged": capped}
        flags.extend(f"{m}: {item}" for item in capped)
    met = all(v["ig_above_legacy"] >= CLAUSE_MIN_SECTIONS for v in per_m.values())
    return {"met": met, "per_multiplier": per_m, "flagged_points": flags,
            "rule": "IG > legacy in >= 7/8 sections at every m, both at n_m (Section 6.8)"}


def clauses_one_two(decisions, collection, arm):
    record = decisions[f"{collection}/{arm}"]
    bin_level = record["ig_minus_legacy_bin"]
    collapse = record["ig_minus_legacy_collapse_diagnostic_P1"]
    return {
        "clause_1_bin_level": {"ig_above_legacy": bin_level["positive_sections"],
                               "sections": bin_level["sections"],
                               "mean_difference": bin_level["mean_difference"],
                               "met": bin_level["positive_sections"] >= CLAUSE_MIN_SECTIONS},
        "clause_2_collapse_diagnostic": {"ig_above_legacy": collapse["positive_sections"],
                                         "sections": collapse["sections"],
                                         "mean_difference": collapse["mean_difference"],
                                         "met": collapse["positive_sections"] >= CLAUSE_MIN_SECTIONS},
    }


def rcc_rows(records):
    rows = []
    for section in SECTIONS["RCC"]:
        for arm in ARMS:
            if ("RCC", section, arm) not in records:
                rows.append({"section": section, "arm": arm, "K_bin": None, "n": None,
                             "status": "not done (scoring pending)", "beta": None,
                             "legacy_msipl": None, **{name: None for name in RCC_METHODS}})
                continue
            summary = records[("RCC", section, arm)]
            m1 = summary["per_multiplier"]["m1.0"]
            row = {"section": section, "arm": arm, "K_bin": summary["K_bin"],
                   "n": m1["n_unique_bins"], "status": m1["selection"]["status"],
                   "beta": m1["selection"]["beta"], "legacy_msipl": m1["legacy_msipl"]}
            row.update({name: m1["rankings"][name] for name in RCC_METHODS})
            rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--rcc-pending", nargs="*", default=[],
                        help="opt-in: RCC runs whose scoring has not run yet (not done)")
    args = parser.parse_args()
    unknown = sorted(set(args.rcc_pending) - set(SECTIONS["RCC"]))
    if unknown:
        parser.error(f"not RCC runs: {unknown}")
    if args.output.exists():
        print(f"Output exists: {args.output} (never overwritten)", file=sys.stderr)
        return 3
    records = load_scores(args.project_root, tuple(args.rcc_pending))
    decisions = json.loads((args.project_root / PARTITION_DECISIONS).read_text(encoding="utf-8"))
    rule = {}
    for collection in ("GBM", "CAC"):
        for arm in ARMS:
            clauses = clauses_one_two(decisions, collection, arm)
            clauses["clause_3_budget_stability"] = clause_three(records, collection, arm)
            clauses["ig_beats_legacy_robust_to_scoring"] = all(
                c["met"] for c in clauses.values())
            rule[f"{collection}/{arm}"] = clauses
    rcc = rcc_rows(records)
    done = [row for row in rcc if row["arm"] == "central_only" and row["n"] is not None]
    counts = [row["n"] for row in done]
    k_bins = [row["K_bin"] for row in done]
    result = {
        "ig_beats_legacy": rule,
        "rcc_count_matched": {
            "label": "descriptive, outside Holm (Section 6.8 answer 4)",
            "runs_scored": len(done), "runs_pending": sorted(args.rcc_pending),
            "complete": not args.rcc_pending,
            "median_n": float(np.median(counts)), "median_K_bin": float(np.median(k_bins)),
            "runs_capped": sum(1 for row in rcc if row["arm"] == "central_only"
                               and row["status"] == "msipl_cap"),
            "rows": rcc},
    }
    args.output.mkdir(parents=True)
    (args.output / "decisions.json").write_text(json.dumps(result, indent=2) + "\n",
                                                encoding="utf-8")
    with (args.output / "rcc_count_matched.csv").open("w", newline="", encoding="utf-8") as h:
        writer = csv.DictWriter(h, fieldnames=list(rcc[0]))
        writer.writeheader()
        writer.writerows(rcc)
    for key, value in rule.items():
        print(f"{key}: clause 3 {'met' if value['clause_3_budget_stability']['met'] else 'not met'};"
              f" robust to scoring: {value['ig_beats_legacy_robust_to_scoring']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
