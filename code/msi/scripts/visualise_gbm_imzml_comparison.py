#!/usr/bin/env python3
"""Visualise the official GBM masks beside the reconstructed HDF5 masks."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import numpy as np

from visualise_massnet_gbm import (
    COVERAGE_COLOUR,
    EXPECTED_FILES,
    NORMAL_COLOUR,
    TUMOUR_COLOUR,
    UNMEASURED_COLOUR,
    display_cmap,
    load_metadata,
    robust_normalise,
    spatial_image,
    stream_spectral_summaries,
)


AGREEMENT_COLOUR = "#457B6E"
DISAGREEMENT_COLOUR = "#D1495B"
OFFICIAL_CMAP = ListedColormap(
    [UNMEASURED_COLOUR, NORMAL_COLOUR, TUMOUR_COLOUR]
)
SEMANTIC_CMAP = ListedColormap([NORMAL_COLOUR, TUMOUR_COLOUR])


def image_axis(axis, title):
    axis.set_title(title)
    axis.set_xlabel("X")
    axis.set_ylabel("Y")
    axis.set_aspect("equal")


def semantic_official_mask(official_mask, coverage):
    semantic = np.full(official_mask.shape, np.nan, dtype=np.float64)
    semantic[coverage] = official_mask[coverage] - 1
    return semantic


def semantic_reconstructed_mask(reconstructed_mask, coverage):
    semantic = reconstructed_mask.astype(np.float64)
    semantic[~coverage] = np.nan
    return semantic


def save_section_figure(section, path):
    fig, axes = plt.subplots(2, 3, figsize=(15, 10), constrained_layout=True)

    axes[0, 0].imshow(
        robust_normalise(section["tic"]),
        cmap=display_cmap("magma"),
        interpolation="nearest",
        vmin=0,
        vmax=1,
    )
    image_axis(axes[0, 0], "Total ion current")

    axes[0, 1].imshow(
        robust_normalise(section["base_peak"]),
        cmap=display_cmap("magma"),
        interpolation="nearest",
        vmin=0,
        vmax=1,
    )
    image_axis(axes[0, 1], "Base-peak intensity")

    axes[0, 2].imshow(
        section["coverage"],
        cmap=ListedColormap([UNMEASURED_COLOUR, COVERAGE_COLOUR]),
        interpolation="nearest",
        vmin=0,
        vmax=1,
    )
    image_axis(axes[0, 2], "MSI coverage")
    axes[0, 2].legend(
        handles=[
            Patch(facecolor=UNMEASURED_COLOUR, label="No spectrum"),
            Patch(facecolor=COVERAGE_COLOUR, label="Measured spectrum"),
        ],
        loc="upper right",
    )

    axes[1, 0].imshow(
        section["official_mask"],
        cmap=OFFICIAL_CMAP,
        interpolation="nearest",
        vmin=0,
        vmax=2,
    )
    image_axis(axes[1, 0], "Official mask encoding")
    axes[1, 0].legend(
        handles=[
            Patch(facecolor=UNMEASURED_COLOUR, label="0: Background"),
            Patch(facecolor=NORMAL_COLOUR, label="1: Normal"),
            Patch(facecolor=TUMOUR_COLOUR, label="2: Tumour"),
        ],
        loc="upper right",
    )

    reconstructed = np.ma.masked_invalid(section["reconstructed_semantic"])
    reconstructed_cmap = SEMANTIC_CMAP.copy()
    reconstructed_cmap.set_bad(UNMEASURED_COLOUR)
    axes[1, 1].imshow(
        reconstructed,
        cmap=reconstructed_cmap,
        interpolation="nearest",
        vmin=0,
        vmax=1,
    )
    image_axis(axes[1, 1], "Our semantic mask")
    axes[1, 1].legend(
        handles=[
            Patch(facecolor=UNMEASURED_COLOUR, label="Unmeasured"),
            Patch(facecolor=NORMAL_COLOUR, label="0: Normal"),
            Patch(facecolor=TUMOUR_COLOUR, label="1: Tumour"),
        ],
        loc="upper right",
    )

    comparison = np.full(section["coverage"].shape, np.nan)
    comparison[section["coverage"]] = section["semantic_disagreement"][
        section["coverage"]
    ]
    comparison_cmap = ListedColormap([AGREEMENT_COLOUR, DISAGREEMENT_COLOUR])
    comparison_cmap.set_bad(UNMEASURED_COLOUR)
    axes[1, 2].imshow(
        np.ma.masked_invalid(comparison),
        cmap=comparison_cmap,
        interpolation="nearest",
        vmin=0,
        vmax=1,
    )
    image_axis(
        axes[1, 2],
        f"Semantic disagreement: {section['semantic_difference_count']:,} pixels",
    )
    axes[1, 2].legend(
        handles=[
            Patch(facecolor=AGREEMENT_COLOUR, label="Same tissue class"),
            Patch(facecolor=DISAGREEMENT_COLOUR, label="Different tissue class"),
            Patch(facecolor=UNMEASURED_COLOUR, label="Unmeasured"),
        ],
        loc="upper right",
    )

    fig.suptitle(
        f"{section['dataset']} - official imzML versus HDF5 representation",
        fontsize=17,
    )
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_overlay(section, path):
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.imshow(
        robust_normalise(section["tic"]),
        cmap=display_cmap("gray"),
        interpolation="nearest",
        vmin=0,
        vmax=1,
    )
    cmap = SEMANTIC_CMAP.copy()
    cmap.set_bad((0, 0, 0, 0))
    ax.imshow(
        np.ma.masked_invalid(section["official_semantic"]),
        cmap=cmap,
        interpolation="nearest",
        vmin=0,
        vmax=1,
        alpha=0.45,
    )
    image_axis(ax, f"{section['dataset']} - TIC with official tissue mask")
    ax.legend(
        handles=[
            Patch(facecolor=NORMAL_COLOUR, label="Normal"),
            Patch(facecolor=TUMOUR_COLOUR, label="Tumour"),
        ],
        loc="upper right",
    )
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_collection_overview(sections, output_dir):
    for key, title, filename, cmap, minimum, maximum in (
        (
            "official_mask",
            "Official GBM masks: 0 background, 1 normal, 2 tumour",
            "official_masks_overview.png",
            OFFICIAL_CMAP,
            0,
            2,
        ),
        (
            "official_semantic",
            "Official GBM masks after semantic recoding",
            "semantic_masks_overview.png",
            SEMANTIC_CMAP,
            0,
            1,
        ),
    ):
        fig, axes = plt.subplots(2, 4, figsize=(18, 9), constrained_layout=True)
        for axis, section in zip(axes.ravel(), sections):
            image = section[key]
            shown_cmap = cmap.copy()
            if key == "official_semantic":
                shown_cmap.set_bad(UNMEASURED_COLOUR)
                image = np.ma.masked_invalid(image)
            axis.imshow(
                image,
                cmap=shown_cmap,
                interpolation="nearest",
                vmin=minimum,
                vmax=maximum,
            )
            axis.set_title(section["dataset"])
            axis.axis("off")
        fig.suptitle(title, fontsize=18)
        fig.savefig(output_dir / filename, dpi=220, bbox_inches="tight")
        plt.close(fig)

    fig, axes = plt.subplots(2, 4, figsize=(18, 9), constrained_layout=True)
    cmap = ListedColormap([AGREEMENT_COLOUR, DISAGREEMENT_COLOUR])
    cmap.set_bad(UNMEASURED_COLOUR)
    for axis, section in zip(axes.ravel(), sections):
        comparison = np.full(section["coverage"].shape, np.nan)
        comparison[section["coverage"]] = section["semantic_disagreement"][
            section["coverage"]
        ]
        axis.imshow(
            np.ma.masked_invalid(comparison),
            cmap=cmap,
            interpolation="nearest",
            vmin=0,
            vmax=1,
        )
        axis.set_title(
            f"{section['dataset']} ({section['semantic_difference_count']} different)"
        )
        axis.axis("off")
    fig.suptitle("Official versus reconstructed tissue classes", fontsize=18)
    fig.savefig(output_dir / "semantic_disagreements_overview.png", dpi=220)
    plt.close(fig)


def process_section(h5_path, official_root, reconstructed_root, output_root, chunk_size):
    dataset = h5_path.stem
    output_dir = output_root / dataset
    output_dir.mkdir(parents=True, exist_ok=True)

    data_shape, mz, raw_labels, x, y = load_metadata(h5_path)
    shape = (int(np.max(y)), int(np.max(x)))
    coverage = np.zeros(shape, dtype=bool)
    coverage[y - 1, x - 1] = True

    official_mask = np.load(official_root / "masks" / f"{dataset}_mask.npy")
    reconstructed_mask = np.load(
        reconstructed_root / "masks" / f"{dataset}_mask.npy"
    )
    if official_mask.shape != shape or reconstructed_mask.shape != shape:
        raise ValueError(f"{dataset}: mask shape does not match coordinates")

    official_semantic = semantic_official_mask(official_mask, coverage)
    reconstructed_semantic = semantic_reconstructed_mask(
        reconstructed_mask, coverage
    )
    semantic_disagreement = np.zeros(shape, dtype=np.uint8)
    semantic_disagreement[coverage] = (
        official_semantic[coverage] != reconstructed_semantic[coverage]
    )

    tic_values, base_peak_values, _ions = stream_spectral_summaries(
        h5_path,
        data_shape,
        len(mz),
        len(x),
        [],
        chunk_size,
    )
    section = {
        "dataset": dataset,
        "coverage": coverage,
        "tic": spatial_image(tic_values, x, y, shape),
        "base_peak": spatial_image(base_peak_values, x, y, shape),
        "official_mask": official_mask,
        "official_semantic": official_semantic,
        "reconstructed_semantic": reconstructed_semantic,
        "semantic_disagreement": semantic_disagreement,
        "semantic_difference_count": int(
            np.count_nonzero(semantic_disagreement[coverage])
        ),
        "numeric_encoding_difference_count": int(
            np.count_nonzero(official_mask != reconstructed_mask)
        ),
        "measured_pixels": int(len(x)),
        "normal_pixels": int(np.count_nonzero(raw_labels == 1)),
        "tumour_pixels": int(np.count_nonzero(raw_labels == 2)),
    }
    save_section_figure(section, output_dir / "representation_comparison.png")
    save_overlay(section, output_dir / "official_tic_mask_overlay.png")
    print(
        f"{dataset}: semantic differences="
        f"{section['semantic_difference_count']}, saved={output_dir}",
        flush=True,
    )
    return section


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h5-root", required=True, type=Path)
    parser.add_argument("--official-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=2048)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    sections = [
        process_section(
            args.h5_root / filename,
            args.official_root,
            args.h5_root,
            args.output_dir,
            args.chunk_size,
        )
        for filename in EXPECTED_FILES
    ]
    save_collection_overview(sections, args.output_dir)

    summary = {
        "purpose": "Visual comparison of official imzML and reconstructed HDF5 masks",
        "encoding": {
            "official": {"0": "background", "1": "normal", "2": "tumour"},
            "reconstructed": {
                "coverage_false": "unmeasured",
                "0": "normal",
                "1": "tumour",
            },
        },
        "sections": [
            {
                key: value
                for key, value in section.items()
                if key
                in {
                    "dataset",
                    "semantic_difference_count",
                    "numeric_encoding_difference_count",
                    "measured_pixels",
                    "normal_pixels",
                    "tumour_pixels",
                }
            }
            for section in sections
        ],
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"Visualisations saved to {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()

