#!/usr/bin/env python3
"""Explain which frozen attention peaks change when neighbour inputs are shuffled.

This is a post-hoc, CPU-only diagnostic. The expert labels are used only for
evaluation and illustrative ion maps, never to produce either saved ranking.
"""

import argparse
import csv
import json
from pathlib import Path

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from evaluate_msipl_massnet_peaks import THRESHOLDS, true_indices_at_threshold
from evaluate_spatial_msipl_attributed_peaks import (
    load_correlations,
    read_feature_matrix,
    read_h5_metadata,
    score_indices,
    spatial_image,
)


def changed_indices(real, shuffled):
    """Return entering/leaving bins in their own ranking order."""
    real = np.asarray(real, dtype=np.int64)
    shuffled = np.asarray(shuffled, dtype=np.int64)
    if len(np.unique(real)) != len(real) or len(np.unique(shuffled)) != len(shuffled):
        raise ValueError("saved selected rankings contain duplicate bins")
    if len(real) != len(shuffled):
        raise ValueError("real and shuffled lists have different peak counts")
    real_set, shuffled_set = set(real.tolist()), set(shuffled.tolist())
    gained = [int(index) for index in shuffled if index not in real_set]
    lost = [int(index) for index in real if index not in shuffled_set]
    if len(gained) != len(lost):
        raise AssertionError("entering and leaving peak counts disagree")
    return gained, lost


def positive_sets(correlations):
    return {
        str(threshold): set().union(*(
            true_indices_at_threshold(values, threshold)
            for values in correlations.values()
        ))
        for threshold in THRESHOLDS
    }


def best_positive_pcc(index, correlations):
    best_class = max(correlations, key=lambda label: correlations[label][index])
    return best_class, float(correlations[best_class][index])


def write_changed_csv(path, gained, lost, real, shuffled, mz, correlations, reference_sets):
    real_ranks = {int(index): rank for rank, index in enumerate(real, 1)}
    shuffled_ranks = {int(index): rank for rank, index in enumerate(shuffled, 1)}
    fields = ["change", "bin_index", "mz", "real_rank", "shuffled_rank",
              "best_positive_pcc_class", "best_positive_pcc"]
    fields += [f"pcc_class_{label}" for label in sorted(correlations)]
    fields += [f"reference_positive_{threshold}" for threshold in THRESHOLDS]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for change, indices in (("gained_by_shuffle", gained), ("lost_by_shuffle", lost)):
            for index in indices:
                label, best = best_positive_pcc(index, correlations)
                row = {
                    "change": change,
                    "bin_index": index,
                    "mz": float(mz[index]),
                    "real_rank": real_ranks.get(index, ""),
                    "shuffled_rank": shuffled_ranks.get(index, ""),
                    "best_positive_pcc_class": label,
                    "best_positive_pcc": best,
                }
                row.update({f"pcc_class_{key}": float(values[index])
                            for key, values in correlations.items()})
                row.update({f"reference_positive_{threshold}": int(index in reference_sets[str(threshold)])
                            for threshold in THRESHOLDS})
                writer.writerow(row)


def save_score_plot(path, gained, lost, correlations, reference_sets, section):
    thresholds = [str(value) for value in THRESHOLDS]
    gained_hits = [len(set(gained) & reference_sets[value]) for value in thresholds]
    lost_hits = [len(set(lost) & reference_sets[value]) for value in thresholds]
    gained_pcc = [best_positive_pcc(index, correlations)[1] for index in gained]
    lost_pcc = [best_positive_pcc(index, correlations)[1] for index in lost]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    positions = np.arange(len(thresholds))
    axes[0].bar(positions - 0.18, gained_hits, width=0.36, label="Gained by shuffle")
    axes[0].bar(positions + 0.18, lost_hits, width=0.36, label="Lost by shuffle")
    axes[0].set_xticks(positions, thresholds)
    axes[0].set_xlabel("PCC threshold")
    axes[0].set_ylabel("Reference-positive changed bins")
    axes[0].legend(fontsize=8)
    axes[1].hist([gained_pcc, lost_pcc], bins=np.linspace(-1, 1, 21),
                 label=["Gained", "Lost"], alpha=0.8)
    axes[1].set_xlabel("Highest positive class PCC per changed bin")
    axes[1].set_ylabel("Bins")
    axes[1].legend(fontsize=8)
    fig.suptitle(f"{section}: post-hoc comparison of changed selected bins")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return gained_hits, lost_hits


def save_ion_maps(path, input_path, gained, lost, mz, labels, x, y, pixels_first, correlations, section):
    # Pick by each ranking's order, not by expert-mask PCC.
    chosen = [("Gained", index) for index in gained[:3]]
    chosen += [("Lost", index) for index in lost[:3]]
    if not chosen:
        return
    values = read_feature_matrix(input_path, [index for _, index in chosen], pixels_first)
    fig, axes = plt.subplots(2, 4, figsize=(14, 7), squeeze=False)
    mask = spatial_image(labels.astype(float), x, y)
    palette = matplotlib.colormaps["tab10"].copy()
    palette.set_bad("#eeeeee")
    axes[0, 0].imshow(mask, cmap=palette, interpolation="nearest")
    axes[0, 0].set_title("Expert mask (post-hoc only)")
    cmap = matplotlib.colormaps["magma"].copy()
    cmap.set_bad("#eeeeee")
    for axis, (change, index), spectrum in zip(axes.ravel()[1:], chosen, values.T):
        image = spatial_image(spectrum, x, y)
        measured = image[np.isfinite(image)]
        low, high = np.percentile(measured, [1, 99])
        if high <= low:
            high = low + 1
        scaled = np.clip((image - low) / (high - low), 0, 1)
        axis.imshow(scaled, cmap=cmap, vmin=0, vmax=1, interpolation="nearest")
        label, pcc = best_positive_pcc(index, correlations)
        axis.set_title(f"{change}: bin {index}, m/z {mz[index]:.3f}\n"
                       f"best positive PCC C{label}: {pcc:.3f}", fontsize=9)
    for axis in axes.ravel():
        axis.set_xticks([])
        axis.set_yticks([])
    for axis in axes.ravel()[len(chosen) + 1:]:
        axis.axis("off")
    fig.suptitle(f"{section}: top changed peaks by saved rank (each ion scaled separately)")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--ranking-dir", required=True, type=Path)
    parser.add_argument("--original-peaks", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=256)
    args = parser.parse_args()
    section = args.input.stem
    source_summary = json.loads((args.ranking_dir / "summary.json").read_text(encoding="utf-8"))
    if source_summary["status"] != "valid" or source_summary["section"] != section:
        raise ValueError("frozen ranking summary is invalid or belongs to another section")
    with np.load(args.ranking_dir / "rankings.npz") as saved:
        mz_saved = saved["mz"].copy()
        real = saved["real_indices"].copy()
        shuffled = saved["shuffled_indices"].copy()
    mz, labels, x, y, pixels_first = read_h5_metadata(args.input)
    if not np.array_equal(mz, mz_saved) or len(real) != source_summary["matched_count"]:
        raise ValueError("input axis or peak count differs from the frozen ranking")
    if any(np.any((indices < 0) | (indices >= len(mz))) for indices in (real, shuffled)):
        raise ValueError("saved ranking contains out-of-range bins")
    if not (len(labels) == len(x) == len(y)):
        raise ValueError("label and coordinate lengths differ")
    with args.original_peaks.open(newline="", encoding="utf-8") as handle:
        original = np.asarray([int(row["bin_index"]) for row in csv.DictReader(handle)])
    if not np.array_equal(real, original):
        raise ValueError("saved real ranking differs from the original matched peak CSV")
    gained, lost = changed_indices(real, shuffled)
    correlations = load_correlations(args.input, labels, len(mz), pixels_first, args.chunk_size)
    real_score = score_indices(real, correlations, len(mz))
    shuffled_score = score_indices(shuffled, correlations, len(mz))
    if any(abs(score["mSCF1"] - source_summary[key]["mSCF1"]) > 1e-9
           for key, score in (("real", real_score), ("shuffled", shuffled_score))):
        raise ValueError("PCC scores fail to reproduce the frozen ranking-swap summary")
    reference_sets = positive_sets(correlations)
    args.output.mkdir(parents=True, exist_ok=True)
    write_changed_csv(args.output / "changed_bins.csv", gained, lost, real, shuffled,
                      mz, correlations, reference_sets)
    gained_hits, lost_hits = save_score_plot(args.output / "changed_bin_pcc.png", gained, lost,
                                            correlations, reference_sets, section)
    save_ion_maps(args.output / "changed_ion_images.png", args.input, gained, lost,
                  mz, labels, x, y, pixels_first, correlations, section)
    result = {
        "status": "valid",
        "section": section,
        "source_ranking_summary": str(args.ranking_dir / "summary.json"),
        "selected_count_each": len(real),
        "gained_by_shuffle": len(gained),
        "lost_by_shuffle": len(lost),
        "overlap": len(real) - len(lost),
        "real_mSCF1": real_score["mSCF1"],
        "shuffled_mSCF1": shuffled_score["mSCF1"],
        "thresholds": {
            str(threshold): {
                "reference_positive_gained": gain,
                "reference_positive_lost": loss,
                "net_true_positive_change": gain - loss,
            }
            for threshold, gain, loss in zip(THRESHOLDS, gained_hits, lost_hits)
        },
        "interpretation_limit": "Post-hoc two-section, one-seed diagnostic; shuffled input may be out of distribution.",
    }
    (args.output / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
