#!/usr/bin/env python3
"""Post-hoc CAC S3PL/IG diagnostics from frozen, matched-count results.

The local analysis needs no MSI data. With --h5-root it additionally draws raw
ion images for the highest-ranked peaks unique to each method; no model runs.
"""

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS = ("0.3", "0.4", "0.5", "0.6")


def rows(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def ranked_mz(path, field):
    values = [float(row[field]) for row in rows(path)]
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate selected m/z values: {path}")
    return values


def s3pl_paths(root, section, count):
    candidates = list((root / "results/baselines/s3pl").glob(
        f"{section}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9_matched_{count}peaks"
    ))
    if len(candidates) != 1:
        raise ValueError(f"expected one matched S3PL result for {section}/{count}, found {len(candidates)}")
    directory = candidates[0]
    return directory / "metrics.json", directory / f"picked_peaks_{section}_256peaks_z_patchsize_9.csv"


def collect(root):
    comparison = rows(root / "results/comparisons/spatial_msipl_cac_validation/section_metrics.csv")
    if len(comparison) != 8:
        raise ValueError(f"expected eight CAC sections, found {len(comparison)}")
    records = []
    for row in comparison:
        section = row["dataset"]
        count = int(row["matched_peak_count"])
        s3pl_metrics_path, s3pl_peaks_path = s3pl_paths(root, section, count)
        ig_root = root / "results/experiments/spatial_msipl_cac_attributed_peak_evaluation" / f"{section}_seed1/uniform_mean"
        ig_metrics = load_json(ig_root / "summary.json")["matched_peak_evaluation"]["methods"]["integrated_gradients"]
        s3pl_metrics = load_json(s3pl_metrics_path)
        ig_ranked = ranked_mz(ig_root / f"ig_matched_{count}_bins.csv", "mz")
        s3pl_ranked = ranked_mz(s3pl_peaks_path, "0")
        if len(ig_ranked) != count or len(s3pl_ranked) != count:
            raise ValueError(f"{section}: selected-list size does not equal matched count")
        ig_set, s3pl_set = set(ig_ranked), set(s3pl_ranked)
        shared = len(ig_set & s3pl_set)
        ig_score = float(ig_metrics["mSCF1"])
        s3pl_score = float(s3pl_metrics["mSCF1"])
        if abs(ig_score - float(row["spatial_ig_mscf1"])) > 1e-9 or abs(s3pl_score - float(row["s3pl_mscf1"])) > 1e-9:
            raise ValueError(f"{section}: aggregate score disagrees with source metrics")
        thresholds = {}
        for threshold in THRESHOLDS:
            ig_f1 = float(ig_metrics["mixed_f1"][threshold])
            s3pl_f1 = float(s3pl_metrics["mixed_f1"][threshold])
            thresholds[threshold] = {"ig_f1": ig_f1, "s3pl_f1": s3pl_f1, "s3pl_minus_ig": s3pl_f1 - ig_f1}
        records.append({
            "section": section,
            "matched_peaks": count,
            "ig_mscf1": ig_score,
            "s3pl_mscf1": s3pl_score,
            "s3pl_minus_ig_mscf1": s3pl_score - ig_score,
            "shared_peak_mz": shared,
            "shared_fraction_of_each_list": shared / count,
            "jaccard_mz": shared / (2 * count - shared),
            "s3pl_exclusive_mz_by_rank": [value for value in s3pl_ranked if value not in ig_set],
            "ig_exclusive_mz_by_rank": [value for value in ig_ranked if value not in s3pl_set],
            "thresholds": thresholds,
        })
    return sorted(records, key=lambda record: int(record["section"].replace("TopL", "")))


def plot_scores(records, output):
    sections = [record["section"] for record in records]
    deltas = [record["s3pl_minus_ig_mscf1"] for record in records]
    figure, (left, right) = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
    x = np.arange(len(records))
    left.bar(x, deltas, color=["#4c78a8" if value > 0 else "#f28e2b" for value in deltas])
    left.axhline(0, color="0.25", linewidth=1)
    left.set_xticks(x, sections, rotation=45, ha="right")
    left.set_ylabel("S3PL − uniform IG mSCF1")
    left.set_title("Matched-count difference by CAC section")
    for index, value in enumerate(deltas):
        left.annotate(f"{value:+.3f}", (index, value), xytext=(0, 3 if value >= 0 else -3), textcoords="offset points", ha="center", va="bottom" if value >= 0 else "top", fontsize=8)

    mean_deltas = [np.mean([record["thresholds"][threshold]["s3pl_minus_ig"] for record in records]) for threshold in THRESHOLDS]
    right.axhline(0, color="0.25", linewidth=1)
    for record in records:
        right.plot(range(4), [record["thresholds"][threshold]["s3pl_minus_ig"] for threshold in THRESHOLDS], color="0.7", alpha=0.65, linewidth=1)
    right.plot(range(4), mean_deltas, color="#4c78a8", marker="o", linewidth=2.5, label="Mean across 8 sections")
    right.set_xticks(range(4), THRESHOLDS)
    right.set_xlabel("PCC threshold")
    right.set_ylabel("S3PL − uniform IG mixed F1")
    right.set_title("Where the quality difference occurs")
    right.legend(frameon=False)
    figure.savefig(output, dpi=180)
    plt.close(figure)


def plot_overlap(records, output):
    figure, axis = plt.subplots(figsize=(8.5, 4.3), constrained_layout=True)
    x = np.arange(len(records))
    shared = [record["shared_fraction_of_each_list"] for record in records]
    axis.bar(x, shared, color="#4c78a8")
    axis.set_xticks(x, [record["section"] for record in records], rotation=45, ha="right")
    axis.set_ylabel("Fraction of selected m/z values shared")
    axis.set_ylim(0, 1)
    axis.set_title("S3PL versus uniform IG: matched-count peak-set overlap")
    for index, value in enumerate(shared):
        axis.text(index, value + 0.02, f"{value:.0%}", ha="center", va="bottom", fontsize=8)
    figure.savefig(output, dpi=180)
    plt.close(figure)


def h5_ion_figure(record, h5_root, output):
    import h5py
    from matplotlib.colors import BoundaryNorm, ListedColormap

    section = record["section"]
    with h5py.File(h5_root / f"{section}.h5", "r") as handle:
        mz_axis = np.asarray(handle["mzArray"], dtype=float).reshape(-1)
        x = np.asarray(handle["xLocation"], dtype=int).reshape(-1) - 1
        y = np.asarray(handle["yLocation"], dtype=int).reshape(-1) - 1
        labels = np.asarray(handle["Class_Label"], dtype=int).reshape(-1)
        if len(set(zip(x.tolist(), y.tolist()))) != len(x):
            raise ValueError(f"{section}: duplicate measured coordinates")
        if set(np.unique(labels)) != {0, 1, 2}:
            raise ValueError(f"{section}: expected labels 0, 1, 2")
        shape = (int(y.max()) + 1, int(x.max()) + 1)
        mask = np.full(shape, np.nan)
        mask[y, x] = labels
        figure = plt.figure(figsize=(13, 5.5), constrained_layout=True)
        grid = figure.add_gridspec(2, 4, width_ratios=[1.1, 1, 1, 1])
        mask_axis = figure.add_subplot(grid[:, 0])
        cmap = ListedColormap(["#4c78a8", "#f28e2b", "#54a24b"])
        cmap.set_bad("#dddddd")
        ion_cmap = plt.get_cmap("magma").copy()
        ion_cmap.set_bad("#dddddd")
        mask_axis.imshow(np.ma.masked_invalid(mask), cmap=cmap, norm=BoundaryNorm([-0.5, 0.5, 1.5, 2.5], 3), interpolation="nearest")
        mask_axis.set_title("Expert classes\n(measured pixels)")
        mask_axis.set_xticks([])
        mask_axis.set_yticks([])
        for row_number, (method, candidates) in enumerate((("S3PL-only", record["s3pl_exclusive_mz_by_rank"]), ("IG-only", record["ig_exclusive_mz_by_rank"]))):
            if len(candidates) < 3:
                raise ValueError(f"{section}: fewer than three {method} peaks for ion images")
            for column, value in enumerate(candidates[:3], start=1):
                matches = np.flatnonzero(np.isclose(mz_axis, value, atol=1e-4, rtol=0))
                if len(matches) != 1:
                    raise ValueError(f"{section}: m/z {value} does not map uniquely to H5 axis")
                index = int(matches[0])
                data = handle["Data"]
                if data.shape == (len(x), len(mz_axis)):
                    intensities = np.asarray(data[:, index], dtype=float)
                elif data.shape == (len(mz_axis), len(x)):
                    intensities = np.asarray(data[index, :], dtype=float)
                else:
                    raise ValueError(f"{section}: unexpected Data shape {data.shape}")
                image = np.full(shape, np.nan)
                image[y, x] = np.log1p(np.maximum(intensities, 0))
                axis = figure.add_subplot(grid[row_number, column])
                axis.imshow(np.ma.masked_invalid(image), cmap=ion_cmap, vmin=0, vmax=max(float(np.nanpercentile(image, 99)), 1e-6), interpolation="nearest")
                axis.set_title(f"{method} #{column}\nm/z {value:.3f}")
                axis.set_xticks([])
                axis.set_yticks([])
        figure.suptitle(f"{section}: highest-ranked exclusive peaks (raw log1p ion images; individual colour scales)")
        figure.savefig(output, dpi=170)
        plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "results/comparisons/s3pl_cac_gap_diagnostics")
    parser.add_argument("--h5-root", type=Path)
    parser.add_argument("--ion-sections", nargs="+", default=["360TopL", "520TopL"])
    args = parser.parse_args()
    records = collect(args.project_root)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "diagnostics.json").write_text(json.dumps({"source": "frozen matched-count CAC results", "sections": records}, indent=2), encoding="utf-8")
    plot_scores(records, args.output / "cac_s3pl_ig_thresholds.png")
    plot_overlap(records, args.output / "cac_s3pl_ig_peak_overlap.png")
    if args.h5_root is not None:
        by_section = {record["section"]: record for record in records}
        for section in args.ion_sections:
            h5_ion_figure(by_section[section], args.h5_root, args.output / f"{section}_exclusive_ion_images.png")
    print(json.dumps({"output": str(args.output), "sections": len(records), "ion_sections": args.ion_sections if args.h5_root else []}, indent=2))


if __name__ == "__main__":
    main()
