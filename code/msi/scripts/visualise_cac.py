import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from pyimzml.ImzMLParser import ImzMLParser


def load_cac_data(imzml_path, mask_path):
    """Load spectra, coordinates, and segmentation mask."""

    print(f"Loading MSI file: {imzml_path}")
    parser = ImzMLParser(str(imzml_path))

    mask = np.load(mask_path)

    print(f"Mask file: {mask_path}")
    print(f"Mask shape: {mask.shape}")
    print(f"Mask classes: {np.unique(mask)}")

    spectra = []
    coordinates = []

    for idx, (x, y, z) in enumerate(parser.coordinates):
        mzs, intensities = parser.getspectrum(idx)

        spectra.append(intensities)
        coordinates.append((x, y, z))

    spectra = np.asarray(spectra)
    coordinates = np.asarray(coordinates)

    # m/z values are shared across the continuous imzML file.
    mz_values, _ = parser.getspectrum(0)
    mz_values = np.asarray(mz_values)

    print()
    print("=== DATA INFORMATION ===")
    print(f"Number of pixels: {len(coordinates)}")
    print(f"Spectrum shape: {spectra.shape}")
    print(f"Number of m/z values: {len(mz_values)}")
    print(f"m/z range: {mz_values.min():.4f} - {mz_values.max():.4f}")
    print(f"Coordinates x: {coordinates[:, 0].min()} - {coordinates[:, 0].max()}")
    print(f"Coordinates y: {coordinates[:, 1].min()} - {coordinates[:, 1].max()}")

    return parser, mz_values, spectra, coordinates, mask


def create_image(values, coordinates, image_shape):
    """Place one value at each MSI spatial coordinate."""

    image = np.full(image_shape, np.nan, dtype=float)

    for value, (x, y, _) in zip(values, coordinates):
        image[y - 1, x - 1] = value

    return image


def save_image(
    image,
    output_path,
    title,
    cmap="viridis",
    colorbar_label=None,
    vmin=None,
    vmax=None,
):
    """Save a single image."""

    plt.figure(figsize=(8, 6))

    plt.imshow(
        image,
        cmap=cmap,
        interpolation="nearest",
        vmin=vmin,
        vmax=vmax,
    )

    plt.title(title)
    plt.xlabel("X")
    plt.ylabel("Y")

    cbar = plt.colorbar()

    if colorbar_label:
        cbar.set_label(colorbar_label)

    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Visualise CAC MSI data, segmentation masks, and ion images."
    )

    parser.add_argument(
        "--dataset",
        default="40TopL",
        help="CAC dataset name, e.g. 40TopL",
    )

    parser.add_argument(
        "--data-dir",
        default="/datasets/zsuliman/msi_data/cac",
        help="Directory containing CAC .imzML and .ibd files.",
    )

    parser.add_argument(
        "--output-dir",
        default="results/visualisations/cac",
        help="Directory where visualisations will be saved.",
    )

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir) / args.dataset

    output_dir.mkdir(parents=True, exist_ok=True)

    imzml_path = data_dir / f"{args.dataset}.imzML"
    mask_path = data_dir / "masks" / f"{args.dataset}_mask.npy"

    if not imzml_path.exists():
        raise FileNotFoundError(f"MSI file not found: {imzml_path}")

    if not mask_path.exists():
        raise FileNotFoundError(f"Mask file not found: {mask_path}")

    print("=== CAC VISUALISATION ===")
    print(f"Dataset: {args.dataset}")
    print(f"Output directory: {output_dir}")
    print()

    (
        parser,
        mz_values,
        spectra,
        coordinates,
        mask,
    ) = load_cac_data(imzml_path, mask_path)

    # ---------------------------------------------------------
    # Determine spatial dimensions
    # ---------------------------------------------------------

    height, width = mask.shape

    print()
    print("=== SPATIAL INFORMATION ===")
    print(f"Image dimensions: {width} x {height}")
    print(f"Pixels in mask: {height * width}")
    print(f"Spectra available: {len(spectra)}")

    # ---------------------------------------------------------
    # 1. Segmentation mask
    # ---------------------------------------------------------

    save_image(
        mask,
        output_dir / "mask.png",
        f"{args.dataset} - Segmentation Mask",
        cmap="tab10",
        colorbar_label="Class",
        vmin=0,
        vmax=2,
    )

    # ---------------------------------------------------------
    # 2. Total Ion Current (TIC)
    # ---------------------------------------------------------

    tic = np.sum(spectra, axis=1)

    tic_image = create_image(
        tic,
        coordinates,
        mask.shape,
    )

    save_image(
        tic_image,
        output_dir / "tic.png",
        f"{args.dataset} - Total Ion Current",
        cmap="viridis",
        colorbar_label="Total ion intensity",
    )

    # ---------------------------------------------------------
    # 3. Base peak intensity
    # ---------------------------------------------------------

    base_peak = np.max(spectra, axis=1)

    base_peak_image = create_image(
        base_peak,
        coordinates,
        mask.shape,
    )

    save_image(
        base_peak_image,
        output_dir / "base_peak_intensity.png",
        f"{args.dataset} - Base Peak Intensity",
        cmap="viridis",
        colorbar_label="Intensity",
    )

    # ---------------------------------------------------------
    # 4. Representative m/z ion images
    # ---------------------------------------------------------

    print()
    print("=== REPRESENTATIVE m/z VALUES ===")

    # Choose several evenly spaced m/z indices.
    num_ion_images = 6

    mz_indices = np.linspace(
        0,
        len(mz_values) - 1,
        num=num_ion_images,
        dtype=int,
    )

    for index in mz_indices:
        mz = mz_values[index]

        ion_image = create_image(
            spectra[:, index],
            coordinates,
            mask.shape,
        )

        filename = f"ion_mz_{mz:.4f}.png"

        print(
            f"Index {index}: "
            f"m/z = {mz:.6f}"
        )

        save_image(
            ion_image,
            output_dir / filename,
            f"{args.dataset} - m/z {mz:.4f}",
            cmap="viridis",
            colorbar_label="Intensity",
        )

    # ---------------------------------------------------------
    # 5. Save metadata
    # ---------------------------------------------------------

    metadata_path = output_dir / "metadata.txt"

    with open(metadata_path, "w") as f:
        f.write(f"Dataset: {args.dataset}\n")
        f.write(f"MSI file: {imzml_path}\n")
        f.write(f"Mask file: {mask_path}\n")
        f.write(f"Mask shape: {mask.shape}\n")
        f.write(f"Number of pixels: {len(coordinates)}\n")
        f.write(f"Number of m/z values: {len(mz_values)}\n")
        f.write(f"m/z minimum: {mz_values.min()}\n")
        f.write(f"m/z maximum: {mz_values.max()}\n")
        f.write(f"Coordinate X range: {coordinates[:, 0].min()} - {coordinates[:, 0].max()}\n")
        f.write(f"Coordinate Y range: {coordinates[:, 1].min()} - {coordinates[:, 1].max()}\n")

        f.write("\nClass distribution:\n")

        unique, counts = np.unique(mask, return_counts=True)

        for class_value, count in zip(unique, counts):
            percentage = count / mask.size * 100

            f.write(
                f"Class {class_value}: "
                f"{count} pixels "
                f"({percentage:.2f}%)\n"
            )

    print()
    print("=== VISUALISATION COMPLETE ===")
    print(f"Results saved to: {output_dir}")


if __name__ == "__main__":
    main()