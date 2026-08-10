from pathlib import Path

import numpy as np


MASK_DIR = Path("/datasets/zsuliman/msi_data/cac/masks")


def main():
    print("=== CAC MASK INSPECTION ===")
    print(f"Mask directory: {MASK_DIR}")
    print()

    mask_files = sorted(MASK_DIR.glob("*_mask.npy"))

    if not mask_files:
        print("No mask files found.")
        return

    for path in mask_files:
        mask = np.load(path)

        values, counts = np.unique(mask, return_counts=True)

        print(f"--- {path.name} ---")
        print(f"Shape: {mask.shape}")
        print(f"Dtype: {mask.dtype}")
        print(f"Total pixels: {mask.size}")
        print()

        print("Class distribution:")

        for value, count in zip(values, counts):
            percentage = (count / mask.size) * 100

            print(
                f"  Class {value}: "
                f"{count} pixels "
                f"({percentage:.2f}%)"
            )

        print()


if __name__ == "__main__":
    main()