#!/usr/bin/env python3
"""Protocol 18 Section 6.7 (Investigation 21), Part C: which part of the S3PL seed matters.

Local only. Three GBM sections (GBM108_positive, GBM108_negative, GBM12_2; the largest
saved init-screen seed SD, chat 2026-10-20 11:42), released settings (10 epochs, p3, z256,
reference_spatial_max, random_seed 1), S3PL's own in-job mSCF1 recomputed unrounded.

Arms per section (saved runs reused, chat 11:46 Q5):
- "init varies": initialization_seed 1-5, sample_order_seed 1;
- "order varies": sample_order_seed 1-5, initialization_seed 1;
- "repeat": the released random_seed 1 run three times (the August original plus two
  repeats), the nondeterminism floor.

Rule (Section 6.7, fixed before these runs): per section, the SD (ddof = 1) of each arm.
- A component is "dominant" if its SD is >= 2x the other's in >= 2 of the 3 sections.
  Edge case written here before the runs: an SD of 0 is never dominant (0 >= 2 x 0).
- "dominated by nondeterminism" if the repeat SD is >= half the smaller arm's SD.
  Section 6.7 does not say how sections combine for this clause. This script reports it
  per section and applies the same ">= 2 of the 3 sections" count as the dominance clause;
  a repeat SD of 0 never meets it. Both readings are reported for the supervisor to confirm.

Nondeterminism check (descriptive): per section, whether the three repeats are
bit-identical in all 10 losses, mixed_f1 and the picked-peak SHA-256.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import summarise_s3pl_seed_investigation_21 as inv  # noqa: E402

PROTOCOL = ("protocol 18 Section 6.7 (Investigation 21), Part C; supervisor chat 2026-10-20 10:53, "
            "11:42 plan, 11:46 Q5, 20:57")
DEFAULT_OUTPUT = Path("results") / "diagnostics" / "s3pl_seed_investigation_21" / "part_c"
SECTIONS = ("GBM108_positive", "GBM108_negative", "GBM12_2")
SEEDS = (1, 2, 3, 4, 5)
REPEATS = (0, 1, 2)
MASSNET = Path("reproducibility") / "s3pl_massnet"
PART_C = inv.INVESTIGATION_ROOT / "part_c"
NOTES = (
    "Descriptive arms of 5 runs (init, order) and 3 runs (repeat) per section; n = 3 sections.",
    "S3PL in-job mSCF1 (metrics.json), recomputed unrounded; not the fair-scoring evaluator.",
    "The init and order arms share the init 1 / order 1 run.",
    "GBM108_positive's init and order pattern was largely visible from saved runs before "
    "Part C (chat 11:46 Q5); its new information is the repeat arm.",
    "Investigation 21 GPU jobs were not exclusive (bigbatch has no GPU gres).",
)


def controlled_locations(section, init, order):
    name = inv.run_name("GBM", section)
    folder = f"{section}_p3_rng_init{init}_order{order}"
    saved = (init <= 3 and order == 1) or (section == "GBM108_positive" and (order == 1 or (init, order) == (1, 2)))
    return inv._run_paths((MASSNET if saved else PART_C) / folder, name)


def repeat_locations(section, repeat):
    name = inv.run_name("GBM", section)
    if repeat == 0:
        return inv.released_locations("GBM", section, 1)
    if (section, repeat) == ("GBM108_positive", 1):
        return inv._run_paths(MASSNET / "GBM108_positive_p3_seed1_repeat1", name)
    if (section, repeat) == ("GBM12_2", 1):
        return inv._run_paths(inv.INVESTIGATION_ROOT / "gate_repeat" / "GBM12_2_p3_seed1_repeat_r2", name)
    return inv._run_paths(PART_C / f"{section}_p3_seed1_repeat{repeat}", name)


def arm_runs():
    """[(arm, section, init, order, repeat, locate)] in a fixed order."""
    runs = []
    for section in SECTIONS:
        for init in SEEDS:
            runs.append(("init", section, init, 1, None))
        for order in SEEDS:
            runs.append(("order", section, 1, order, None))
        for repeat in REPEATS:
            runs.append(("repeat", section, None, None, repeat))
    return runs


def load(root, arm, section, init, order, repeat, native):
    if arm == "repeat":
        locate = lambda c, s, _seed: repeat_locations(s, repeat)  # noqa: E731
    else:
        locate = lambda c, s, _seed: controlled_locations(s, init, order)  # noqa: E731
    record, _, used = inv.load_run(root, "GBM", section, 1, locate)
    controlled = (record["initialization_seed"], record["sample_order_seed"])
    expected = (None, None) if arm == "repeat" else (init, order)
    if record["random_seed"] != 1 or controlled != expected or record["normalization"] not in (
            None, "reference_spatial_max"):
        raise ValueError(f"{record['results_folder']}: saved seeds {record['random_seed']}, {controlled} "
                         f"do not match {arm} {expected}")
    inv.check_peak_count(record, native, {})
    log, results = locate("GBM", section, 1)
    history = json.loads((Path(root) / log).read_text())["train_history"]
    mixed = json.loads((Path(root) / results / "metrics.json").read_text())["mixed_f1"]
    record.update({"arm": arm, "init": init, "order": order, "repeat": repeat,
                   "train_history": json.dumps(history), "mixed_f1": json.dumps(mixed, sort_keys=True)})
    return record, used


def sd(values):
    # Identical values give exactly 0 (np.std can return ~1e-17 from the mean's rounding),
    # so the "> 0" guards below see bit-identical repeats as zero spread.
    return 0.0 if len(set(values)) == 1 else float(np.std(values, ddof=1))


def dominates(a, b):
    return a > 0 and a >= 2 * b


def summarise(root):
    native = inv.native_counts()
    runs, files = [], []
    for arm, section, init, order, repeat in arm_runs():
        record, used = load(root, arm, section, init, order, repeat, native[section])
        runs.append(record)
        files.extend(used)
    sections = []
    for section in SECTIONS:
        by_arm = {arm: [r for r in runs if r["section"] == section and r["arm"] == arm]
                  for arm in ("init", "order", "repeat")}
        s = {arm: sd([r["mscf1"] for r in rows]) for arm, rows in by_arm.items()}
        smaller = min(s["init"], s["order"])
        reps = by_arm["repeat"]
        identical = all(r[k] == reps[0][k] for r in reps for k in ("train_history", "mixed_f1", "peaks_sha256"))
        sections.append({
            "section": section,
            "init_sd": s["init"], "order_sd": s["order"], "repeat_sd": s["repeat"],
            "init_scores": json.dumps([round(r["mscf1"], 6) for r in by_arm["init"]]),
            "order_scores": json.dumps([round(r["mscf1"], 6) for r in by_arm["order"]]),
            "repeat_scores": json.dumps([round(r["mscf1"], 6) for r in reps]),
            "init_ge_2x_order": dominates(s["init"], s["order"]),
            "order_ge_2x_init": dominates(s["order"], s["init"]),
            "repeat_ge_half_smaller_arm": s["repeat"] > 0 and s["repeat"] >= 0.5 * smaller,
            "repeats_bit_identical": identical,
            "repeat_distinct_peak_lists": len({r["peaks_sha256"] for r in reps}),
        })
    init_count = sum(r["init_ge_2x_order"] for r in sections)
    order_count = sum(r["order_ge_2x_init"] for r in sections)
    if init_count >= 2:
        dominant = "initialisation dominant"
    elif order_count >= 2:
        dominant = "data order dominant"
    else:
        dominant = "neither component dominant"
    nondet_count = sum(r["repeat_ge_half_smaller_arm"] for r in sections)
    summary = {
        "dominant_label": dominant,
        "sections_init_ge_2x_order": init_count, "sections_order_ge_2x_init": order_count,
        "nondeterminism_label": ("dominated by nondeterminism" if nondet_count >= 2
                                 else "not dominated by nondeterminism"),
        "nondeterminism_aggregation": ">= 2 of 3 sections (Code's reading; Section 6.7 does not "
                                      "specify; per-section values reported)",
        "sections_repeat_ge_half_smaller_arm": nondet_count,
        "sections_repeats_bit_identical": sum(r["repeats_bit_identical"] for r in sections),
    }
    return summary, sections, runs, files


def run(root, output):
    output = Path(output)
    if output.exists():
        print(f"refusing: {output} exists; move it aside first", file=sys.stderr)
        return 3
    summary, sections, runs, files = summarise(root)
    result = {"protocol": PROTOCOL, "part": "C",
              "evaluator": "S3PL in-job mSCF1 (metrics.json); not the fair-scoring evaluator",
              "C": summary, "notes": list(NOTES),
              "provenance": {
                  "inputs": [inv.file_record(root, rel) for rel in sorted(set(files), key=str)],
                  "code": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in (Path(__file__).resolve(), Path(inv.__file__).resolve())},
                  "versions": inv.versions()}}
    output.mkdir(parents=True)
    inv.write_csv(output / "sections.csv", sections)
    inv.write_csv(output / "runs.csv", runs)
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    return run(args.root, args.output or args.root / DEFAULT_OUTPUT)


if __name__ == "__main__":
    sys.exit(main())
