#!/usr/bin/env python3

"""
Visualise the complete CAC MSI dataset.

For every CAC section:
    - TIC image
    - Base-peak intensity image
    - 3-class segmentation mask
    - TIC + mask overlay
    - MSI coverage map
    - representative ion images
    - section summary

Dataset-wide:
    - TIC overview
    - segmentation mask overview
    - MSI coverage overview
    - dataset summary

Usage:

python scripts/visualise_cac.py \
    --data-dir /datasets/zsuliman/msi_data/cac \
    --output-dir results/visualisations/cac
"""

import argparse
from pathlib import Path

import numpy as np

import matplotlib

# We are running on the cluster without a display.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

from pyimzml.ImzMLParser import ImzMLParser


# ============================================================
# MASK COLOURS
# ============================================================

# Current labels are intentionally generic.
#
# The S3PL README gives:
#
#   0 = background
#   1 = tumour
#   2 = healthy tissue
#
# as an example of a 3-class segmentation setup.
#
# It does NOT explicitly establish that these exact labels
# correspond to the CAC masks we have.
#
# Therefore:
#
#   0 = Background
#   1 = Class 1
#   2 = Class 2
#
# We can rename 1/2 once their biological meaning is verified.

MASK_COLOURS = [
    "#20242A",   # Class 0 - background
    "#E76F51",   # Class 1
    "#2A9D8F",   # Class 2
]

MASK_LABELS = [
    "Background",
    "Class 1",
    "Class 2",
]

MASK_CMAP = ListedColormap(MASK_COLOURS)


# ============================================================
# DATASET DISCOVERY
# ============================================================

def discover_datasets(data_dir):
    """
    Find all CAC .imzML files.

    Returns:
        List of dataset names without extensions.
    """

    datasets = sorted(
        path.stem
        for path in Path(data_dir).glob("*.imzML")
    )

    if not datasets:
        raise FileNotFoundError(
            f"No .imzML files found in {data_dir}"
        )

    return datasets


# ============================================================
# LOAD ONE SECTION
# ============================================================

def load_section(data_dir, dataset):

    imzml_path = (
        Path(data_dir)
        / f"{dataset}.imzML"
    )

    mask_path = (
        Path(data_dir)
        / "masks"
        / f"{dataset}_mask.npy"
    )

    if not imzml_path.exists():
        raise FileNotFoundError(
            f"MSI file not found: {imzml_path}"
        )

    if not mask_path.exists():
        raise FileNotFoundError(
            f"Mask file not found: {mask_path}"
        )

    parser = ImzMLParser(
        str(imzml_path)
    )

    spectra = []
    xs = []
    ys = []

    mz_values = None

    for idx, (x, y, z) in enumerate(
        parser.coordinates
    ):

        mzs, intensities = (
            parser.getspectrum(idx)
        )

        if mz_values is None:
            mz_values = np.asarray(
                mzs,
                dtype=np.float32
            )

        spectra.append(
            np.asarray(
                intensities,
                dtype=np.float32
            )
        )

        xs.append(int(x))
        ys.append(int(y))

    spectra = np.asarray(
        spectra,
        dtype=np.float32
    )

    xs = np.asarray(
        xs,
        dtype=np.int32
    )

    ys = np.asarray(
        ys,
        dtype=np.int32
    )

    mask = np.load(
        mask_path
    )

    return (
        spectra,
        mz_values,
        xs,
        ys,
        mask,
    )


# ============================================================
# SPECTRA -> SPATIAL IMAGE
# ============================================================

def spectra_to_image(
    values,
    xs,
    ys,
    shape
):
    """
    Convert values associated with MSI coordinates
    into a 2D spatial image.

    IMPORTANT:

    The image is based on the mask's spatial dimensions,
    but only coordinates actually present in the MSI file
    are populated.

    Missing spatial locations remain NaN.
    """

    image = np.full(
        shape,
        np.nan,
        dtype=np.float32
    )

    for value, x, y in zip(
        values,
        xs,
        ys
    ):

        image[
            y - 1,
            x - 1
        ] = value

    return image


# ============================================================
# MSI COVERAGE MAP
# ============================================================

def create_coverage_map(
    xs,
    ys,
    shape
):
    """
    Create a binary image showing where MSI spectra exist.

    1 = spectrum exists
    0 = no spectrum
    """

    coverage = np.zeros(
        shape,
        dtype=np.uint8
    )

    for x, y in zip(xs, ys):

        coverage[
            y - 1,
            x - 1
        ] = 1

    return coverage


# ============================================================
# MASK VALUES AT ACTUAL MSI LOCATIONS
# ============================================================

def get_mask_values_at_msi_locations(
    mask,
    xs,
    ys
):
    """
    Extract the segmentation class corresponding
    to every actual MSI spectrum.

    This follows the same coordinate logic used
    by S3PL's create_pearson_labels.py.
    """

    mask_values = np.empty(
        len(xs),
        dtype=mask.dtype
    )

    for i, (x, y) in enumerate(
        zip(xs, ys)
    ):

        mask_values[i] = (
            mask[y - 1, x - 1]
        )

    return mask_values


# ============================================================
# ROBUST DISPLAY NORMALISATION
# ============================================================

def normalise_for_display(
    image,
    low=1,
    high=99
):
    """
    Robust percentile-based normalisation.

    This prevents a small number of extremely intense
    pixels from dominating the visualisation.
    """

    finite = image[
        np.isfinite(image)
    ]

    if finite.size == 0:
        return np.zeros_like(
            image
        )

    lower = np.percentile(
        finite,
        low
    )

    upper = np.percentile(
        finite,
        high
    )

    if upper <= lower:
        return np.nan_to_num(
            image
        )

    result = (
        image - lower
    ) / (
        upper - lower
    )

    return np.clip(
        result,
        0,
        1
    )


# ============================================================
# GENERIC IMAGE SAVER
# ============================================================

def save_image(
    image,
    path,
    title,
    cmap="magma",
    vmin=None,
    vmax=None,
):
    fig, ax = plt.subplots(
        figsize=(7, 6)
    )

    ax.imshow(
        image,
        cmap=cmap,
        interpolation="nearest",
        vmin=vmin,
        vmax=vmax,
    )

    ax.set_title(
        title,
        fontsize=13,
        pad=10
    )

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_aspect("equal")

    plt.tight_layout()

    fig.savefig(
        path,
        dpi=200,
        bbox_inches="tight"
    )

    plt.close(fig)


# ============================================================
# MASK IMAGE
# ============================================================

def save_mask(
    mask,
    path,
    title
):
    fig, ax = plt.subplots(
        figsize=(7, 6)
    )

    ax.imshow(
        mask,
        cmap=MASK_CMAP,
        interpolation="nearest",
        vmin=0,
        vmax=2,
    )

    ax.set_title(
        title,
        fontsize=13,
        pad=10
    )

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_aspect("equal")

    legend = [
        Patch(
            facecolor=MASK_COLOURS[i],
            label=f"{i}: {MASK_LABELS[i]}"
        )
        for i in range(3)
    ]

    ax.legend(
        handles=legend,
        loc="upper right",
        framealpha=0.9,
    )

    plt.tight_layout()

    fig.savefig(
        path,
        dpi=200,
        bbox_inches="tight"
    )

    plt.close(fig)


# ============================================================
# MASK + TIC OVERLAY
# ============================================================

def save_overlay(
    tic,
    mask,
    coverage,
    path,
    title
):
    """
    Show TIC in grayscale with segmentation
    classes overlaid.

    Importantly, mask pixels that do not have
    MSI data are not overlaid.
    """

    fig, ax = plt.subplots(
        figsize=(7, 6)
    )

    tic_display = normalise_for_display(
        tic
    )

    ax.imshow(
        tic_display,
        cmap="gray",
        interpolation="nearest",
    )

    # Only display mask where MSI data exists.
    mask_overlay = np.ma.masked_where(
        coverage == 0,
        mask
    )

    ax.imshow(
        mask_overlay,
        cmap=MASK_CMAP,
        interpolation="nearest",
        alpha=0.45,
        vmin=0,
        vmax=2,
    )

    ax.set_title(
        title,
        fontsize=13,
        pad=10
    )

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_aspect("equal")

    legend = [
        Patch(
            facecolor=MASK_COLOURS[1],
            label="Class 1"
        ),
        Patch(
            facecolor=MASK_COLOURS[2],
            label="Class 2"
        ),
    ]

    ax.legend(
        handles=legend,
        loc="upper right",
        framealpha=0.9,
    )

    plt.tight_layout()

    fig.savefig(
        path,
        dpi=200,
        bbox_inches="tight"
    )

    plt.close(fig)


# ============================================================
# COVERAGE IMAGE
# ============================================================

def save_coverage(
    coverage,
    path,
    title
):
    """
    Visualise where MSI spectra actually exist.
    """

    cmap = ListedColormap([
        "#ECECEC",
        "#264653",
    ])

    fig, ax = plt.subplots(
        figsize=(7, 6)
    )

    ax.imshow(
        coverage,
        cmap=cmap,
        interpolation="nearest",
        vmin=0,
        vmax=1,
    )

    ax.set_title(
        title,
        fontsize=13,
        pad=10
    )

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_aspect("equal")

    legend = [
        Patch(
            facecolor="#ECECEC",
            label="No MSI spectrum"
        ),
        Patch(
            facecolor="#264653",
            label="MSI spectrum"
        ),
    ]

    ax.legend(
        handles=legend,
        loc="upper right",
        framealpha=0.9,
    )

    plt.tight_layout()

    fig.savefig(
        path,
        dpi=200,
        bbox_inches="tight"
    )

    plt.close(fig)


# ============================================================
# REPRESENTATIVE ION IMAGES
# ============================================================

def save_ion_images(
    spectra,
    mz_values,
    xs,
    ys,
    shape,
    output_dir
):
    """
    Save six representative ion images across
    the m/z range.
    """

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    n_mz = len(
        mz_values
    )

    indices = np.linspace(
        0,
        n_mz - 1,
        6,
        dtype=int
    )

    for idx in indices:

        image = spectra_to_image(
            spectra[:, idx],
            xs,
            ys,
            shape
        )

        image = normalise_for_display(
            image
        )

        mz = mz_values[idx]

        save_image(
            image,
            output_dir
            / (
                f"ion_{idx:04d}"
                f"_mz_{mz:.4f}.png"
            ),
            (
                f"Representative ion — "
                f"m/z {mz:.4f}"
            ),
            cmap="viridis",
            vmin=0,
            vmax=1,
        )


# ============================================================
# SECTION SUMMARY
# ============================================================

def save_section_summary(
    dataset,
    spectra,
    mz_values,
    xs,
    ys,
    mask,
    coverage,
    output_dir
):
    """
    Write a detailed text summary.

    Includes both:
        1. full mask distribution
        2. mask distribution at actual MSI locations
    """

    total_mask_pixels = mask.size
    total_msi_pixels = len(xs)

    full_classes, full_counts = (
        np.unique(
            mask,
            return_counts=True
        )
    )

    mask_at_msi = (
        get_mask_values_at_msi_locations(
            mask,
            xs,
            ys
        )
    )

    msi_classes, msi_counts = (
        np.unique(
            mask_at_msi,
            return_counts=True
        )
    )

    lines = [
        f"Dataset: {dataset}",
        "",
        "=== MSI INFORMATION ===",
        f"MSI spectra: {total_msi_pixels}",
        f"Spectrum shape: {spectra.shape}",
        f"Number of m/z values: {len(mz_values)}",
        (
            f"m/z range: "
            f"{mz_values.min():.6f} - "
            f"{mz_values.max():.6f}"
        ),
        (
            f"Mask grid shape: "
            f"{mask.shape}"
        ),
        (
            f"Image dimensions: "
            f"{mask.shape[1]} x "
            f"{mask.shape[0]}"
        ),
        (
            f"X coordinates: "
            f"{xs.min()} - {xs.max()}"
        ),
        (
            f"Y coordinates: "
            f"{ys.min()} - {ys.max()}"
        ),
        "",
        "=== SPATIAL COVERAGE ===",
        (
            f"Mask grid pixels: "
            f"{total_mask_pixels}"
        ),
        (
            f"MSI pixels: "
            f"{total_msi_pixels}"
        ),
        (
            f"Missing MSI locations: "
            f"{total_mask_pixels - total_msi_pixels}"
        ),
        (
            f"MSI coverage: "
            f"{100 * total_msi_pixels / total_mask_pixels:.2f}%"
        ),
        "",
        "=== FULL MASK DISTRIBUTION ===",
    ]

    for cls, count in zip(
        full_classes,
        full_counts
    ):

        percentage = (
            100 * count
            / total_mask_pixels
        )

        cls_int = int(cls)

        label = (
            MASK_LABELS[cls_int]
            if cls_int < len(MASK_LABELS)
            else f"Class {cls}"
        )

        lines.append(
            f"Class {cls}: "
            f"{label}: "
            f"{count} pixels "
            f"({percentage:.2f}%)"
        )

    lines.extend([
        "",
        "=== MASK DISTRIBUTION AT MSI LOCATIONS ===",
    ])

    for cls, count in zip(
        msi_classes,
        msi_counts
    ):

        percentage = (
            100 * count
            / total_msi_pixels
        )

        cls_int = int(cls)

        label = (
            MASK_LABELS[cls_int]
            if cls_int < len(MASK_LABELS)
            else f"Class {cls}"
        )

        lines.append(
            f"Class {cls}: "
            f"{label}: "
            f"{count} MSI pixels "
            f"({percentage:.2f}%)"
        )

    (
        output_dir / "summary.txt"
    ).write_text(
        "\n".join(lines)
    )


# ============================================================
# DATASET-WIDE OVERVIEW
# ============================================================

def save_dataset_overview(
    sections,
    output_dir,
    kind
):
    """
    Create a 4-column overview containing
    all CAC sections.
    """

    n = len(
        sections
    )

    cols = 4

    rows = int(
        np.ceil(n / cols)
    )

    fig, axes = plt.subplots(
        rows,
        cols,
        figsize=(16, 4 * rows)
    )

    axes = np.atleast_1d(
        axes
    ).ravel()

    for ax, section in zip(
        axes,
        sections
    ):

        image = section[kind]

        if kind == "mask":

            ax.imshow(
                image,
                cmap=MASK_CMAP,
                interpolation="nearest",
                vmin=0,
                vmax=2,
            )

        elif kind == "coverage":

            coverage_cmap = ListedColormap([
                "#ECECEC",
                "#264653",
            ])

            ax.imshow(
                image,
                cmap=coverage_cmap,
                interpolation="nearest",
                vmin=0,
                vmax=1,
            )

        else:

            ax.imshow(
                normalise_for_display(
                    image
                ),
                cmap="magma",
                interpolation="nearest",
            )

        ax.set_title(
            section["dataset"],
            fontsize=12
        )

        ax.axis("off")

    for ax in axes[n:]:
        ax.axis("off")

    titles = {
        "tic": (
            "CAC Dataset — "
            "Total Ion Current Overview"
        ),
        "mask": (
            "CAC Dataset — "
            "Segmentation Mask Overview"
        ),
        "coverage": (
            "CAC Dataset — "
            "MSI Coverage Overview"
        ),
    }

    fig.suptitle(
        titles[kind],
        fontsize=17,
        y=0.995
    )

    plt.tight_layout()

    fig.savefig(
        output_dir
        / f"cac_overview_{kind}.png",
        dpi=220,
        bbox_inches="tight"
    )

    plt.close(fig)


# ============================================================
# DATASET SUMMARY
# ============================================================

def save_dataset_summary(
    sections,
    output_dir
):
    """
    Write a dataset-wide summary.
    """

    lines = [
        "CAC DATASET OVERVIEW",
        "====================",
        "",
        f"Number of sections: {len(sections)}",
        "",
    ]

    for section in sections:

        dataset = section["dataset"]
        mask = section["mask"]
        spectra = section["spectra"]
        mz = section["mz_values"]
        xs = section["xs"]

        mask_at_msi = (
            get_mask_values_at_msi_locations(
                mask,
                xs,
                section["ys"]
            )
        )

        classes, counts = (
            np.unique(
                mask_at_msi,
                return_counts=True
            )
        )

        lines.extend([
            dataset,
            "-" * len(dataset),
            f"MSI spectra: {len(xs)}",
            f"Mask pixels: {mask.size}",
            (
                f"MSI coverage: "
                f"{100 * len(xs) / mask.size:.2f}%"
            ),
            (
                f"Image shape: "
                f"{mask.shape[1]} x "
                f"{mask.shape[0]}"
            ),
            f"Spectral bins: {len(mz)}",
            (
                f"m/z range: "
                f"{mz.min():.4f} - "
                f"{mz.max():.4f}"
            ),
            "",
            "Mask distribution at MSI locations:",
        ])

        for cls, count in zip(
            classes,
            counts
        ):

            percentage = (
                100 * count / len(xs)
            )

            lines.append(
                f"  Class {cls}: "
                f"{count} "
                f"({percentage:.2f}%)"
            )

        lines.append("")

    (
        output_dir / "dataset_summary.txt"
    ).write_text(
        "\n".join(lines)
    )


# ============================================================
# PROCESS ONE SECTION
# ============================================================

def process_section(
    data_dir,
    dataset,
    output_root
):

    print(
        f"\n=== {dataset} ==="
    )

    output_dir = (
        output_root / dataset
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    ion_output_dir = (
        output_dir / "ion_images"
    )

    ion_output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    print(
        "Loading MSI data..."
    )

    (
        spectra,
        mz_values,
        xs,
        ys,
        mask,
    ) = load_section(
        data_dir,
        dataset
    )

    shape = mask.shape

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # We DO NOT require:
    #
    #     len(spectra) == mask.size
    #
    # The mask is a spatial grid while the MSI file
    # contains spectra only at actual measured coordinates.
    # --------------------------------------------------------

    coverage = create_coverage_map(
        xs,
        ys,
        shape
    )

    mask_at_msi = (
        get_mask_values_at_msi_locations(
            mask,
            xs,
            ys
        )
    )

    # --------------------------------------------------------
    # TIC
    # --------------------------------------------------------

    tic_values = np.sum(
        spectra,
        axis=1
    )

    tic = spectra_to_image(
        tic_values,
        xs,
        ys,
        shape
    )

    # --------------------------------------------------------
    # Base peak
    # --------------------------------------------------------

    base_peak_values = np.max(
        spectra,
        axis=1
    )

    base_peak = spectra_to_image(
        base_peak_values,
        xs,
        ys,
        shape
    )

    print(
        f"MSI spectra: {len(spectra)}"
    )

    print(
        f"Mask pixels: {mask.size}"
    )

    print(
        f"MSI coverage: "
        f"{100 * len(spectra) / mask.size:.2f}%"
    )

    print(
        f"Spectrum shape: {spectra.shape}"
    )

    print(
        f"m/z range: "
        f"{mz_values.min():.4f} - "
        f"{mz_values.max():.4f}"
    )

    print(
        f"Mask classes: "
        f"{np.unique(mask)}"
    )

    print(
        "Mask classes at MSI locations: "
        f"{np.unique(mask_at_msi)}"
    )

    # --------------------------------------------------------
    # Save images
    # --------------------------------------------------------

    save_image(
        normalise_for_display(tic),
        output_dir / "tic.png",
        f"{dataset} — Total Ion Current",
        cmap="magma",
        vmin=0,
        vmax=1
    )

    save_image(
        normalise_for_display(base_peak),
        output_dir / "base_peak.png",
        f"{dataset} — Base Peak Intensity",
        cmap="magma",
        vmin=0,
        vmax=1
    )

    save_mask(
        mask,
        output_dir / "mask.png",
        f"{dataset} — Segmentation Mask"
    )

    save_overlay(
        tic,
        mask,
        coverage,
        output_dir / "tic_mask_overlay.png",
        f"{dataset} — TIC + Segmentation"
    )

    save_coverage(
        coverage,
        output_dir / "msi_coverage.png",
        f"{dataset} — MSI Spatial Coverage"
    )

    # --------------------------------------------------------
    # Representative ion images
    # --------------------------------------------------------

    save_ion_images(
        spectra,
        mz_values,
        xs,
        ys,
        shape,
        ion_output_dir
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    save_section_summary(
        dataset,
        spectra,
        mz_values,
        xs,
        ys,
        mask,
        coverage,
        output_dir
    )

    return {
        "dataset": dataset,
        "spectra": spectra,
        "mz_values": mz_values,
        "xs": xs,
        "ys": ys,
        "mask": mask,
        "tic": tic,
        "coverage": coverage,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Visualise the complete "
            "CAC MSI dataset."
        )
    )

    parser.add_argument(
        "--data-dir",
        required=True,
        help=(
            "Directory containing CAC "
            ".imzML/.ibd files and masks/"
        )
    )

    parser.add_argument(
        "--output-dir",
        required=True,
        help=(
            "Directory where "
            "visualisations will be written."
        )
    )

    args = parser.parse_args()

    data_dir = Path(
        args.data_dir
    )

    output_root = Path(
        args.output_dir
    )

    output_root.mkdir(
        parents=True,
        exist_ok=True
    )

    print(
        "=== CAC DATASET VISUALISATION ==="
    )

    print(
        f"Data directory: {data_dir}"
    )

    print(
        f"Output directory: {output_root}"
    )

    datasets = discover_datasets(
        data_dir
    )

    print(
        f"Found {len(datasets)} CAC sections:"
    )

    for dataset in datasets:
        print(
            f"  - {dataset}"
        )

    sections = []

    for dataset in datasets:

        section = process_section(
            data_dir,
            dataset,
            output_root
        )

        sections.append(
            section
        )

    # --------------------------------------------------------
    # Dataset-wide visualisations
    # --------------------------------------------------------

    print(
        "\n=== Creating dataset-wide overviews ==="
    )

    save_dataset_overview(
        sections,
        output_root,
        "tic"
    )

    save_dataset_overview(
        sections,
        output_root,
        "mask"
    )

    save_dataset_overview(
        sections,
        output_root,
        "coverage"
    )

    save_dataset_summary(
        sections,
        output_root
    )

    print(
        "\n=== VISUALISATION COMPLETE ==="
    )

    print(
        f"Results saved to: {output_root}"
    )


if __name__ == "__main__":
    main()