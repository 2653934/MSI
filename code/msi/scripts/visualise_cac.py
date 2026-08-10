import argparse
import os

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from pyimzml.ImzMLParser import ImzMLParser


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

MASK_COLORS = [
    "#20252B",  # Class 0 - background
    "#E76F51",  # Class 1
    "#2A9D8F",  # Class 2
]

MASK_LABELS = [
    "Class 0",
    "Class 1",
    "Class 2",
]


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def load_spectra(imzml_path):
    """Load all spectra and spatial coordinates from an imzML file."""

    print(f"Loading MSI file: {imzml_path}")

    parser = ImzMLParser(imzml_path)

    spectra = []
    x_coords = []
    y_coords = []

    for idx, (x, y, z) in enumerate(parser.coordinates):
        mzs, intensities = parser.getspectrum(idx)

        spectra.append(intensities)
        x_coords.append(x)
        y_coords.append(y)

    spectra = np.asarray(spectra)
    x_coords = np.asarray(x_coords)
    y_coords = np.asarray(y_coords)

    # m/z values are assumed to be the same across spectra.
    mz_values, _ = parser.getspectrum(0)

    return (
        parser,
        spectra,
        np.asarray(mz_values),
        x_coords,
        y_coords,
    )


def spectra_to_image(values, x_coords, y_coords):
    """Convert one value per spectrum into a spatial image."""

    width = int(np.max(x_coords))
    height = int(np.max(y_coords))

    image = np.full((height, width), np.nan)

    for value, x, y in zip(values, x_coords, y_coords):
        image[int(y) - 1, int(x) - 1] = value

    return image


def save_mask_visualisation(mask, dataset, output_path):
    """Save a clean discrete segmentation mask."""

    cmap = ListedColormap(MASK_COLORS)

    fig, ax = plt.subplots(figsize=(10, 8))

    ax.imshow(
        mask,
        cmap=cmap,
        interpolation="nearest",
        vmin=0,
        vmax=2,
    )

    ax.set_title(f"{dataset} - Segmentation Mask", fontsize=18)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")

    legend_handles = [
        Patch(
            facecolor=MASK_COLORS[i],
            edgecolor="black",
            label=MASK_LABELS[i],
        )
        for i in range(3)
    ]

    ax.legend(
        handles=legend_handles,
        title="Segmentation",
        loc="upper right",
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def save_heatmap(
    image,
    dataset,
    title,
    colorbar_label,
    output_path,
):
    """Save a spatial heatmap."""

    fig, ax = plt.subplots(figsize=(10, 8))

    im = ax.imshow(
        image,
        interpolation="nearest",
    )

    ax.set_title(f"{dataset} - {title}", fontsize=18)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label(colorbar_label)

    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def save_ion_image(
    image,
    dataset,
    mz,
    index,
    output_path,
):
    """Save an ion image for one m/z value."""

    fig, ax = plt.subplots(figsize=(10, 8))

    im = ax.imshow(
        image,
        interpolation="nearest",
    )

    ax.set_title(
        f"{dataset} - Ion Image\n"
        f"m/z = {mz:.6f}  (index {index})",
        fontsize=18,
    )

    ax.set_xlabel("X")
    ax.set_ylabel("Y")

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Intensity")

    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


# ------------------------------------------------------------
# Main visualisation
# ------------------------------------------------------------

def visualise_dataset(dataset, data_dir, output_dir):

    print()
    print("=" * 60)
    print(f"VISUALISING {dataset}")
    print("=" * 60)

    imzml_path = os.path.join(
        data_dir,
        f"{dataset}.imzML",
    )

    mask_path = os.path.join(
        data_dir,
        "masks",
        f"{dataset}_mask.npy",
    )

    dataset_output = os.path.join(
        output_dir,
        dataset,
    )

    os.makedirs(dataset_output, exist_ok=True)

    if not os.path.exists(imzml_path):
        print(f"ERROR: Missing {imzml_path}")
        return

    if not os.path.exists(mask_path):
        print(f"ERROR: Missing {mask_path}")
        return

    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

    mask = np.load(mask_path)

    print(f"Mask file: {mask_path}")
    print(f"Mask shape: {mask.shape}")
    print(f"Mask classes: {np.unique(mask)}")

    (
        parser,
        spectra,
        mz_values,
        x_coords,
        y_coords,
    ) = load_spectra(imzml_path)

    print()
    print("=== DATA INFORMATION ===")

    print(f"Number of pixels: {len(spectra)}")
    print(f"Spectrum shape: {spectra.shape}")
    print(f"Number of m/z values: {len(mz_values)}")
    print(
        f"m/z range: "
        f"{mz_values.min():.4f} - "
        f"{mz_values.max():.4f}"
    )

    print(
        f"Coordinates x: "
        f"{x_coords.min()} - {x_coords.max()}"
    )

    print(
        f"Coordinates y: "
        f"{y_coords.min()} - {y_coords.max()}"
    )

    # --------------------------------------------------------
    # Mask
    # --------------------------------------------------------

    if mask.shape != (
        int(y_coords.max()),
        int(x_coords.max()),
    ):
        print()
        print("WARNING:")
        print(
            "Mask dimensions do not exactly match "
            "the MSI coordinate dimensions."
        )

    print()
    print("Saving segmentation mask...")

    save_mask_visualisation(
        mask,
        dataset,
        os.path.join(
            dataset_output,
            "mask.png",
        ),
    )

    # --------------------------------------------------------
    # Base peak intensity
    # --------------------------------------------------------

    print("Calculating base peak intensity...")

    base_peak = np.max(
        spectra,
        axis=1,
    )

    base_peak_image = spectra_to_image(
        base_peak,
        x_coords,
        y_coords,
    )

    save_heatmap(
        base_peak_image,
        dataset,
        "Base Peak Intensity",
        "Intensity",
        os.path.join(
            dataset_output,
            "base_peak.png",
        ),
    )

    # --------------------------------------------------------
    # Total ion current
    # --------------------------------------------------------

    print("Calculating total ion current...")

    tic = np.sum(
        spectra,
        axis=1,
    )

    tic_image = spectra_to_image(
        tic,
        x_coords,
        y_coords,
    )

    save_heatmap(
        tic_image,
        dataset,
        "Total Ion Current",
        "Total intensity",
        os.path.join(
            dataset_output,
            "tic.png",
        ),
    )

    # --------------------------------------------------------
    # Representative ion images
    # --------------------------------------------------------

    print("Creating representative ion images...")

    num_mz = len(mz_values)

    representative_indices = np.linspace(
        0,
        num_mz - 1,
        6,
        dtype=int,
    )

    ion_dir = os.path.join(
        dataset_output,
        "ion_images",
    )

    os.makedirs(
        ion_dir,
        exist_ok=True,
    )

    for index in representative_indices:

        mz = mz_values[index]

        ion_values = spectra[:, index]

        ion_image = spectra_to_image(
            ion_values,
            x_coords,
            y_coords,
        )

        save_ion_image(
            ion_image,
            dataset,
            mz,
            index,
            os.path.join(
                ion_dir,
                f"mz_{index:04d}_{mz:.4f}.png",
            ),
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=== VISUALISATION COMPLETE ===")

    print(
        f"Results saved to: {dataset_output}"
    )


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Visualise CAC MSI datasets."
        )
    )

    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help=(
            "Dataset name, e.g. 40TopL. "
            "If omitted, all CAC datasets are processed."
        ),
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Path to CAC dataset directory.",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Output directory.",
    )

    args = parser.parse_args()

    if args.dataset is not None:

        datasets = [args.dataset]

    else:

        datasets = sorted(
            filename.replace(
                ".imzML",
                "",
            )
            for filename in os.listdir(args.data_dir)
            if filename.endswith(".imzML")
        )

    print("=== CAC VISUALISATION ===")
    print(f"Dataset directory: {args.data_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"Datasets: {datasets}")

    for dataset in datasets:

        visualise_dataset(
            dataset,
            args.data_dir,
            args.output_dir,
        )

    print()
    print("=== ALL CAC VISUALISATIONS COMPLETE ===")


if __name__ == "__main__":
    main()