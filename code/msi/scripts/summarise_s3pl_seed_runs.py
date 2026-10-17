#!/usr/bin/env python3
"""Per-section S3PL seed table against the published values (overnight items 2 and 3).

Reads each seed's released-protocol metrics.json, recomputes mSCF1 unrounded as
the mean of the four mixed F1 values, and writes section_table.csv and
summary.json with each seed, the published value (IonMorphNet
sota_comparison.py, investigation 19), the per-seed collection means and whether
each mean lies inside the published 95% CI. Descriptive only: a seed is never
selected. Reads local files only.

Fails closed (supervisor chat 2026-10-17 07:16): every run's provenance is
checked before anything is written, and any failure exits non-zero with no
table. Per run: metrics.json (dataset, normalisation, picked count against the
released num_GT_peaks, no frozen-input ablation or context mode, source
training name), the training log (seed, settings, data file, artifact root),
the seed manifest where one exists, and the picked-peaks CSV row count. The
sha256 of every file read is recorded.
"""

import argparse
import ast
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = {
    "cac": {
        "sections": ["40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL",
                     "400TopL", "520TopL"],
        "published": [0.68, 0.53, 0.61, 0.67, 0.63, 0.64, 0.35, 0.70],
        "published_mean": 0.601, "published_ci": [0.506, 0.697],
        "name": "{}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9",
        "settings": {"n_epochs": 10, "peaks_per_spectral_patch": 256, "spectral_patch_size": 9},
        "data_suffix": ".imzML",
        "manifest_settings": ("patch 9", "256 peaks/patch", "d1 51", "d2 1", "10 epochs",
                              "batch 16", "lr 1e-2", "reference_spatial_max"),
        "seeds": {1: "results/baselines/s3pl",
                  2: "reproducibility/s3pl_cac_seeds/seed2_released/results/baselines/s3pl",
                  3: "reproducibility/s3pl_cac_seeds/seed3_released/results/baselines/s3pl"},
    },
    "rcc": {
        "sections": ["MH0204_33", "UH0505_12", "UH0710_33", "UH9610_15", "UH9812_03",
                     "UH9905_18", "UH9911_05", "UH9912_01"],
        "published": [0.56, 0.44, 0.48, 0.14, 0.50, 0.51, 0.56, 0.57],
        "published_mean": 0.470, "published_ci": [0.352, 0.588],
        "name": "{}_Attention3DConvAutoencoder_10epochs_1024_spectral_patch_size_5",
        "settings": {"n_epochs": 10, "peaks_per_spectral_patch": 1024, "spectral_patch_size": 5},
        "data_suffix": ".h5",
        "manifest_settings": ("p 5", "z 1024", "d1 51", "d2 1", "10 epochs", "batch 16",
                              "lr 1e-2", "reference_spatial_max", "n = num_GT_peaks"),
        "seeds": {s: f"reproducibility/s3pl_rcc/seed{s}_released/results/baselines/s3pl"
                  for s in (1, 2, 3)},
    },
}
# Released settings shared by every run (baselines/s3pl/config.json).
RELEASED = {"kernel_depth_d1": 51, "kernel_depth_d2": 1, "batch_size": 16,
            "learning_rate": 0.01, "number_peaks": None}
NORMALIZATION = "reference_spatial_max"
ABLATION_KEYS = ("frozen_input_ablation", "training_input_context_mode",
                 "effective_input_context_mode")
# CAC seed 1 (results/baselines/s3pl, run 2026-08-21) predates the seed manifests
# and the normalisation option (3fb2f75, 2026-09-12): neither its metrics.json nor
# its training log records the normalisation, the ablation fields or the source
# training name. At that commit the only normalisation was the released one
# (tic_norm_spectra, renamed reference_spatial_max_norm in 3fb2f75). These runs are
# accepted with the gaps recorded; a field that is present must still be right, and
# any other run missing a field is refused.
PRE_PROVENANCE = {("cac", 1)}
PRE_PROVENANCE_NOTES = {
    "manifest": "no manifest (pre-manifest run)",
    "normalization": ("not recorded (run 2026-08-21, before the normalisation option "
                      "3fb2f75 of 2026-09-12; the only normalisation then was the "
                      "released reference_spatial_max)"),
    "ablation": ("not recorded (pre-ablation format); the training name has no "
                 "ablation suffix and the log no ablation setting"),
    "source_training_name": ("not recorded (pre-provenance format); the run folder and "
                             "the training log name match"),
}


class ProvenanceError(Exception):
    pass


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", required=True, choices=sorted(COLLECTIONS))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=ROOT,
                        help="workspace root holding the seed folders (tests only)")
    parser.add_argument("--data-configs", type=Path,
                        default=ROOT / "baselines" / "s3pl" / "data_configs.py")
    return parser.parse_args()


def released_targets(path):
    """num_GT_peaks from the released data_configs.py, parsed without importing it."""
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "num_GT_peaks" for t in node.targets):
            return ast.literal_eval(node.value)
    raise ProvenanceError(f"{path}: no num_GT_peaks")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    if not path.is_file():
        raise ProvenanceError(f"missing {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def expect(condition, message):
    if not condition:
        raise ProvenanceError(message)


def verify_run(collection, spec, section, seed, project_root, targets):
    """Check one run's provenance; return its metrics and the verified record."""
    name = spec["name"].format(section)
    results_root = project_root / spec["seeds"][seed]
    run_dir = results_root / name
    artifact_root = results_root.parents[2]  # <artifact root>/results/baselines/s3pl
    pre = (collection, seed) in PRE_PROVENANCE
    where = f"{collection.upper()} {section} seed {seed}"
    metrics_path = run_dir / "metrics.json"
    log_path = artifact_root / "logs" / "s3pl" / f"{name}.json"
    metrics, log = read_json(metrics_path), read_json(log_path)
    target = targets.get(section)
    expect(target is not None, f"{where}: no released num_GT_peaks")
    record = {"seed": seed, "training_name": name, "num_GT_peaks": target}

    # metrics.json; a field may be absent only in a pre-provenance run.
    expect(metrics.get("dataset") == section,
           f"{where}: metrics dataset {metrics.get('dataset')!r}, expected {section!r}")
    expect(metrics.get("number_picked_peaks") == target,
           f"{where}: picked {metrics.get('number_picked_peaks')} peaks, "
           f"num_GT_peaks is {target}")
    if "normalization" in metrics or not pre:
        expect(metrics.get("normalization") == NORMALIZATION,
               f"{where}: metrics normalisation {metrics.get('normalization')!r}, "
               f"expected {NORMALIZATION!r}")
    for key in ABLATION_KEYS:
        if key in metrics or not pre:
            expect(metrics.get(key) == "none", f"{where}: metrics {key} {metrics.get(key)!r}")
    if "source_training_name" in metrics or not pre:
        expect(metrics.get("source_training_name") == name,
               f"{where}: source_training_name {metrics.get('source_training_name')!r}, "
               f"expected {name!r}")

    # The run's own training log: seed, settings, data file, artifact root.
    expect(log.get("random_seed") == seed,
           f"{where}: training log seed {log.get('random_seed')!r}, table assigns {seed}")
    expect(log.get("training_name") == name,
           f"{where}: training log name {log.get('training_name')!r}")
    for key, value in {**spec["settings"], **RELEASED}.items():
        expect(log.get(key, "missing") == value,
               f"{where}: training log {key} {log.get(key, 'missing')!r}, expected {value!r}")
    if "normalization" in log or not pre:
        expect(log.get("normalization") == NORMALIZATION,
               f"{where}: training log normalisation {log.get('normalization')!r}")
    expect(Path(str(log.get("data_dir", ""))).name == section + spec["data_suffix"],
           f"{where}: training log data_dir {log.get('data_dir')!r}")
    relative = artifact_root.resolve().relative_to(project_root.resolve()).as_posix()
    expect(str(log.get("artifact_root", "")).rstrip("/").endswith(
               "/msi" if relative == "." else "/" + relative),
           f"{where}: training log artifact_root {log.get('artifact_root')!r}")

    peaks = sorted(run_dir.glob(f"picked_peaks_{section}_*peaks_z_patchsize_*.csv"))
    expect(len(peaks) == 1, f"{where}: expected one picked-peaks CSV, found {len(peaks)}")
    with open(peaks[0], encoding="utf-8") as stream:
        rows = sum(1 for line in stream if line.strip()) - 1  # header line
    expect(rows == target, f"{where}: picked-peaks CSV has {rows} rows, expected {target}")

    manifest = artifact_root / "provenance" / "manifest.txt"
    if manifest.is_file():
        text = manifest.read_text(encoding="utf-8")
        expect(re.search(rf"^random_seed={seed}\b", text, re.MULTILINE) is not None,
               f"{where}: manifest random_seed is not {seed}")
        settings = [line for line in text.splitlines() if line.startswith("settings=")]
        expect(len(settings) == 1, f"{where}: manifest has no single settings line")
        missing = [t for t in spec["manifest_settings"] if t not in settings[0]]
        expect(not missing, f"{where}: manifest settings lack {missing}")
        record["manifest_sha256"] = sha256(manifest)
    else:
        expect(pre, f"{where}: missing {manifest}")
        record["manifest_sha256"] = None
        record["manifest"] = PRE_PROVENANCE_NOTES["manifest"]

    if "normalization" in metrics or "normalization" in log:
        record["normalization"] = NORMALIZATION
    else:
        record["normalization"] = PRE_PROVENANCE_NOTES["normalization"]
    if any(key in metrics for key in ABLATION_KEYS):
        record["ablation"] = "none"
    else:
        expect(not re.search(r"_(frozen|matched|train_tile)", name) and not any(
                   key in log for key in ABLATION_KEYS),
               f"{where}: ablation not recorded and not excluded by name and log")
        record["ablation"] = PRE_PROVENANCE_NOTES["ablation"]
    record["source_training_name"] = (name if "source_training_name" in metrics
                                      else PRE_PROVENANCE_NOTES["source_training_name"])
    record["verified"] = (["dataset", "number_picked_peaks", "training_log_seed",
                           "training_log_settings", "training_log_name", "data_dir",
                           "artifact_root", "picked_peaks_rows"]
                          + [k for k in ("normalization", "source_training_name")
                             if k in metrics]
                          + (["ablation_and_context_mode"]
                             if any(k in metrics for k in ABLATION_KEYS) else [])
                          + (["manifest_seed", "manifest_settings"]
                             if manifest.is_file() else []))
    record["sha256"] = {"metrics.json": sha256(metrics_path), "picked_peaks": sha256(peaks[0]),
                        "training_log": sha256(log_path)}
    record["paths"] = {"metrics.json": metrics_path.relative_to(project_root).as_posix(),
                       "picked_peaks": peaks[0].relative_to(project_root).as_posix(),
                       "training_log": log_path.relative_to(project_root).as_posix()}
    return metrics, record


def main():
    args = parse_arguments()
    spec = COLLECTIONS[args.collection]
    try:
        targets = released_targets(args.data_configs)
    except (OSError, ProvenanceError) as error:
        raise SystemExit(f"provenance check failed; no table written: {error}")
    verified, failures = {}, []
    for section in spec["sections"]:
        for seed in spec["seeds"]:
            try:
                verified[section, seed] = verify_run(args.collection, spec, section, seed,
                                                     args.project_root, targets)
            except (ProvenanceError, OSError, ValueError) as error:
                failures.append(str(error))
    if failures:
        print("provenance check failed; no table written:", *failures, sep="\n  ",
              file=sys.stderr)
        raise SystemExit(1)

    rows = []
    for section, published in zip(spec["sections"], spec["published"]):
        row = {"collection": args.collection.upper(), "section": section,
               "published_mSCF1": published}
        values = []
        for seed in spec["seeds"]:
            metrics, _ = verified[section, seed]
            value = float(np.mean([float(v) for v in metrics["mixed_f1"].values()]))
            row[f"seed{seed}_mSCF1"] = value
            row[f"seed{seed}_picked_peaks"] = int(metrics["number_picked_peaks"])
            values.append(value)
        row["seed_min"], row["seed_max"] = min(values), max(values)
        row["published_within_seed_range"] = min(values) <= published <= max(values)
        rows.append(row)
    low, high = spec["published_ci"]
    means = {seed: float(np.mean([r[f"seed{seed}_mSCF1"] for r in rows])) for seed in spec["seeds"]}
    summary = {
        "collection": args.collection.upper(),
        "descriptive": "seeds reported side by side; no seed is selected",
        "published_source": "IonMorphNet msianalyzer/external/s3pl/sota_comparison.py at 640406a (investigation 19)",
        "published_mean": spec["published_mean"], "published_95ci": spec["published_ci"],
        "seed_means": {str(s): m for s, m in means.items()},
        "seed_mean_inside_published_ci": {str(s): low <= m <= high for s, m in means.items()},
        "seed_mean_minus_published": {str(s): m - spec["published_mean"] for s, m in means.items()},
        "sections": rows,
        "provenance_checks": {
            "status": "passed", "runs": len(verified), "sections": len(spec["sections"]),
            "seeds": len(spec["seeds"]),
            "with_manifest": sum(r["manifest_sha256"] is not None
                                 for _, r in verified.values()),
            "pre_provenance_runs": sum((args.collection, s) in PRE_PROVENANCE
                                       for _, s in verified),
            "data_configs_sha256": sha256(args.data_configs),
        },
        "provenance": {f"{section}/seed{seed}": record
                       for (section, seed), (_, record) in verified.items()},
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with open(args.output / "section_table.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"provenance checks passed: {len(verified)} runs")
    for seed, mean in means.items():
        print(f"seed {seed}: mean {mean:.4f} (published {spec['published_mean']}, CI {low}-{high})")


if __name__ == "__main__":
    main()
