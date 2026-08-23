"""Shared MSI data access for imzML and MassNet HDF5 inputs."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np


HDF5_SUFFIXES = {".h5", ".hdf5"}


@dataclass
class SpectrumTable:
    """Spectra and spatial metadata in a format independent of the source file."""

    spectra: np.ndarray
    mz_values: np.ndarray
    x: np.ndarray
    y: np.ndarray


def _validate_coordinates(path, x, y, n_pixels):
    if len(x) != n_pixels or len(y) != n_pixels:
        raise ValueError(
            f"{path}: coordinate lengths do not match the number of spectra: "
            f"spectra={n_pixels}, x={len(x)}, y={len(y)}"
        )
    if n_pixels == 0:
        raise ValueError(f"{path}: contains no spectra")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError(f"{path}: coordinates contain non-finite values")
    if not np.all(x == np.rint(x)) or not np.all(y == np.rint(y)):
        raise ValueError(f"{path}: coordinates must be integers")

    x = x.astype(np.int32, copy=False)
    y = y.astype(np.int32, copy=False)
    if np.any(x < 1) or np.any(y < 1):
        raise ValueError(f"{path}: coordinates must be one-based and positive")

    coordinates = np.column_stack((x, y))
    if len(np.unique(coordinates, axis=0)) != n_pixels:
        raise ValueError(f"{path}: duplicate spatial coordinates found")
    return x, y


def load_massnet_h5(path):
    """Load a MassNet file and orient its data as (pixels, m/z)."""
    import h5py

    path = Path(path)
    with h5py.File(path, "r") as handle:
        required = ("Data", "mzArray", "xLocation", "yLocation")
        missing = [name for name in required if name not in handle]
        if missing:
            raise KeyError(f"{path}: missing HDF5 datasets {missing}")

        mz_values = np.asarray(handle["mzArray"], dtype=np.float32).reshape(-1)
        x = np.asarray(handle["xLocation"]).reshape(-1)
        y = np.asarray(handle["yLocation"]).reshape(-1)
        data = np.asarray(handle["Data"], dtype=np.float32)

    n_pixels = len(x)
    n_mz = len(mz_values)
    pixels_by_mz = data.shape == (n_pixels, n_mz)
    mz_by_pixels = data.shape == (n_mz, n_pixels)
    if pixels_by_mz and mz_by_pixels:
        raise ValueError(
            f"{path}: square Data shape {data.shape} is ambiguous; "
            "pixel and m/z dimensions cannot be distinguished"
        )
    if pixels_by_mz:
        spectra = data
    elif mz_by_pixels:
        spectra = data.T
    else:
        raise ValueError(
            f"{path}: cannot orient Data shape {data.shape}; expected "
            f"({n_pixels}, {n_mz}) or ({n_mz}, {n_pixels})"
        )

    if n_mz == 0:
        raise ValueError(f"{path}: contains an empty mzArray")
    if not np.all(np.isfinite(mz_values)):
        raise ValueError(f"{path}: mzArray contains non-finite values")
    if np.any(np.diff(mz_values) <= 0):
        raise ValueError(f"{path}: mzArray must be strictly increasing")

    x, y = _validate_coordinates(path, x, y, len(spectra))
    return SpectrumTable(spectra=spectra, mz_values=mz_values, x=x, y=y)


def load_imzml_table(path):
    """Load continuous-profile imzML spectra for evaluation helpers."""
    from pyimzml.ImzMLParser import ImzMLParser

    path = Path(path)
    parser = ImzMLParser(str(path))
    spectra = []
    x = []
    y = []
    mz_values = None

    for index, (x_coord, y_coord, _z_coord) in enumerate(parser.coordinates):
        mz, intensities = parser.getspectrum(index)
        if mz_values is None:
            mz_values = np.asarray(mz)
        elif len(mz) != len(mz_values) or not np.array_equal(mz, mz_values):
            raise ValueError(
                f"{path}: S3PL requires a shared continuous m/z axis"
            )
        spectra.append(np.asarray(intensities, dtype=np.float32))
        x.append(x_coord)
        y.append(y_coord)

    if mz_values is None:
        raise ValueError(f"{path}: contains no spectra")

    spectra = np.stack(spectra)
    x, y = _validate_coordinates(path, np.asarray(x), np.asarray(y), len(spectra))
    return SpectrumTable(
        spectra=spectra,
        mz_values=np.asarray(mz_values),
        x=x,
        y=y,
    )


def load_spectrum_table(path):
    """Load spectra and coordinates for format-independent evaluation."""
    path = Path(path).expanduser().resolve()
    if path.suffix.lower() in HDF5_SUFFIXES:
        return load_massnet_h5(path)
    if path.suffix.lower() == ".imzml":
        return load_imzml_table(path)
    raise ValueError(f"Unsupported MSI input format: {path.suffix}")


class H5SpectrumPatchDataset:
    """Create S3PL spatial patches centred only on measured HDF5 pixels."""

    def __init__(self, table, patch_size, transform=None):
        if patch_size < 1 or patch_size % 2 == 0:
            raise ValueError("spectral patch size must be a positive odd integer")

        self.spectra = table.spectra
        self.mz_values = table.mz_values
        self.x = table.x
        self.y = table.y
        self.patch_size = patch_size
        self.transform = transform

        index_grid = np.full(
            (int(self.y.max()), int(self.x.max())), -1, dtype=np.int32
        )
        index_grid[self.y - 1, self.x - 1] = np.arange(len(self.x), dtype=np.int32)

        radius = patch_size // 2
        padded = np.pad(index_grid, radius, constant_values=-1)
        windows = np.lib.stride_tricks.sliding_window_view(
            padded, (patch_size, patch_size)
        )
        self.patch_indices = windows[self.y - 1, self.x - 1].reshape(
            len(self.x), -1
        )

    def __len__(self):
        return len(self.x)

    def __getitem__(self, index):
        neighbour_indices = self.patch_indices[index]
        measured = neighbour_indices >= 0
        patch = np.zeros(
            (1, len(self.mz_values), self.patch_size, self.patch_size),
            dtype=np.float32,
        )
        patch.reshape(len(self.mz_values), -1)[:, measured] = self.spectra[
            neighbour_indices[measured]
        ].T

        if self.transform is not None:
            patch = self.transform(patch)
        return patch, index


def build_patch_dataset(path, patch_size, transform=None):
    """Build the reference imzML dataset or the compatible HDF5 dataset."""
    path = Path(path).expanduser().resolve()
    if path.suffix.lower() in HDF5_SUFFIXES:
        table = load_massnet_h5(path)
        return H5SpectrumPatchDataset(table, patch_size, transform), table.mz_values

    if path.suffix.lower() == ".imzml":
        import m2aia as m2

        image = m2.ImzMLReader(str(path))
        dataset = m2.SpectrumDataset(
            [image],
            shape=(patch_size, patch_size),
            buffer_type="memory",
            transform_data=transform,
        )
        return dataset, np.asarray(image.GetXAxis())

    raise ValueError(f"Unsupported MSI input format: {path.suffix}")
