#!/usr/bin/env python3
"""Map, consolidate, visualise, and score Spatial-msiPL attributed peaks."""

import argparse
import csv
import itertools
import json
import time
from pathlib import Path

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import (
    adjusted_rand_score,
    balanced_accuracy_score,
    normalized_mutual_info_score,
)

from evaluate_msipl_massnet_peaks import (
    THRESHOLDS,
    classification_metrics,
    nearest_unique_indices,
    pearson_by_feature,
    true_indices_at_threshold,
)
from spatial_msipl.peak_selection import (
    balanced_round_robin_rankings,
    ppm_nonmaximum_suppression,
)


METHOD_COLOURS = {
    "legacy_msipl": "#8D99AE",
    "integrated_gradients": "#457B9D",
    "first_layer_l2": "#E76F51",
}
DISPLAY_NAMES = {
    "legacy_msipl": "Legacy msiPL",
    "integrated_gradients": "GMM Integrated Gradients",
    "first_layer_l2": "First-layer L2",
}


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--attribution-dir", required=True, type=Path)
    parser.add_argument("--legacy-peaks", required=True, type=Path)
    parser.add_argument("--legacy-metrics", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--matched-count", type=int, default=530)
    parser.add_argument("--peak-tolerance-ppm", type=float, default=10.0)
    parser.add_argument("--consolidated-candidates", type=int, default=50)
    parser.add_argument("--ion-images", type=int, default=12)
    parser.add_argument("--chunk-size", type=int, default=1024)
    return parser.parse_args()


def read_h5_metadata(path):
    with h5py.File(path, "r") as handle:
        required = ("Data", "mzArray", "Class_Label", "xLocation", "yLocation")
        missing = [name for name in required if name not in handle]
        if missing:
            raise KeyError(f"missing HDF5 datasets: {missing}")
        mz = np.asarray(handle["mzArray"], dtype=np.float64).reshape(-1)
        labels = np.asarray(handle["Class_Label"], dtype=np.int64).reshape(-1)
        x = np.asarray(handle["xLocation"], dtype=np.int64).reshape(-1)
        y = np.asarray(handle["yLocation"], dtype=np.int64).reshape(-1)
        shape = tuple(handle["Data"].shape)
    pixels_first = shape == (len(labels), len(mz))
    mz_first = shape == (len(mz), len(labels))
    if not pixels_first and not mz_first:
        raise ValueError(f"cannot orient Data shape {shape}")
    return mz, labels, x, y, pixels_first


def read_feature_matrix(path, indices, pixels_first):
    indices = np.asarray(indices, dtype=np.int64)
    order = np.argsort(indices)
    sorted_indices = indices[order]
    with h5py.File(path, "r") as handle:
        data = handle["Data"]
        if pixels_first:
            sorted_values = np.asarray(data[:, sorted_indices], dtype=np.float32)
        else:
            sorted_values = np.asarray(data[sorted_indices, :], dtype=np.float32).T
    return sorted_values[:, np.argsort(order)]


def load_correlations(path, labels, mz_count, pixels_first, chunk_size):
    correlations = {}
    with h5py.File(path, "r") as handle:
        data = handle["Data"]
        for value in sorted(np.unique(labels).tolist()):
            correlations[int(value)] = pearson_by_feature(
                data,
                (labels == value).astype(np.uint8),
                pixels_first,
                chunk_size,
            )
    if any(len(values) != mz_count for values in correlations.values()):
        raise RuntimeError("PCC output length does not match the m/z axis")
    return correlations


def score_indices(indices, correlations, total_features):
    selected = set(np.asarray(indices, dtype=np.int64).tolist())
    thresholds = {}
    mixed_f1 = []
    for threshold in THRESHOLDS:
        class_true = {
            value: true_indices_at_threshold(values, threshold)
            for value, values in correlations.items()
        }
        mixed_true = set().union(*class_true.values())
        mixed = classification_metrics(selected, mixed_true, total_features)
        mixed_f1.append(mixed["F1"])
        thresholds[str(threshold)] = {
            "mixed_classes": mixed,
            "true_bins_mixed": len(mixed_true),
            "class_metrics": {
                str(value): classification_metrics(
                    selected, class_true[value], total_features
                )
                for value in sorted(class_true)
            },
        }
    return {
        "selected_bins": len(selected),
        "threshold_results": thresholds,
        "mixed_f1": {
            str(threshold): float(score)
            for threshold, score in zip(THRESHOLDS, mixed_f1)
        },
        "mSCF1": float(np.mean(mixed_f1)),
    }


def best_component_mapping(components, expert_labels):
    component_values = sorted(np.unique(components).tolist())
    label_values = sorted(np.unique(expert_labels).tolist())
    if len(component_values) != len(label_values):
        raise ValueError("component and expert-label counts must match")
    confusion = np.zeros((len(component_values), len(label_values)), dtype=np.int64)
    for row, component in enumerate(component_values):
        for column, label in enumerate(label_values):
            confusion[row, column] = np.count_nonzero(
                (components == component) & (expert_labels == label)
            )
    best = None
    for permutation in itertools.permutations(label_values):
        mapping = dict(zip(component_values, permutation))
        mapped = np.asarray([mapping[int(value)] for value in components])
        accuracy = float(np.mean(mapped == expert_labels))
        if best is None or accuracy > best["accuracy"]:
            best = {"mapping": mapping, "mapped": mapped, "accuracy": accuracy}
    best["confusion_rows_components_columns_labels"] = confusion.tolist()
    best["balanced_accuracy"] = float(
        balanced_accuracy_score(expert_labels, best["mapped"])
    )
    best["adjusted_rand_index"] = float(
        adjusted_rand_score(expert_labels, components)
    )
    best["normalized_mutual_information"] = float(
        normalized_mutual_info_score(expert_labels, components)
    )
    return best


def spatial_image(values, x, y):
    image = np.full((int(y.max()), int(x.max())), np.nan)
    image[y - 1, x - 1] = values
    return image


def categorical_colormap(class_count):
    base = ("#2A9D8F", "#E76F51", "#6D597A", "#457B9D", "#E9C46A")
    if class_count <= len(base):
        colours = base[:class_count]
    else:
        colours = matplotlib.colormaps["tab20"](
            np.linspace(0, 1, class_count)
        )
    result = matplotlib.colors.ListedColormap(colours)
    result.set_bad("#ECECEC")
    return result


def save_cluster_mapping(mapping, expert, components, posterior, x, y, output):
    mapped = mapping["mapped"]
    fig, axes = plt.subplots(1, 4, figsize=(20, 4.8))
    class_count = len(np.unique(expert))
    categorical = categorical_colormap(class_count)
    error_cmap = matplotlib.colors.ListedColormap(["#F4F1DE", "#9B2226"])
    error_cmap.set_bad("#ECECEC")
    confidence_cmap = matplotlib.colormaps["viridis"].copy()
    confidence_cmap.set_bad("#ECECEC")
    axes[0].imshow(
        spatial_image(expert, x, y),
        cmap=categorical,
        vmin=-0.5,
        vmax=class_count - 0.5,
    )
    axes[0].set_title("Expert mask")
    axes[1].imshow(
        spatial_image(mapped, x, y),
        cmap=categorical,
        vmin=-0.5,
        vmax=class_count - 0.5,
    )
    axes[1].set_title("Mapped GMM clusters")
    axes[2].imshow(
        spatial_image((mapped != expert).astype(int), x, y),
        cmap=error_cmap,
        vmin=0,
        vmax=1,
    )
    axes[2].set_title("Mismatch (dark red)")
    shown = axes[3].imshow(
        spatial_image(posterior, x, y),
        cmap=confidence_cmap,
        vmin=1.0 / class_count,
        vmax=1.0,
    )
    axes[3].set_title("Assigned posterior")
    fig.colorbar(shown, ax=axes[3], fraction=0.046)
    for axis in axes:
        axis.set_xlabel("X")
        axis.set_ylabel("Y")
        axis.set_aspect("equal")
    fig.suptitle("Label-free GMM mapped to the expert mask", fontsize=15)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_mscf1_plot(methods, matched_count, output):
    labels = [str(value) for value in THRESHOLDS] + ["mSCF1"]
    x = np.arange(len(labels))
    width = 0.25
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for offset, method in enumerate(
        ("legacy_msipl", "integrated_gradients", "first_layer_l2")
    ):
        result = methods[method]
        values = [result["mixed_f1"][str(value)] for value in THRESHOLDS]
        values.append(result["mSCF1"])
        ax.bar(
            x + (offset - 1) * width,
            values,
            width,
            label=DISPLAY_NAMES[method],
            color=METHOD_COLOURS[method],
        )
    ax.set_xticks(x, labels)
    ax.set_xlabel("PCC threshold / mean")
    ax.set_ylabel("F1 (higher is better)")
    ax.set_ylim(0, 1)
    ax.set_title(f"Matched {matched_count}-bin peak evaluation")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def robust_image(values, x, y):
    image = spatial_image(values, x, y)
    measured = image[np.isfinite(image)]
    low, high = np.percentile(measured, [1, 99])
    if high <= low:
        high = low + 1.0
    return np.clip((image - low) / (high - low), 0, 1)


def save_ion_images(feature_values, indices, mz, correlations, sources, x, y, output):
    columns = 4
    rows = int(np.ceil(len(indices) / columns))
    fig, axes = plt.subplots(rows, columns, figsize=(16, 4 * rows), squeeze=False)
    cmap = matplotlib.colormaps["magma"].copy()
    cmap.set_bad("#ECECEC")
    for rank, (axis, index) in enumerate(zip(axes.ravel(), indices), start=1):
        pcc_values = {value: correlations[value][index] for value in correlations}
        strongest_class = max(pcc_values, key=lambda value: abs(pcc_values[value]))
        axis.imshow(
            robust_image(feature_values[:, rank - 1], x, y),
            cmap=cmap,
            vmin=0,
            vmax=1,
            interpolation="nearest",
        )
        axis.set_title(
            f"#{rank}  m/z {mz[index]:.4f}\n"
            f"source C{sources[rank - 1]}, PCC class {strongest_class}: "
            f"{pcc_values[strongest_class]:.3f}"
        )
        axis.set_xlabel("X")
        axis.set_ylabel("Y")
        axis.set_aspect("equal")
    for axis in axes.ravel()[len(indices):]:
        axis.axis("off")
    fig.suptitle("Top consolidated nonlinear-attribution ion images", fontsize=16)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def write_selected_csv(path, indices, mz, scores, correlations, sources=None):
    with path.open("w", newline="", encoding="utf-8") as handle:
        fields = ["rank", "bin_index", "mz", "score"]
        if sources is not None:
            fields.append("source_component")
        fields.extend([f"pcc_class_{value}" for value in sorted(correlations)])
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for rank, index in enumerate(indices, start=1):
            row = {
                "rank": rank,
                "bin_index": int(index),
                "mz": float(mz[index]),
                "score": float(scores[index]),
            }
            if sources is not None:
                row["source_component"] = int(sources[rank - 1])
            for value in sorted(correlations):
                row[f"pcc_class_{value}"] = float(correlations[value][index])
            writer.writerow(row)


def main():
    args = parse_arguments()
    if args.matched_count < 1 or args.consolidated_candidates < 1:
        raise ValueError("candidate counts must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    mz, raw_labels, x, y, pixels_first = read_h5_metadata(args.input)
    expert = raw_labels - raw_labels.min()
    attribution = np.load(args.attribution_dir / "attributions.npz")
    coordinate_gmm = np.load(args.attribution_dir / "coordinates_and_gmm.npz")
    if not np.array_equal(x, coordinate_gmm["x"]) or not np.array_equal(
        y, coordinate_gmm["y"]
    ):
        raise ValueError("attribution coordinates do not match the HDF5 input")
    components = coordinate_gmm["component"].astype(np.int64)
    posterior = coordinate_gmm["assigned_posterior"]
    mapping = best_component_mapping(components, expert)

    component_values = sorted(np.unique(components).tolist())
    component_scores = {
        component: attribution[
            f"component_{component}_combined_absolute_mean"
        ].astype(np.float64)
        for component in component_values
    }
    rankings = {
        component: np.argsort(scores)[::-1].copy()
        for component, scores in component_scores.items()
    }
    full_balanced, full_sources = balanced_round_robin_rankings(
        rankings, len(mz)
    )
    ig_indices = full_balanced[: args.matched_count]
    ig_sources = full_sources[: args.matched_count]
    normalized_scores = {
        component: scores / max(float(scores.max()), np.finfo(float).eps)
        for component, scores in component_scores.items()
    }
    ig_score = np.maximum.reduce(
        [normalized_scores[component] for component in component_values]
    )
    first_layer_score = attribution["first_layer_combined_l2"].astype(np.float64)
    l2_indices = np.argsort(first_layer_score)[::-1][: args.matched_count].copy()

    legacy_values = np.genfromtxt(args.legacy_peaks, delimiter=",", names=True)
    legacy_mz = np.asarray(legacy_values[legacy_values.dtype.names[0]]).reshape(-1)
    legacy_indices = nearest_unique_indices(mz, legacy_mz)
    if len(legacy_indices) != args.matched_count:
        raise ValueError(
            f"legacy peak list has {len(legacy_indices)} unique bins, expected "
            f"{args.matched_count}"
        )

    correlations = load_correlations(
        args.input, raw_labels, len(mz), pixels_first, args.chunk_size
    )
    methods = {
        "integrated_gradients": score_indices(
            ig_indices, correlations, len(mz)
        ),
        "first_layer_l2": score_indices(l2_indices, correlations, len(mz)),
    }
    legacy_metrics = json.loads(args.legacy_metrics.read_text(encoding="utf-8"))
    methods["legacy_msipl"] = {
        "selected_bins": int(legacy_metrics["unique_nearest_bins"]),
        "mixed_f1": legacy_metrics["mixed_f1"],
        "mSCF1": float(legacy_metrics["mSCF1"]),
        "threshold_results": legacy_metrics["threshold_results"],
    }

    consolidated_indices = ppm_nonmaximum_suppression(
        full_balanced,
        mz,
        args.peak_tolerance_ppm,
        count=args.consolidated_candidates,
    )
    source_by_index = {
        int(index): int(source) for index, source in zip(full_balanced, full_sources)
    }
    consolidated_sources = np.asarray(
        [source_by_index[int(index)] for index in consolidated_indices],
        dtype=np.int64,
    )
    l2_consolidated = ppm_nonmaximum_suppression(
        np.argsort(first_layer_score)[::-1].copy(),
        mz,
        args.peak_tolerance_ppm,
        count=args.consolidated_candidates,
    )

    write_selected_csv(
        args.output / f"ig_matched_{args.matched_count}_bins.csv",
        ig_indices,
        mz,
        ig_score,
        correlations,
        sources=ig_sources,
    )
    write_selected_csv(
        args.output / f"first_layer_l2_matched_{args.matched_count}_bins.csv",
        l2_indices,
        mz,
        first_layer_score,
        correlations,
    )
    write_selected_csv(
        args.output / "ig_consolidated_candidates.csv",
        consolidated_indices,
        mz,
        ig_score,
        correlations,
        sources=consolidated_sources,
    )
    write_selected_csv(
        args.output / "first_layer_l2_consolidated_candidates.csv",
        l2_consolidated,
        mz,
        first_layer_score,
        correlations,
    )

    ion_indices = consolidated_indices[: args.ion_images]
    ion_sources = consolidated_sources[: args.ion_images]
    ion_values = read_feature_matrix(args.input, ion_indices, pixels_first)
    save_cluster_mapping(
        mapping,
        expert,
        components,
        posterior,
        x,
        y,
        args.output / "gmm_expert_mapping.png",
    )
    save_mscf1_plot(
        methods,
        args.matched_count,
        args.output / "matched_mscf1_comparison.png",
    )
    save_ion_images(
        ion_values,
        ion_indices,
        mz,
        correlations,
        ion_sources,
        x,
        y,
        args.output / "top_ig_ion_images.png",
    )

    overlap = {}
    sets = {
        "legacy_msipl": set(legacy_indices.tolist()),
        "integrated_gradients": set(ig_indices.tolist()),
        "first_layer_l2": set(l2_indices.tolist()),
    }
    for left, right in itertools.combinations(sorted(sets), 2):
        intersection = len(sets[left] & sets[right])
        union = len(sets[left] | sets[right])
        overlap[f"{left}__{right}"] = {
            "intersection": intersection,
            "jaccard": float(intersection / union),
        }

    summary = {
        "evaluation_version": 1,
        "status": "complete",
        "dataset": args.input.stem,
        "scope": "section attribution and matched-count peak evaluation",
        "pixels": int(len(x)),
        "spectral_bins": int(len(mz)),
        "cluster_mapping": {
            "component_to_analysis_label": {
                str(key): int(value) for key, value in mapping["mapping"].items()
            },
            "analysis_label_names": {
                str(value): f"class_{value}"
                for value in sorted(np.unique(expert).tolist())
            },
            "confusion_rows_components_columns_labels": mapping[
                "confusion_rows_components_columns_labels"
            ],
            "accuracy": mapping["accuracy"],
            "balanced_accuracy": mapping["balanced_accuracy"],
            "adjusted_rand_index": mapping["adjusted_rand_index"],
            "normalized_mutual_information": mapping[
                "normalized_mutual_information"
            ],
            "mapping_use": "evaluation and display only; expert labels did not fit the GMM or rank peaks",
        },
        "matched_peak_evaluation": {
            "count": args.matched_count,
            "selection": {
                "integrated_gradients": "deterministic component-balanced round robin over combined absolute IG rankings",
                "first_layer_l2": "descending combined central-plus-context first-layer L2",
                "legacy_msipl": "existing LearnPeaks output",
            },
            "pcc_thresholds": list(THRESHOLDS),
            "methods": methods,
            "overlap": overlap,
        },
        "consolidation": {
            "method": "greedy non-maximum suppression in descending attribution order",
            "tolerance_ppm": args.peak_tolerance_ppm,
            "reported_candidates_per_method": args.consolidated_candidates,
            "purpose": "interpretation and ion images only; matched mSCF1 uses raw bins",
        },
        "runtime_seconds": time.perf_counter() - started,
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
