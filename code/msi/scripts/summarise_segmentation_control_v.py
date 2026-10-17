#!/usr/bin/env python3
"""Test V decision table (protocol 18 Section 6.4; supervisor chat 2026-10-17 12:42).

Reads <root>/<collection>/<section>_seed1/summary.json written by
evaluate_segmentation_control_v.py and applies the predeclared rule per
collection to VAE centre-only posterior-|PCC| minus PCA-5 posterior-|PCC|:
- "VAE segmentation helps": mean >= +0.02 and positive in >= 6/8, at every
  applicable scale (GBM/CAC bin and P1; RCC bin);
- "equivalent": |mean| < 0.02 at every applicable scale;
- "PCA better": mean <= -0.02 and VAE positive in <= 2/8, at every applicable scale;
- otherwise "mixed"; fewer than 8 sections: "incomplete; no verdict (n/8 sections)".
Descriptive only, never decided: (a) PCA-20, (b) segmentation balanced accuracy,
(c) PCA-5 against Moran's I and IG, VAE uniform_mean against PCA-5, and (d) when
Test R fair scoring exists for both seeds 2 and 3, the VAE side as the mean over
seeds 1-3. Refuses mixed code or settings, a wrong scale set for the collection,
unknown sections and folder/dataset mismatches. Local files only.
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from summarise_fair_scoring_baselines import paired

PRACTICAL = 0.02
MIN_POSITIVE = 6
MAX_POSITIVE_PCA = 2
N_SECTIONS = 8
SECTIONS = {
    "GBM": ("GBM108_negative", "GBM108_positive", "GBM12_1", "GBM12_2", "GBM22_1",
            "GBM22_2", "GBM39_1", "GBM39_2"),
    "CAC": ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL", "400TopL",
            "520TopL"),
    "RCC": ("RCC_MH0204_33", "RCC_UH0505_12", "RCC_UH0710_33", "RCC_UH9610_15",
            "RCC_UH9812_03", "RCC_UH9905_18", "RCC_UH9911_05", "RCC_UH9912_01"),
}
SCALES = {"GBM": ("bin", "P1"), "CAC": ("bin", "P1"), "RCC": ("bin",)}
PLAIN = "posterior_abs_pcc_balanced"
PCA5, PCA20 = f"pca5_{PLAIN}", f"pca20_{PLAIN}"
MORANS, IG, UNIFORM = "morans_i", "integrated_gradients", f"vae_uniform_mean_{PLAIN}"
HELPS = "VAE segmentation helps"
EQUIVALENT = "equivalent"
PCA_BETTER = "PCA better"
MIXED = "mixed"
DEFAULT_TEST_R_FAIR = (Path(__file__).resolve().parents[1] / "results" / "diagnostics"
                       / "fair_scoring_baselines" / "test_r")
NOTES = {
    "GBM": "8 sections from 4 patients; sections are not independent patients",
    "CAC": ("CAC P1 is singleton groups, so its peak-level score is the bin-level score at "
            "the K_peak budget; requiring both is a two-budget check"),
    "RCC": ("bin level only (protocol 18 Section 6.1 amendment); unannotated class, 45-78% "
            "of pixels; the dataset's own Cardinal workflow treats these pixels as "
            "background (rcc_nobg), but this was not independently verified; GMM K = 3 is "
            "class-informed; uniform_mean UH0505_12 has no seed-1 result (IG not done)"),
}


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path,
                        help="results/diagnostics/segmentation_control_V")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--test-r-fair", type=Path, default=DEFAULT_TEST_R_FAIR,
                        help="Test R fair-scoring root, for descriptive item (d)")
    return parser.parse_args()


def decide(by_scale, sections, expected=N_SECTIONS):
    """The 12:42 rule on the paired VAE - PCA-5 records of every applicable scale."""
    if sections != expected:
        return f"incomplete; no verdict ({sections}/{expected} sections)"
    records = by_scale.values()
    if all(r["mean_difference"] >= PRACTICAL and r["positive_sections"] >= MIN_POSITIVE
           for r in records):
        return HELPS
    if all(abs(r["mean_difference"]) < PRACTICAL for r in records):
        return EQUIVALENT
    if all(r["mean_difference"] <= -PRACTICAL and r["positive_sections"] <= MAX_POSITIVE_PCA
           for r in records):
        return PCA_BETTER
    return MIXED


def test_r_values(fair_root, section, scale):
    """VAE central_only posterior-|PCC| at seeds 2/3 from complete Test R fair scoring."""
    scope = "bin_level_only" if scale == "bin" else "with_approved_partitions"
    values = {}
    for seed in (2, 3):
        path = Path(fair_root) / scope / f"{section}_seed{seed}" / "central_only" / "summary.json"
        if not path.exists():
            continue
        summary = json.loads(path.read_text(encoding="utf-8"))
        if summary.get("status") != "complete" or summary.get("class_subset") is not None:
            continue
        if scale == "bin":
            values[seed] = float(summary["bin_level"][PLAIN]["1.0"]["mSCF1"])
        else:
            values[seed] = float(summary["peak_level"]["P1"]["methods"][PLAIN]
                                 ["matched_K_peak"]["mSCF1"])
    return values


def load(root):
    records, keys = [], set()
    for path in sorted(root.glob("*/*_seed1/summary.json")):
        collection, section = path.parents[1].name, path.parent.name[:-len("_seed1")]
        if collection not in SECTIONS or section not in SECTIONS[collection]:
            raise SystemExit(f"{path}: {section} is not a {collection} section")
        summary = json.loads(path.read_text(encoding="utf-8"))
        if summary.get("status") != "complete" or summary.get("dataset") != section:
            raise SystemExit(f"{path}: not a complete Test V result for {section}")
        parameters = summary["provenance"]["parameters"]
        if tuple(parameters.get("scales", ())) != SCALES[collection]:
            raise SystemExit(f"{path}: scales {parameters.get('scales')} but {collection} "
                             f"needs {list(SCALES[collection])}")
        shared = {k: v for k, v in parameters.items() if k not in ("gmm_components", "scales")}
        keys.add(json.dumps({"version": summary["provenance"]["test_v_version"],
                             "parameters": shared, "code": summary["provenance"]["code"]},
                            sort_keys=True))
        records.append((collection, section, summary))
    if not records:
        raise SystemExit(f"no Test V summaries under {root}")
    if len(keys) != 1:
        raise SystemExit("Test V results come from different code or settings; "
                         "refusing to mix them in one table")
    return records


def mean_or_none(values):
    values = [v for v in values if v is not None]
    return float(np.mean(values)) if values else None


def main():
    args = parse_arguments()
    records = load(args.root)
    rows = []
    for collection, section, summary in records:
        row = {"collection": collection, "section": section, "K_bin": summary["K_bin"]}
        for scale, values in summary["mSCF1"].items():
            for name, value in values.items():
                row[f"{scale}:{name}"] = value
            for name, value in summary["saved_descriptive"][scale].items():
                row[f"{scale}:{name}"] = value
            seeds = test_r_values(args.test_r_fair, section, scale)
            row[f"{scale}:vae_seed_mean_1_3"] = (
                float(np.mean([values[PLAIN], seeds[2], seeds[3]]))
                if set(seeds) == {2, 3} else None)
        for key, agreement in summary["segmentation_vs_expert"].items():
            if isinstance(agreement, dict):
                row[f"balanced_accuracy_{key}"] = agreement.get("balanced_accuracy")
        for key, record in summary["pca"].items():
            row[f"explained_variance_{key}"] = record["explained_variance_ratio_sum"]
        rows.append(row)

    decisions = {}
    for collection in SECTIONS:
        subset = sorted((r for r in rows if r["collection"] == collection),
                        key=lambda r: SECTIONS[collection].index(r["section"]))
        if not subset:
            continue
        record = {"sections": [r["section"] for r in subset],
                  "scales": list(SCALES[collection]), "vae_minus_pca5": {},
                  "mean_mSCF1": {}}
        descriptive = {"status": "descriptive only; no verdict",
                       "a_vae_minus_pca20": {}, "c_pca5_minus_morans_i": {},
                       "c_pca5_minus_ig": {}, "vae_uniform_minus_pca5": {},
                       "d_vae_seed_mean_minus_pca5": None}
        seed_means = {}
        for scale in SCALES[collection]:
            column = lambda name: [r[f"{scale}:{name}"] for r in subset]
            record["vae_minus_pca5"][scale] = paired(column(PLAIN), column(PCA5))
            record["mean_mSCF1"][scale] = {name: mean_or_none(column(name))
                                           for name in (PLAIN, PCA5, PCA20, MORANS, IG, UNIFORM)}
            descriptive["a_vae_minus_pca20"][scale] = paired(column(PLAIN), column(PCA20))
            descriptive["c_pca5_minus_morans_i"][scale] = paired(column(PCA5), column(MORANS))
            descriptive["c_pca5_minus_ig"][scale] = paired(column(PCA5), column(IG))
            pairs = [(r[f"{scale}:{UNIFORM}"], r[f"{scale}:{PCA5}"]) for r in subset
                     if r[f"{scale}:{UNIFORM}"] is not None]
            descriptive["vae_uniform_minus_pca5"][scale] = (
                paired(*zip(*pairs)) if pairs else None)
            seeds = [(r[f"{scale}:vae_seed_mean_1_3"], r[f"{scale}:{PCA5}"]) for r in subset
                     if r[f"{scale}:vae_seed_mean_1_3"] is not None]
            if seeds:
                seed_means[scale] = paired(*zip(*seeds))
        if seed_means:
            descriptive["d_vae_seed_mean_minus_pca5"] = seed_means
        descriptive["b_balanced_accuracy_mean"] = {
            key: mean_or_none([r.get(f"balanced_accuracy_{key}") for r in subset])
            for key in ("vae_central_only", "pca5", "pca20")}
        descriptive["explained_variance_mean"] = {
            key: mean_or_none([r.get(f"explained_variance_{key}") for r in subset])
            for key in ("pca5", "pca20")}
        record["verdict"] = decide(record["vae_minus_pca5"], len(subset))
        record["descriptive"] = descriptive
        record["note"] = NOTES[collection]
        decisions[collection] = record

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "decisions.json").write_text(json.dumps(decisions, indent=2) + "\n",
                                                encoding="utf-8")
    fields = sorted({k for r in rows for k in r})
    with open(args.output / "section_table.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    for key, record in decisions.items():
        bits = ", ".join(f"{s} {v['mean_difference']:+.3f} ({v['positive_sections']}/"
                         f"{v['sections']})" for s, v in record["vae_minus_pca5"].items())
        print(f"{key}: {record['verdict']}; VAE - PCA-5 {bits}")


if __name__ == "__main__":
    main()
