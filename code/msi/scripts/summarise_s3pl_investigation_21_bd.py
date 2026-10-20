#!/usr/bin/env python3
"""Protocol 18 Section 6.7 (Investigation 21), Parts B and D, from saved S3PL runs.

Local only. Scores are S3PL's own in-job mSCF1 (``metrics.json``; recomputed unrounded as
the mean of ``mixed_f1``), the metric of the published 0.496 / 0.601, not the
fair-scoring evaluator (chat 2026-10-20 11:46, Q3).

Part B: released ``random_seed`` 1-10, all 8 sections of GBM and CAC.
- per section: mean, SD, min, max, and the percentile of the published value within our
  10 seeds;
- collection mean +- SD across the 10 seed-level collection means;
- B1 (and B3 for CAC): "inside our seed distribution" if the published collection mean is
  <= the maximum of our 10 seed-level collection means, else "outside";
- B2 (and B3 for CAC): per section, the exact expected maximum over k seeds (all
  k-subsets of the 10), averaged over sections, for k = 1..10; the smallest k at which it
  reaches the published mean. "consistent with per-section best-of-k selection (k = ...)"
  if k <= 10, else "not explained by seed selection alone".

Part D: GBM, 8 sections x seeds 1-3, paper TIC vs the released helper. Per-section seed
means, paired (TIC - released). Label on the TIC collection mean: "explains the gap" if
>= 0.446; "partly" if it rises by >= +0.05 but stays below 0.446; "does not explain"
otherwise. Section 6.6-style statistics beside the label. The label carries the
disclosure fixed in chat 11:46 (Q4).
"""

import argparse
import hashlib
import json
import math
import sys
from itertools import combinations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import summarise_s3pl_seed_investigation_21 as inv  # noqa: E402
from spatial_msipl import paired_statistics as ps  # noqa: E402

PROTOCOL = ("protocol 18 Section 6.7 (Investigation 21), Parts B and D, with the 11:54 addendum; "
            "supervisor chat 2026-10-20 10:53, 11:46 and 11:58")
DEFAULT_OUTPUT = Path("results") / "diagnostics" / "s3pl_seed_investigation_21"
# Published per-section S3PL mSCF1: IonMorphNet msianalyzer/external/s3pl/sota_comparison.py
# at 640406a, transcribed in investigation 19, Section 3. Means equal the paper's Table 3.
PUBLISHED = {
    "GBM": {"GBM12_1": 0.27, "GBM12_2": 0.55, "GBM22_1": 0.47, "GBM22_2": 0.61,
            "GBM39_1": 0.38, "GBM39_2": 0.56, "GBM108_positive": 0.47, "GBM108_negative": 0.66},
    "CAC": {"40TopL": 0.68, "160TopL": 0.53, "200TopL": 0.61, "240TopL": 0.67,
            "280TopL": 0.63, "360TopL": 0.64, "400TopL": 0.35, "520TopL": 0.70},
}
PUBLISHED_MEAN = {"GBM": 0.496, "CAC": 0.601}
B_SEEDS = tuple(range(1, 11))
D_SEEDS = (1, 2, 3)
D_EXPLAINS = 0.446
D_PARTLY_RISE = 0.05
D_DISCLOSURE = ("seed 1 existed before the predeclaration (0.289 vs 0.316) and was seen during the "
                "inventory; seeds 2-3 are blind")
NOTES = (
    "Scores are S3PL's own in-job mSCF1 (metrics.json), recomputed unrounded; not the "
    "fair-scoring evaluator. Published values are given to 2 decimals.",
    "Saved released runs are reused after gate 72136 (bit-identical to job 53121).",
    "The percentile of a published value is the share of our seeds strictly below it, with "
    "ties counted as one half.",
    "B2 uses the exact expectation of the maximum over a uniformly random k-subset of the 10 "
    "seeds, per section, then the mean over sections.",
    "Investigation 21 GPU jobs were not exclusive (bigbatch has no GPU gres); runtimes are "
    "descriptive.",
    "A run may hold fewer than num_GT_peaks peaks only if that equals its logged distinct-"
    "selection count (released code, test.py:167-184; chat 2026-10-20 20:39); such runs are "
    "kept, so the 8 x 10 design stays balanced, and are listed in short_peak_lists.",
)


native_counts = inv.native_counts


def scores(root, collection, seeds, locate, mode, normalization="reference_spatial_max"):
    """{section: [unrounded mSCF1 per seed]}, with every run validated; plus input files and
    the runs accepted with fewer than ``num_GT_peaks`` peaks (``inv.check_peak_count``)."""
    native, logged = native_counts(), inv.logged_selection_counts(root)
    table, files, short = {}, [], []
    for section in inv.SECTIONS[collection]:
        values = []
        for seed in seeds:
            record, _, used = inv.load_run(root, collection, section, seed, locate)
            inv.check_settings(record, mode, seed, normalization)
            note = inv.check_peak_count(record, native[section], logged, normalization)
            if note:
                short.append(note)
            values.append(record["mscf1"])
            files.extend(used)
        table[section] = values
    if logged:
        files.append(inv.SELECTION_COUNTS)
    return table, files, short


def expected_max(values, k):
    """Exact E[max] over all k-subsets: sum_i x_(i) C(i-1, k-1) / C(n, k), x ascending."""
    x = sorted(values)
    n = len(x)
    return sum(x[i] * math.comb(i, k - 1) for i in range(n)) / math.comb(n, k)


def percentile_of(value, values):
    below = sum(v < value for v in values)
    ties = sum(v == value for v in values)
    return 100.0 * (below + 0.5 * ties) / len(values)


def part_b(root, collection):
    table, files, short = scores(root, collection, B_SEEDS, inv.released_locations, "released")
    sections = []
    for section, values in table.items():
        sections.append({
            "collection": collection, "section": section, "n_seeds": len(values),
            "mean": float(np.mean(values)), "sd": float(np.std(values, ddof=1)),
            "min": float(min(values)), "max": float(max(values)),
            "published": PUBLISHED[collection][section],
            "published_percentile_within_our_seeds": percentile_of(PUBLISHED[collection][section], values),
            "seed_scores": json.dumps([round(v, 6) for v in values]),
        })
    matrix = np.array([table[s] for s in inv.SECTIONS[collection]])
    seed_means = matrix.mean(axis=0)
    published = PUBLISHED_MEAN[collection]
    b1 = ("inside our seed distribution" if published <= seed_means.max()
          else "outside our seed distribution")
    curve = [float(np.mean([expected_max(table[s], k) for s in table])) for k in range(1, 11)]
    reached = [k for k, value in zip(range(1, 11), curve) if value >= published]
    smallest = reached[0] if reached else None
    b2 = (f"consistent with per-section best-of-k selection (k = {smallest})" if smallest
          else "not explained by seed selection alone")
    summary = {
        "collection": collection, "seeds": list(B_SEEDS), "published_mean": published,
        "published_mean_of_sections": float(np.mean(list(PUBLISHED[collection].values()))),
        "seed_level_collection_means": {str(s): float(v) for s, v in zip(B_SEEDS, seed_means)},
        "collection_mean": float(seed_means.mean()), "collection_sd": float(np.std(seed_means, ddof=1)),
        "collection_mean_max": float(seed_means.max()), "collection_mean_min": float(seed_means.min()),
        "section_seed_sd_median": float(np.median([r["sd"] for r in sections])),
        "section_seed_sd_min": float(min(r["sd"] for r in sections)),
        "section_seed_sd_max": float(max(r["sd"] for r in sections)),
        "consistency_label": b1,
        "best_of_k_expected_mean": {str(k): v for k, v in zip(range(1, 11), curve)},
        "best_of_k_smallest_k": smallest, "best_of_k_label": b2,
        "question_ids": "B1, B2" if collection == "GBM" else "B3 (B1 and B2 for CAC)",
        "n_runs": len(B_SEEDS) * len(table), "short_peak_lists": short,
    }
    return summary, sections, files


def part_d(root):
    tic, files_t, short_t = scores(root, "GBM", D_SEEDS, inv.paper_tic_locations, "released", "paper_tic")
    rel, files_r, short_r = scores(root, "GBM", D_SEEDS, inv.released_locations, "released")
    rows = []
    for section in inv.SECTIONS["GBM"]:
        rows.append({"section": section,
                     "tic_seed_mean": float(np.mean(tic[section])),
                     "released_seed_mean": float(np.mean(rel[section])),
                     "difference_tic_minus_released": float(np.mean(tic[section]) - np.mean(rel[section])),
                     "tic_seed_scores": json.dumps([round(v, 6) for v in tic[section]]),
                     "released_seed_scores": json.dumps([round(v, 6) for v in rel[section]])})
    tic_mean = float(np.mean([r["tic_seed_mean"] for r in rows]))
    rel_mean = float(np.mean([r["released_seed_mean"] for r in rows]))
    rise = tic_mean - rel_mean
    if tic_mean >= D_EXPLAINS:
        label = "explains the gap"
    elif rise >= D_PARTLY_RISE:
        label = "partly"
    else:
        label = "does not explain"
    stats = ps.paired_summary([r["difference_tic_minus_released"] for r in rows])
    summary = {"label": label, "label_with_disclosure": f"{label}; {D_DISCLOSURE}",
               "tic_collection_mean": tic_mean, "released_collection_mean": rel_mean,
               "rise": rise, "thresholds": {"explains": D_EXPLAINS, "partly_rise": D_PARTLY_RISE},
               "paired_statistics_tic_minus_released": stats,
               "unit": "per-section mean over seeds 1-3; n = 8 sections (4 PDX lines)",
               "short_peak_lists": short_t + short_r}
    return summary, rows, files_t + files_r


def run(root, output, part):
    output = Path(output)
    if output.exists():
        print(f"refusing: {output} exists; move it aside first", file=sys.stderr)
        return 3
    result = {"protocol": PROTOCOL, "part": part,
              "evaluator": "S3PL in-job mSCF1 (metrics.json); not the fair-scoring evaluator",
              "notes": list(NOTES)}
    files, tables = [], {}
    if part == "B":
        result["collections"] = {}
        tables["sections.csv"] = []
        for collection in ("GBM", "CAC"):
            summary, sections, used = part_b(root, collection)
            result["collections"][collection] = summary
            tables["sections.csv"] += sections
            files += used
        result["short_peak_lists"] = inv.short_list_sentence(
            [s for c in result["collections"].values() for s in c["short_peak_lists"]],
            sum(c["n_runs"] for c in result["collections"].values()))
    else:
        summary, rows, files = part_d(root)
        result["D"] = summary
        tables["sections.csv"] = rows
    result["provenance"] = {
        "inputs": [inv.file_record(root, rel) for rel in sorted(set(files), key=str)],
        "code": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in (Path(__file__).resolve(), Path(inv.__file__).resolve(),
                           Path(ps.__file__).resolve())},
        "versions": inv.versions(),
    }
    output.mkdir(parents=True)
    for name, rows in tables.items():
        inv.write_csv(output / name, rows)
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--part", choices=("B", "D"), required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    default = DEFAULT_OUTPUT / ("part_b" if args.part == "B" else "part_d")
    return run(args.root, args.output or args.root / default, args.part)


if __name__ == "__main__":
    sys.exit(main())
