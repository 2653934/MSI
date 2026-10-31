#!/usr/bin/env python3
"""Three-seed main table and the seed-averaged F2 addendum (supervisor chat
2026-10-30 20:16, request 1). Local only, on saved and committed results.

1. Per collection x arm, bin level at K_bin: the collection mean over sections for
   each training seed (1-3), then the mean +- SD (ddof = 1) of those three seed-level
   collection means, for IG and posterior-|PCC| (balanced). Source: the Test R section
   table regenerated with the IG-steps composite (decisions_20261030_ig_steps_local),
   so every arm is complete.
2. Seed-independent rankings (mean intensity, variance, Moran's I, oracle, random mean,
   legacy msiPL on GBM/CAC), once per collection x arm, from the seed-1 fair-scoring
   section tables, and a check that the seed-2 and seed-3 fair-scoring summaries (the
   IG-steps composite root, which holds every Test R arm) give
   exactly the same values (1e-12) for every section and arm; otherwise the script stops.
3. F2 addendum (descriptive; the predeclared seed-1 F2 rows stay in the record): per
   GBM/CAC section, IG averaged over the three seeds minus legacy msiPL, then mean,
   Hodges-Lehmann [95% CI], matched-pairs rank-biserial r, exact Wilcoxon p, and Holm
   within these 4 rows (spatial_msipl.paired_statistics, as in Section 6.6).
Refuses an existing output.
"""

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from spatial_msipl import paired_statistics as ps  # noqa: E402

FSB = Path("results") / "diagnostics" / "fair_scoring_baselines"
TEST_R_TABLE = FSB / "test_r" / "decisions_20261030_ig_steps_local" / "section_table.csv"
CORE_TABLE = FSB / "bin_level_only" / "summary_66097" / "section_table.csv"
RCC_TABLE = FSB / "rcc" / "decisions_20261030_ig_steps_p1_local" / "section_table.csv"
# Test R seeds 2-3 with the IG-steps reruns: the composite root holds every arm.
TEST_R_FAIR = (Path("results") / "diagnostics" / "ig_steps_20261030" / "composite_root" / FSB
               / "test_r" / "bin_level_only")
COLLECTIONS = ("GBM", "CAC", "RCC")
ARMS = ("central_only", "uniform_mean")
SEEDS = (1, 2, 3)
SEED_FREE = ("morans_i", "mean_intensity", "variance", "legacy_msipl", "random_mean", "oracle")
TOLERANCE = 1e-12


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seed_rows(root):
    rows = {}
    for row in read_csv(root / TEST_R_TABLE):
        if row["scale"] != "bin":
            continue
        key = (row["collection"], row["arm"], int(row["seed"]))
        rows.setdefault(key, {})[row["section"]] = (float(row["ig_mSCF1"]),
                                                     float(row["posterior_mSCF1"]))
    return rows


def seed_free_rows(root):
    values = {}
    for path, collections in ((CORE_TABLE, ("GBM", "CAC")), (RCC_TABLE, ("RCC",))):
        for row in read_csv(root / path):
            if row["collection"] not in collections:
                continue
            record = {}
            for name in SEED_FREE:
                text = row.get(f"bin:{name}", "")
                record[name] = float(text) if text not in ("", None) else None
            values[(row["collection"], row["arm"], row["section"])] = record
    return values


def fair_value(summary, name):
    bin_level = summary["bin_level"]
    if name == "random_mean":
        return float(bin_level["random"]["1.0"]["mSCF1_mean"])
    if name not in bin_level:
        return None
    return float(bin_level[name]["1.0"]["mSCF1"])


def check_seed_independence(root, seed_free):
    """Seeds 2 and 3 must give the seed-1 values for every seed-free ranking."""
    checked, largest = 0, 0.0
    for (collection, arm, section), record in sorted(seed_free.items()):
        for seed in (2, 3):
            path = root / TEST_R_FAIR / f"{section}_seed{seed}" / arm / "summary.json"
            summary = json.loads(path.read_text(encoding="utf-8"))
            if summary.get("status") != "complete":
                raise ValueError(f"incomplete fair-scoring summary: {path}")
            for name, value in record.items():
                other = fair_value(summary, name)
                if value is None and other is None:
                    continue
                if value is None or other is None:
                    raise ValueError(f"{name} present in only one seed: {path}")
                difference = abs(value - other)
                largest = max(largest, difference)
                if difference > TOLERANCE:
                    raise ValueError(f"{name} varies by seed ({difference}): {path}")
                checked += 1
    return checked, largest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    root, output = args.project_root, args.output
    if output.exists():
        print(f"Output exists: {output} (never overwritten)", file=sys.stderr)
        return 3

    per_seed = seed_rows(root)
    seed_free = seed_free_rows(root)
    checked, largest = check_seed_independence(root, seed_free)

    table, f2_rows = [], []
    for collection in COLLECTIONS:
        for arm in ARMS:
            sections = sorted(per_seed[(collection, arm, 1)])
            for seed in SEEDS:
                if sorted(per_seed[(collection, arm, seed)]) != sections or len(sections) != 8:
                    raise ValueError(f"{collection}/{arm} seed {seed}: sections incomplete")
            row = {"collection": collection, "arm": arm, "sections": len(sections)}
            for index, name in enumerate(("ig", "posterior")):
                seed_means = [float(np.mean([per_seed[(collection, arm, s)][x][index]
                                             for x in sections])) for s in SEEDS]
                row[f"{name}_seed_means"] = ";".join(repr(v) for v in seed_means)
                row[f"{name}_mean"] = float(np.mean(seed_means))
                row[f"{name}_sd"] = float(np.std(seed_means, ddof=1))
            for name in SEED_FREE:
                values = [seed_free[(collection, arm, x)][name] for x in sections]
                row[name] = (None if any(v is None for v in values)
                             else float(np.mean(values)))
            table.append(row)
            if collection in ("GBM", "CAC"):
                differences = [float(np.mean([per_seed[(collection, arm, s)][x][0]
                                              for s in SEEDS]))
                               - seed_free[(collection, arm, x)]["legacy_msipl"]
                               for x in sections]
                f2_rows.append({"comparison": "IG seed mean 1-3 - legacy msiPL",
                                "collection": collection, "arm": arm, "scale": "bin",
                                **ps.paired_summary(differences), "holm_p": None,
                                "sections": ";".join(sections),
                                "differences": ";".join(repr(v) for v in differences)})
    for record, adjusted in zip(f2_rows, ps.holm([r["p_exact"] for r in f2_rows])):
        record["holm_p"] = adjusted

    output.mkdir(parents=True)
    for name, rows in (("main_table.csv", table), ("f2_seed_averaged.csv", f2_rows)):
        with open(output / name, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    summary = {
        "status": "complete",
        "request": "supervisor chat 2026-10-30 20:16, request 1 (three-seed main table "
                   "and F2 addendum, descriptive presentation change)",
        "definition": "mean +- SD (ddof = 1) across 3 training seeds of the seed-level "
                      "collection means; bin level at K_bin, all classes",
        "inputs": {str(p): sha256(root / p) for p in (TEST_R_TABLE, CORE_TABLE, RCC_TABLE)},
        "seed_independence": {"values_checked": checked, "max_abs_difference": largest,
                              "tolerance": TOLERANCE,
                              "rankings": list(SEED_FREE),
                              "result": "identical across seeds 1-3 within tolerance"},
        "rcc_legacy_msipl": "not in the fair evaluator (legacy msiPL not run on RCC); see "
                            "the Section 6.8 count-matched re-tune",
        "f2_holm": "Holm within these 4 rows; outside the predeclared F2 family",
        "main_table": table,
        "f2_seed_averaged": f2_rows,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n",
                                         encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
