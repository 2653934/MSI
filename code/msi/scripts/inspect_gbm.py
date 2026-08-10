from pathlib import Path

import h5py


GBM_DIR = Path("/datasets/zsuliman/msi_data/gbm")


def show_item(name, obj):
    if isinstance(obj, h5py.Dataset):
        print(
            f"{name}: "
            f"shape={obj.shape}, "
            f"dtype={obj.dtype}"
        )
    elif isinstance(obj, h5py.Group):
        print(f"{name}/")


def main():
    print("=== GBM DATASET INSPECTION ===")
    print(f"Dataset directory: {GBM_DIR}")
    print()

    files = sorted(GBM_DIR.glob("*.h5"))

    if not files:
        print("No HDF5 files found.")
        return

    for path in files:
        print(f"========== {path.name} ==========")

        with h5py.File(path, "r") as f:
            print(f"Root keys: {list(f.keys())}")
            print()

            f.visititems(show_item)

        print()


if __name__ == "__main__":
    main()