#!/usr/bin/env python3
"""Visualise MassNet GBM HDF5 sections and expert-derived masks."""

import argparse
import json
from pathlib import Path

import h5py
import numpy as np

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch


EXPECTED_FILES = (
    "GBM108_negative.h5",
    "GBM108_positive.h5",
    "GBM12_1.h5",
    "GBM12_2.h5",
    "GBM22_1.h5",
    "GBM22_2.h5",
    "GBM39_1.h5",
    "GBM39_2.h5",
)

DEFAULT_ION_TARGETS = (
    394.1757,
    438.2978,
    480.9211,
    529.9846,
    558.2953,
    616.1700,
)

NORMAL_COLOUR = "#2A9D8F"
TUMOUR_COLOUR = "#E76F51"
UNMEASURED_COLOUR = "#ECECEC"
COVERAGE_COLOUR = "#264653"
MASK_CMAP = ListedColormap([NORMAL_COLOUR, TUMOUR_COLOUR])


def display_cmap(name):
    cmap = matplotlib.colormaps[name].copy()
    cmap.set_bad(UNMEASURED_COLOUR)
    return cmap


def spatial_image(values, x, y, shape):
    image = np.full(shape, np.nan, dtype=np.float64)
    image[y - 1, x - 1] = values
    return image


def robust_normalise(image, low=1.0, high=99.0):
    finite = image[np.isfinite(image)]
    if finite.size == 0:
        return np.zeros_like(image)

    lower, upper = np.percentile(finite, [low, high])
    if upper <= lower:
        result = np.zeros_like(image)
        result[np.isfinite(image)] = finite
        return result

    return np.clip((image - lower) / (upper - lower), 0.0, 1.0)


def load_metadata(path):
    with h5py.File(path, "r") as handle:
        required = ("Data", "mzArray", "Class_Label", "xLocation", "yLocation")
        missing = [name for name in required if name not in handle]
        if missing:
            raise KeyError(f"{path.name}: missing datasets {missing}")

        data_shape = tuple(handle["Data"].shape)
        mz = np.asarray(handle["mzArray"], dtype=np.float64).reshape(-1)
        raw_labels = np.asarray(handle["Class_Label"]).reshape(-1)
        x = np.asarray(handle["xLocation"], dtype=np.int32).reshape(-1)
        y = np.asarray(handle["yLocation"], dtype=np.int32).reshape(-1)

    n_pixels = len(x)
    n_mz = len(mz)
    if not (len(y) == len(raw_labels) == n_pixels):
        raise ValueError(f"{path.name}: coordinate and label lengths differ")
    if data_shape not in ((n_mz, n_pixels), (n_pixels, n_mz)):
        raise ValueError(
            f"{path.name}: unexpected Data shape {data_shape}; "
            f"expected {(n_mz, n_pixels)} or {(n_pixels, n_mz)}"
        )
    if set(np.unique(raw_labels).astype(int).tolist()) != {1, 2}:
        raise ValueError(f"{path.name}: expected MassNet labels 1 and 2")
    if np.any(x < 1) or np.any(y < 1):
        raise ValueError(f"{path.name}: coordinates must be one-based")

    return data_shape, mz, raw_labels.astype(np.uint8), x, y


def stream_spectral_summaries(path, data_shape, n_mz, n_pixels, ion_indices, chunk_size):
    tic = np.zeros(n_pixels, dtype=np.float64)
    base_peak = np.full(n_pixels, -np.inf, dtype=np.float64)
    ion_values = {}

    with h5py.File(path, "r") as handle:
        data = handle["Data"]
        mz_first = data_shape == (n_mz, n_pixels)

        for start in range(0, n_mz, chunk_size):
            stop = min(start + chunk_size, n_mz)
            print(f"  spectral bins {start:,}-{stop - 1:,} / {n_mz:,}", flush=True)

            if mz_first:
                block = np.asarray(data[start:stop, :], dtype=np.float64)
                tic += np.sum(block, axis=0)
                base_peak = np.maximum(base_peak, np.max(block, axis=0))
            else:
                block = np.asarray(data[:, start:stop], dtype=np.float64)
                tic += np.sum(block, axis=1)
                base_peak = np.maximum(base_peak, np.max(block, axis=1))

        for index in ion_indices:
            if mz_first:
                ion_values[index] = np.asarray(data[index, :], dtype=np.float64)
            else:
                ion_values[index] = np.asarray(data[:, index], dtype=np.float64)

    return tic, base_peak, ion_values


def load_and_validate_masks(data_dir, dataset, x, y, shape, raw_labels):
    mask_path = data_dir / "masks" / f"{dataset}_mask.npy"
    coverage_path = data_dir / "masks" / "audit" / f"{dataset}_coverage.npy"
    if not mask_path.is_file():
        raise FileNotFoundError(f"Mask not found: {mask_path}")
    if not coverage_path.is_file():
        raise FileNotFoundError(f"Coverage audit not found: {coverage_path}")

    mask = np.load(mask_path)
    coverage = np.load(coverage_path).astype(bool)
    if mask.shape != shape or coverage.shape != shape:
        raise ValueError(
            f"{dataset}: expected mask/coverage shape {shape}, "
            f"found {mask.shape}/{coverage.shape}"
        )

    coordinate_coverage = np.zeros(shape, dtype=bool)
    coordinate_coverage[y - 1, x - 1] = True
    if not np.array_equal(coverage, coordinate_coverage):
        raise ValueError(f"{dataset}: saved coverage does not match HDF5 coordinates")

    expected_labels = raw_labels - 1
    if not np.array_equal(mask[y - 1, x - 1], expected_labels):
        raise ValueError(f"{dataset}: mask values do not match HDF5 Class_Label values")

    return mask.astype(np.uint8), coverage


def save_scalar_image(image, path, title, cmap="magma"):
    fig, ax = plt.subplots(figsize=(7, 6))
    shown = ax.imshow(
        robust_normalise(image),
        cmap=display_cmap(cmap),
        interpolation="nearest",
        vmin=0,
        vmax=1,
    )
    ax.set_title(title, fontsize=13, pad=10)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_aspect("equal")
    fig.colorbar(shown, ax=ax, label="Robustly scaled intensity")
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def masked_segmentation(mask, coverage):
    return np.ma.masked_where(~coverage, mask)


def mask_legend(include_unmeasured=True):
    handles = [
        Patch(facecolor=NORMAL_COLOUR, label="0: Normal"),
        Patch(facecolor=TUMOUR_COLOUR, label="1: Tumour"),
    ]
    if include_unmeasured:
        handles.append(Patch(facecolor=UNMEASURED_COLOUR, label="Unmeasured"))
    return handles


def save_mask(mask, coverage, path, title):
    cmap = MASK_CMAP.copy()
    cmap.set_bad(UNMEASURED_COLOUR)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.imshow(
        masked_segmentation(mask, coverage),
        cmap=cmap,
        interpolation="nearest",
        vmin=0,
        vmax=1,
    )
    ax.set_title(title, fontsize=13, pad=10)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_aspect("equal")
    ax.legend(handles=mask_legend(), loc="upper right", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_coverage(coverage, path, title):
    cmap = ListedColormap([UNMEASURED_COLOUR, COVERAGE_COLOUR])
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.imshow(coverage, cmap=cmap, interpolation="nearest", vmin=0, vmax=1)
    ax.set_title(title, fontsize=13, pad=10)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_aspect("equal")
    ax.legend(
        handles=[
            Patch(facecolor=UNMEASURED_COLOUR, label="No MSI spectrum"),
            Patch(facecolor=COVERAGE_COLOUR, label="MSI spectrum"),
        ],
        loc="upper right",
        framealpha=0.9,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_overlay(tic_image, mask, coverage, path, title):
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.imshow(
        robust_normalise(tic_image),
        cmap=display_cmap("gray"),
        interpolation="nearest",
        vmin=0,
        vmax=1,
    )
    ax.imshow(
        masked_segmentation(mask, coverage),
        cmap=MASK_CMAP,
        interpolation="nearest",
        alpha=0.45,
        vmin=0,
        vmax=1,
    )
    ax.set_title(title, fontsize=13, pad=10)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_aspect("equal")
    ax.legend(handles=mask_legend(include_unmeasured=False), loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_class_distribution(normal_count, tumour_count, path, title):
    counts = np.array([normal_count, tumour_count])
    percentages = 100.0 * counts / counts.sum()
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(
        ["Normal", "Tumour"],
        counts,
        color=[NORMAL_COLOUR, TUMOUR_COLOUR],
    )
    for bar, count, percentage in zip(bars, counts, percentages):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{count:,}\n({percentage:.1f}%)",
            ha="center",
            va="bottom",
        )
    ax.set_title(title)
    ax.set_ylabel("Measured pixels")
    ax.set_ylim(0, max(counts) * 1.18)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_section_overview(section, output_path):
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    tic = section["tic"]
    base_peak = section["base_peak"]
    mask = section["mask"]
    coverage = section["coverage"]

    axes[0, 0].imshow(robust_normalise(tic), cmap=display_cmap("magma"))
    axes[0, 0].set_title("Total ion current")
    axes[0, 1].imshow(robust_normalise(base_peak), cmap=display_cmap("magma"))
    axes[0, 1].set_title("Base-peak intensity")

    mask_cmap = MASK_CMAP.copy()
    mask_cmap.set_bad(UNMEASURED_COLOUR)
    axes[0, 2].imshow(masked_segmentation(mask, coverage), cmap=mask_cmap, vmin=0, vmax=1)
    axes[0, 2].set_title("Expert-derived mask")

    axes[1, 0].imshow(
        coverage,
        cmap=ListedColormap([UNMEASURED_COLOUR, COVERAGE_COLOUR]),
        vmin=0,
        vmax=1,
    )
    axes[1, 0].set_title("MSI coverage")
    axes[1, 1].imshow(robust_normalise(tic), cmap=display_cmap("gray"), vmin=0, vmax=1)
    axes[1, 1].imshow(
        masked_segmentation(mask, coverage),
        cmap=MASK_CMAP,
        alpha=0.45,
        vmin=0,
        vmax=1,
    )
    axes[1, 1].set_title("TIC + mask")

    counts = section["class_counts"]
    axes[1, 2].bar(
        ["Normal", "Tumour"],
        [counts["normal"], counts["tumour"]],
        color=[NORMAL_COLOUR, TUMOUR_COLOUR],
    )
    axes[1, 2].set_title("Measured class counts")
    axes[1, 2].set_ylabel("Pixels")

    for ax in axes.ravel()[:5]:
        ax.set_aspect("equal")
        ax.set_xlabel("X")
        ax.set_ylabel("Y")

    fig.suptitle(f"{section['dataset']} — MassNet GBM", fontsize=18)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_dataset_overview(sections, output_dir, key, title, filename):
    fig, axes = plt.subplots(2, 4, figsize=(18, 9))
    axes = axes.ravel()
    for ax, section in zip(axes, sections):
        if key == "mask":
            cmap = MASK_CMAP.copy()
            cmap.set_bad(UNMEASURED_COLOUR)
            image = masked_segmentation(section["mask"], section["coverage"])
            ax.imshow(image, cmap=cmap, interpolation="nearest", vmin=0, vmax=1)
        elif key == "coverage":
            ax.imshow(
                section["coverage"],
                cmap=ListedColormap([UNMEASURED_COLOUR, COVERAGE_COLOUR]),
                interpolation="nearest",
                vmin=0,
                vmax=1,
            )
        else:
            ax.imshow(
                robust_normalise(section[key]),
                cmap=display_cmap("magma"),
                interpolation="nearest",
                vmin=0,
                vmax=1,
            )
        ax.set_title(section["dataset"])
        ax.axis("off")
    fig.suptitle(title, fontsize=18)
    fig.tight_layout()
    fig.savefig(output_dir / filename, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_dataset_class_distribution(sections, output_path):
    names = [section["dataset"] for section in sections]
    normal = np.array([section["class_counts"]["normal"] for section in sections])
    tumour = np.array([section["class_counts"]["tumour"] for section in sections])
    y = np.arange(len(names))

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.barh(y, normal, color=NORMAL_COLOUR, label="Normal")
    ax.barh(y, tumour, left=normal, color=TUMOUR_COLOUR, label="Tumour")
    ax.set_yticks(y, labels=names)
    ax.invert_yaxis()
    ax.set_xlabel("Measured pixels")
    ax.set_title("MassNet GBM — Expert-derived class distribution")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def process_section(path, data_dir, output_root, ion_targets, chunk_size):
    dataset = path.stem
    output_dir = output_root / dataset
    ion_dir = output_dir / "ion_images"
    output_dir.mkdir(parents=True, exist_ok=True)
    ion_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 78, flush=True)
    print(f"SECTION: {dataset}", flush=True)
    data_shape, mz, raw_labels, x, y = load_metadata(path)
    shape = (int(np.max(y)), int(np.max(x)))
    mask, coverage = load_and_validate_masks(data_dir, dataset, x, y, shape, raw_labels)

    ion_indices = sorted({int(np.argmin(np.abs(mz - target))) for target in ion_targets})
    tic_values, base_peak_values, ion_values = stream_spectral_summaries(
        path,
        data_shape,
        len(mz),
        len(x),
        ion_indices,
        chunk_size,
    )

    tic = spatial_image(tic_values, x, y, shape)
    base_peak = spatial_image(base_peak_values, x, y, shape)
    mapped_labels = raw_labels - 1
    normal_count = int(np.count_nonzero(mapped_labels == 0))
    tumour_count = int(np.count_nonzero(mapped_labels == 1))

    save_scalar_image(tic, output_dir / "tic.png", f"{dataset} — Total Ion Current")
    save_scalar_image(
        base_peak,
        output_dir / "base_peak.png",
        f"{dataset} — Base-Peak Intensity",
    )
    save_mask(mask, coverage, output_dir / "mask.png", f"{dataset} — Normal/Tumour Mask")
    save_coverage(
        coverage,
        output_dir / "msi_coverage.png",
        f"{dataset} — MSI Spatial Coverage",
    )
    save_overlay(
        tic,
        mask,
        coverage,
        output_dir / "tic_mask_overlay.png",
        f"{dataset} — TIC + Normal/Tumour Mask",
    )
    save_class_distribution(
        normal_count,
        tumour_count,
        output_dir / "class_distribution.png",
        f"{dataset} — Expert-Derived Labels",
    )

    resolved_ions = []
    for index in ion_indices:
        actual_mz = float(mz[index])
        ion_image = spatial_image(ion_values[index], x, y, shape)
        ion_path = ion_dir / f"mz_{actual_mz:.4f}.png"
        save_scalar_image(ion_image, ion_path, f"{dataset} — m/z {actual_mz:.4f}", cmap="viridis")
        resolved_ions.append({"index": index, "mz": actual_mz, "file": str(ion_path)})

    section = {
        "dataset": dataset,
        "source_file": str(path),
        "data_shape": list(data_shape),
        "image_shape_y_x": list(shape),
        "measured_pixels": int(len(x)),
        "grid_pixels": int(np.prod(shape)),
        "coverage_percent": float(100.0 * len(x) / np.prod(shape)),
        "spectral_bins": int(len(mz)),
        "mz_range": [float(np.min(mz)), float(np.max(mz))],
        "class_counts": {"normal": normal_count, "tumour": tumour_count},
        "resolved_ion_images": resolved_ions,
        "tic": tic,
        "base_peak": base_peak,
        "mask": mask,
        "coverage": coverage,
    }
    save_section_overview(section, output_dir / "section_overview.png")

    serialisable = {key: value for key, value in section.items() if key not in {"tic", "base_peak", "mask", "coverage"}}
    (output_dir / "summary.json").write_text(json.dumps(serialisable, indent=2), encoding="utf-8")

    print(f"Measured pixels: {len(x):,}", flush=True)
    print(f"Normal: {normal_count:,} | Tumour: {tumour_count:,}", flush=True)
    print(f"Saved visualisations: {output_dir}", flush=True)
    return section


def main():
    parser = argparse.ArgumentParser(description="Visualise MassNet GBM HDF5 data and masks.")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=2048)
    parser.add_argument("--ion-mz", nargs="*", type=float, default=DEFAULT_ION_TARGETS)
    args = parser.parse_args()

    data_dir = args.data_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.chunk_size < 1:
        raise ValueError("--chunk-size must be positive")

    missing = [name for name in EXPECTED_FILES if not (data_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing expected HDF5 files: {missing}")

    print("MASSNET GBM DATASET VISUALISATION", flush=True)
    print(f"Data directory: {data_dir}", flush=True)
    print(f"Output directory: {output_dir}", flush=True)
    print(f"Sections: {len(EXPECTED_FILES)}", flush=True)
    print(f"Spectral chunk size: {args.chunk_size:,}", flush=True)

    sections = [
        process_section(
            data_dir / filename,
            data_dir,
            output_dir,
            args.ion_mz,
            args.chunk_size,
        )
        for filename in EXPECTED_FILES
    ]

    save_dataset_overview(
        sections,
        output_dir,
        "tic",
        "MassNet GBM — Total Ion Current Overview",
        "gbm_massnet_overview_tic.png",
    )
    save_dataset_overview(
        sections,
        output_dir,
        "base_peak",
        "MassNet GBM — Base-Peak Intensity Overview",
        "gbm_massnet_overview_base_peak.png",
    )
    save_dataset_overview(
        sections,
        output_dir,
        "mask",
        "MassNet GBM — Normal/Tumour Mask Overview",
        "gbm_massnet_overview_masks.png",
    )
    save_dataset_overview(
        sections,
        output_dir,
        "coverage",
        "MassNet GBM — MSI Coverage Overview",
        "gbm_massnet_overview_coverage.png",
    )
    save_dataset_class_distribution(
        sections,
        output_dir / "gbm_massnet_class_distribution.png",
    )

    summary = {
        "provenance": (
            "MassNet Class_Label values are expert-pathologist H&E annotations "
            "manually transferred to MSI coordinates"
        ),
        "mask_classes": {"0": "normal", "1": "tumour"},
        "unmeasured_locations": "excluded using the separate coverage arrays",
        "sections": [
            {key: value for key, value in section.items() if key not in {"tic", "base_peak", "mask", "coverage"}}
            for section in sections
        ],
    }
    (output_dir / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print("=" * 78, flush=True)
    print("VISUALISATION COMPLETE", flush=True)
    print(f"Results: {output_dir}", flush=True)


if __name__ == "__main__":
    main()
