#!/usr/bin/env python3
"""Adapter gate for S3PL on RCC (supervisor chat 2026-10-16 22:07, overnight item 3).

S3PL reads a folder laid out like the GBM one: <run>.h5 plus masks/<run>_mask.npy
(dataname = the file stem, which keys num_GT_peaks). The RCC exports are named
RCC_<run>.h5, so --stage copies each one (and its mask) byte for byte into the
staging folder and checks the sha256 of every copy. No S3PL code changes, so the
GBM/CAC loading paths are untouched.

Then, for every run, S3PL's own create_pearson_labels builds the class rankings in
the staging folder, and the mixed reference set at PCC 0.5 is formed with the rule
of PeakEvaluation.get_groundtruth (per class: the bins before the ranked value
closest to the threshold; union over classes). The gate passes only if that size
equals our |R@0.5| (released_target_budget.json) for every run. The difference from
the released num_GT_peaks is recorded. Exit 4 if the gate fails.
"""

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

S3PL_ROOT = Path(__file__).resolve().parents[1] / "baselines" / "s3pl"
THRESHOLD = 0.5
GATE_VERSION = 1


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path,
                        help="folder with RCC_<run>.h5 and RCC_<run>_mask.npy")
    parser.add_argument("--staging-dir", required=True, type=Path,
                        help="S3PL folder: <run>.h5 and masks/<run>_mask.npy")
    parser.add_argument("--budget-root", required=True, type=Path,
                        help="folder with RCC_<run>_seed1/released_target_budget.json")
    parser.add_argument("--runs", required=True, nargs="+", help="run names, e.g. MH0204_33")
    parser.add_argument("--classes", type=int, default=3)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--stage", action="store_true",
                        help="copy the exports into the staging folder first")
    parser.add_argument("--allow-outside-slurm", action="store_true",
                        help="tests only; real runs must be inside Slurm")
    return parser.parse_args()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage(source_dir, staging_dir, run):
    """Copy RCC_<run>.h5 and its mask; refuse a different existing file."""
    pairs = [(source_dir / f"RCC_{run}.h5", staging_dir / f"{run}.h5"),
             (source_dir / f"RCC_{run}_mask.npy", staging_dir / "masks" / f"{run}_mask.npy")]
    records = {}
    for source, target in pairs:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if sha256(target) != sha256(source):
                raise SystemExit(f"{target} exists and differs from {source}; move it aside")
        else:
            shutil.copyfile(source, target)
        digest = sha256(target)
        if digest != sha256(source):
            raise SystemExit(f"copy of {source} does not match")
        records[target.name] = {"source": str(source), "sha256": digest}
    return records


def reference_size(labels_dir, run, classes, threshold):
    """PeakEvaluation.get_groundtruth: per-class prefix before the value closest to t."""
    union = set()
    for class_id in range(classes):
        ranking = np.load(labels_dir / f"{run}_class{class_id}_ranking.npy")
        pearson = np.load(labels_dir / f"{run}_class{class_id}_pearson_ranking.npy")
        count = int(np.argmin(np.abs(pearson - threshold)))
        union.update(ranking[:count].tolist())
    return len(union)


def main():
    args = parse_arguments()
    if not args.allow_outside_slurm:
        import os
        if not os.environ.get("SLURM_JOB_ID"):
            raise SystemExit("Refusing to process data outside a Slurm job (no SLURM_JOB_ID)")
    started = time.perf_counter()
    sys.path.insert(0, str(S3PL_ROOT))
    import data_configs
    from utils.create_pearson_labels import create_pearson_labels

    records = {}
    passed = True
    for run in args.runs:
        record = {}
        if args.stage:
            record["staged"] = stage(args.source_dir, args.staging_dir, run)
        mask = np.load(args.staging_dir / "masks" / f"{run}_mask.npy")
        record["mask_classes"] = sorted(np.unique(mask).tolist())
        if record["mask_classes"] != list(range(args.classes)):
            raise SystemExit(f"{run}: mask classes {record['mask_classes']} != 0..{args.classes - 1}")
        create_pearson_labels(run, str(args.staging_dir) + "/", args.classes,
                              data_path=args.staging_dir / f"{run}.h5")
        size = reference_size(args.staging_dir / "labels", run, args.classes, THRESHOLD)
        budget = json.loads((args.budget_root / f"RCC_{run}_seed1" /
                             "released_target_budget.json").read_text(encoding="utf-8"))
        ours = int(budget["released_target"]["our_R_at_0.5"])
        target = int(data_configs.num_GT_peaks[run])
        record.update({"s3pl_R_at_0.5": size, "our_R_at_0.5": ours,
                       "released_num_GT_peaks": target, "equal_to_ours": size == ours,
                       "s3pl_minus_released": size - target})
        passed &= size == ours
        records[run] = record
        print(f"{run}: S3PL |R@0.5| = {size}, ours = {ours}, released = {target}", flush=True)
    summary = {
        "gate_version": GATE_VERSION,
        "status": "passed" if passed else "failed",
        "rule": ("S3PL's own create_pearson_labels on the staged RCC data must give the "
                 "PeakEvaluation reference-set size at PCC 0.5 equal to our |R@0.5| for "
                 "every run (supervisor chat 2026-10-16 22:07, item 3)"),
        "threshold": THRESHOLD,
        "classes": args.classes,
        "class_order": "cancer 0, normal 1, unannotated 2 (the paper's background role)",
        "code_sha256": {Path(__file__).name: sha256(__file__),
                        "create_pearson_labels.py": sha256(
                            S3PL_ROOT / "utils" / "create_pearson_labels.py"),
                        "data_configs.py": sha256(S3PL_ROOT / "data_configs.py")},
        "runs": records,
        "runtime_seconds": time.perf_counter() - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"adapter gate: {summary['status']}")
    if not passed:
        raise SystemExit(4)


if __name__ == "__main__":
    main()
