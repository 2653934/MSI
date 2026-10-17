#!/usr/bin/env python3
"""Test N decision table (protocol 18 Section 6.5; supervisor chat 2026-10-17 13:04).

Per CAC section and seed: real S3PL minus S3PL retrained with shuffled nonlocal
neighbours (``_train_shuffle_nonlocal``), at the matched peak count of
``s3pl_cac_controls.csv``. Rule, per seed and then both:
- "S3PL depends on spatially correct neighbours": difference >= 0.02 on >= 7/8
  sections and mean >= 0.02, in both seeds;
- "not spatially specific": |mean| < 0.02 in both seeds;
- otherwise "mixed"; a seed with fewer than 8 sections: "incomplete; no verdict".
Descriptive: shuffled vs the retrained centre-tiled control, and vs mean intensity
at the same count (fair-scoring bin level, seed-1 central_only summary; a
different scorer and representation, TIC-normalised HDF5 bins, so labelled).

Validity (refuse on failure): the real mSCF1 of each seed is recomputed from its
saved metrics.json and must equal the saved ``real`` column; every shuffled run
must be the predeclared configuration (mode, map seed 1701, seeds, count,
epochs, patch size, normalisation). Local files only.
"""

import argparse
import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
S3PL = RESULTS / "baselines" / "s3pl"
CONTROLS = RESULTS / "publication" / "current_evidence" / "s3pl_cac_controls.csv"
SEED2_REAL = ROOT / "reproducibility" / "s3pl_cac_centre_control" / "seed2_init2_order1"
SHUFFLE = ROOT / "reproducibility" / "s3pl_cac_shuffle_control"
FAIR = RESULTS / "diagnostics" / "fair_scoring_baselines" / "bin_level_only"
CAC_COUNTS = (("40TopL", 315), ("160TopL", 210), ("200TopL", 221), ("240TopL", 255),
              ("280TopL", 245), ("360TopL", 247), ("400TopL", 133), ("520TopL", 232))
SEEDS = {1: {"root": "seed1_released", "initialization_seed": None, "sample_order_seed": None},
         2: {"root": "seed2_init2_order1", "initialization_seed": 2, "sample_order_seed": 1}}
PRACTICAL = 0.02
MIN_SECTIONS = 7
DEPENDS = "S3PL depends on spatially correct neighbours"
NOT_SPECIFIC = "not spatially specific"
MIXED = "mixed"
REAL_TOLERANCE = 1e-12


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def unrounded_mscf1(metrics, what):
    value = statistics.fmean(float(v) for v in metrics["mixed_f1"].values())
    if round(value, 3) != round(float(metrics["mSCF1"]), 3):
        raise SystemExit(f"{what}: mixed-F1 mean {value} does not round to {metrics['mSCF1']}")
    return value


def base_name(section):
    return f"{section}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9"


def real_value(section, count, seed):
    if seed == 1:
        path = S3PL / f"{base_name(section)}_matched_{count}peaks" / "metrics.json"
    else:
        path = SEED2_REAL / "results" / "baselines" / "s3pl" / base_name(section) / "metrics.json"
    metrics = load(path)
    if metrics["number_picked_peaks"] != count:
        raise SystemExit(f"{path}: real run picked {metrics['number_picked_peaks']}, not {count}")
    return unrounded_mscf1(metrics, f"seed {seed} {section} real")


def shuffled_value(section, count, seed, shuffle_root=SHUFFLE):
    """The shuffled run's mSCF1, or None when it does not exist yet."""
    root = Path(shuffle_root) / SEEDS[seed]["root"]
    name = f"{base_name(section)}_train_shuffle_nonlocal"
    metrics_path = root / "results" / "baselines" / "s3pl" / name / "metrics.json"
    if not metrics_path.exists():
        return None
    metrics = load(metrics_path)
    config = load(root / "logs" / "s3pl" / f"{name}.json")
    expected = {"input_context_mode": "shuffle_nonlocal", "neighbour_shuffle_seed": 1701,
                "random_seed": 1, "n_epochs": 10, "spectral_patch_size": 9,
                "number_peaks": count, "peaks_per_spectral_patch": 256, "batch_size": 16,
                "initialization_seed": SEEDS[seed]["initialization_seed"],
                "sample_order_seed": SEEDS[seed]["sample_order_seed"]}
    wrong = {k: config.get(k) for k, v in expected.items() if config.get(k) != v}
    if config.get("normalization", "reference_spatial_max") != "reference_spatial_max":
        wrong["normalization"] = config.get("normalization")
    if wrong:
        raise SystemExit(f"{name} seed {seed}: not the predeclared configuration: {wrong}")
    if (metrics["number_picked_peaks"] != count
            or metrics.get("training_input_context_mode") != "shuffle_nonlocal"
            or metrics.get("source_training_name", name) != name):
        raise SystemExit(f"{metrics_path}: count, input mode or training name differs")
    return unrounded_mscf1(metrics, f"seed {seed} {section} shuffled")


def mean_intensity(section, count):
    path = FAIR / f"{section}_seed1" / "central_only" / "summary.json"
    if not path.exists():
        return None
    summary = load(path)
    if int(summary["K_bin"]) != count:
        raise SystemExit(f"{path}: K_bin {summary['K_bin']} differs from the S3PL count {count}")
    return float(summary["bin_level"]["mean_intensity"]["1.0"]["mSCF1"])


def seed_record(differences):
    return {"sections": len(differences),
            "sections_at_least_0.02": sum(d >= PRACTICAL for d in differences),
            "mean_difference": statistics.fmean(differences) if differences else None,
            "per_section": differences}


def decide(per_seed, expected=len(CAC_COUNTS)):
    if any(r["sections"] != expected for r in per_seed.values()) or set(per_seed) != {1, 2}:
        counts = ", ".join(f"seed {s}: {r['sections']}/{expected}" for s, r in sorted(per_seed.items()))
        return f"incomplete; no verdict ({counts})"
    records = per_seed.values()
    if all(r["sections_at_least_0.02"] >= MIN_SECTIONS and r["mean_difference"] >= PRACTICAL
           for r in records):
        return DEPENDS
    if all(abs(r["mean_difference"]) < PRACTICAL for r in records):
        return NOT_SPECIFIC
    return MIXED


def controls_table(path=CONTROLS):
    with open(path, encoding="utf-8") as stream:
        return {(r["section"], int(r["seed"])): r for r in csv.DictReader(stream)}


def build(shuffle_root=SHUFFLE, controls=CONTROLS):
    saved = controls_table(controls)
    rows, per_seed = [], {}
    for seed in SEEDS:
        differences = []
        for section, count in CAC_COUNTS:
            record = saved[(section, seed)]
            if int(record["matched_peaks"]) != count:
                raise SystemExit(f"{section} seed {seed}: saved matched count differs")
            real = real_value(section, count, seed)
            if abs(real - float(record["real"])) > REAL_TOLERANCE:
                raise SystemExit(f"{section} seed {seed}: real {real} does not reproduce the "
                                 f"saved real column {record['real']}")
            shuffled = shuffled_value(section, count, seed, shuffle_root)
            tile = float(record["retrained_tile_centre"])
            mean_int = mean_intensity(section, count)
            row = {"section": section, "seed": seed, "matched_peaks": count, "real": real,
                   "retrained_shuffle_nonlocal": shuffled, "retrained_tile_centre": tile,
                   "mean_intensity_fair_scoring_bin": mean_int,
                   "real_minus_shuffled": None if shuffled is None else real - shuffled,
                   "shuffled_minus_tile_centre": None if shuffled is None else shuffled - tile,
                   "shuffled_minus_mean_intensity": (None if shuffled is None or mean_int is None
                                                     else shuffled - mean_int)}
            rows.append(row)
            if shuffled is not None:
                differences.append(real - shuffled)
        per_seed[seed] = seed_record(differences)
    complete = [r for r in rows if r["retrained_shuffle_nonlocal"] is not None]
    descriptive = {
        "status": "descriptive only; no verdict",
        "shuffled_minus_tile_centre_mean": {
            s: (statistics.fmean(r["shuffled_minus_tile_centre"] for r in complete if r["seed"] == s)
                if any(r["seed"] == s for r in complete) else None) for s in SEEDS},
        "shuffled_minus_mean_intensity_mean": {
            s: (statistics.fmean(r["shuffled_minus_mean_intensity"] for r in complete
                                 if r["seed"] == s and r["shuffled_minus_mean_intensity"] is not None)
                if any(r["seed"] == s and r["shuffled_minus_mean_intensity"] is not None
                       for r in complete) else None) for s in SEEDS},
        "mean_intensity_note": ("fair-scoring bin-level mean intensity at K_bin = the matched "
                                "count, on TIC-normalised HDF5 bins with the fair-scoring "
                                "scorer; not the S3PL evaluator on imzML m/z values"),
    }
    decision = {"rule": "real minus retrained shuffled-nonlocal, per seed then both: >= 0.02 "
                        "on >= 7/8 and mean >= 0.02 in both seeds; |mean| < 0.02 in both; "
                        "otherwise mixed",
                "per_seed": {str(s): r for s, r in per_seed.items()},
                "verdict": decide(per_seed),
                "reconstruction_target": "the input patch (shuffled neighbours, real centre)",
                "real_reproduced_from_saved_metrics": True,
                "descriptive": descriptive,
                "note": "CAC is one biopsy (8 regions); sections are not independent patients"}
    return rows, decision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=RESULTS / "diagnostics" / "s3pl_cac_shuffle_control" /
                        "decisions_local")
    args = parser.parse_args()
    rows, decision = build()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "decisions.json").write_text(json.dumps(decision, indent=2) + "\n",
                                                encoding="utf-8")
    with open(args.output / "section_table.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    for seed, record in decision["per_seed"].items():
        mean = record["mean_difference"]
        print(f"seed {seed}: {record['sections']}/8 sections, >= 0.02 in "
              f"{record['sections_at_least_0.02']}, mean "
              + ("n/a" if mean is None else f"{mean:+.3f}"))
    print(f"Test N: {decision['verdict']}")


if __name__ == "__main__":
    main()
