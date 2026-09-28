#!/usr/bin/env python3
"""Verify S3PL and Spatial-msiPL CAC PCC reference-positive bin sets directly."""

import argparse
import csv
import json
from pathlib import Path

import h5py
import numpy as np

from evaluate_msipl_massnet_peaks import (
    THRESHOLDS,
    pearson_by_feature,
    true_indices_at_threshold,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--h5-root", required=True, type=Path)
    parser.add_argument("--s3pl-label-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=1024)
    args = parser.parse_args()
    if args.chunk_size < 1:
        parser.error("chunk-size must be positive")

    sections_csv = args.project_root / "results/comparisons/spatial_msipl_cac_validation/section_metrics.csv"
    with sections_csv.open("r", encoding="utf-8", newline="") as handle:
        sections = [row["dataset"] for row in csv.DictReader(handle)]
    if len(sections) != 8 or len(set(sections)) != 8:
        raise ValueError("expected eight distinct CAC sections")

    reports = []
    for section in sections:
        with h5py.File(args.h5_root / f"{section}.h5", "r") as handle:
            mz = np.asarray(handle["mzArray"], dtype=np.float64).reshape(-1)
            labels = np.asarray(handle["Class_Label"], dtype=np.int64).reshape(-1)
            data = handle["Data"]
            pixels_first = data.shape == (len(labels), len(mz))
            mz_first = data.shape == (len(mz), len(labels))
            if not pixels_first and not mz_first:
                raise ValueError(f"{section}: invalid H5 Data shape {data.shape}")
            classes = sorted(np.unique(labels).tolist())
            if classes != [0, 1, 2]:
                raise ValueError(f"{section}: unexpected class labels {classes}")
            correlation = {
                class_value: pearson_by_feature(
                    data,
                    (labels == class_value).astype(np.uint8),
                    pixels_first,
                    args.chunk_size,
                )
                for class_value in classes
            }

        s3pl_rankings = {}
        per_class = {}
        for class_value in classes:
            stem = args.s3pl_label_root / f"{section}_class{class_value}"
            ranking = np.load(str(stem) + "_ranking.npy")
            ranked_pcc = np.load(str(stem) + "_pearson_ranking.npy")
            ranked_mz = np.load(str(stem) + "_mz_ranking.npy")
            if len(ranking) != len(mz) or sorted(ranking.tolist()) != list(range(len(mz))):
                raise ValueError(f"{section}/class {class_value}: invalid S3PL ranking permutation")
            if len(ranked_pcc) != len(mz) or len(ranked_mz) != len(mz):
                raise ValueError(f"{section}/class {class_value}: label array length mismatch")
            pcc_abs_diff = np.abs(ranked_pcc - correlation[class_value][ranking])
            mz_abs_diff = np.abs(ranked_mz - mz[ranking])
            s3pl_rankings[class_value] = (ranking, ranked_pcc)
            per_class[str(class_value)] = {
                "max_pcc_absolute_difference": float(np.max(pcc_abs_diff)),
                "max_mz_absolute_difference": float(np.max(mz_abs_diff)),
            }

        threshold_reports = {}
        for threshold in THRESHOLDS:
            s3pl_true = set()
            ig_true = set()
            class_differences = {}
            for class_value in classes:
                ranking, ranked_pcc = s3pl_rankings[class_value]
                count = int(np.argmin(np.abs(ranked_pcc - threshold)))
                s3pl_class = set(ranking[:count].tolist())
                ig_class = true_indices_at_threshold(correlation[class_value], threshold)
                class_differences[str(class_value)] = len(s3pl_class ^ ig_class)
                s3pl_true.update(s3pl_class)
                ig_true.update(ig_class)
            threshold_reports[str(threshold)] = {
                "s3pl_reference_positive_bins": len(s3pl_true),
                "ig_reference_positive_bins": len(ig_true),
                "symmetric_difference_bins": len(s3pl_true ^ ig_true),
                "per_class_symmetric_difference_bins": class_differences,
            }
        reports.append({
            "section": section,
            "spectral_bins": len(mz),
            "measured_pixels": len(labels),
            "classes": per_class,
            "thresholds": threshold_reports,
        })
        print(f"{section}: max mixed reference-set difference = {max(item['symmetric_difference_bins'] for item in threshold_reports.values())}", flush=True)

    differences = sum(
        item["symmetric_difference_bins"]
        for report in reports
        for item in report["thresholds"].values()
    )
    audit = {
        "status": "exact_reference_set_match" if differences == 0 else "reference_set_mismatch",
        "purpose": "read-only post-hoc comparator; does not change peak rankings or model results",
        "source_h5_root": str(args.h5_root),
        "source_s3pl_label_root": str(args.s3pl_label_root),
        "total_mixed_symmetric_difference_bins": differences,
        "sections": reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps({"status": audit["status"], "total_mixed_symmetric_difference_bins": differences, "output": str(args.output)}, indent=2), flush=True)
    if differences:
        raise SystemExit("CAC reference-positive bin sets differ; do not treat the cross-method F1 difference as exclusive-peak-only")


if __name__ == "__main__":
    main()
