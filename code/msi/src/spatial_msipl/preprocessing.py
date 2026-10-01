"""TIC normalization and measured-neighbour context for Spatial-msiPL."""

from pathlib import Path

import h5py
import numpy as np


def square_neighbour_offsets(window_size=3):
    """Row-major odd square window, excluding the centre (1 gives no slots)."""
    if isinstance(window_size, bool) or not isinstance(window_size, (int, np.integer)):
        raise ValueError("window_size must be a positive odd integer")
    if window_size < 1 or window_size % 2 != 1:
        raise ValueError("window_size must be a positive odd integer")
    radius = int(window_size) // 2
    return tuple(
        (dx, dy)
        for dy in range(-radius, radius + 1)
        for dx in range(-radius, radius + 1)
        if not (dx == 0 and dy == 0)
    )


MOORE_OFFSETS = square_neighbour_offsets(3)


def tic_normalize(spectra):
    """Divide each spectrum by its total ion current; keep zero spectra zero."""
    values = np.asarray(spectra, dtype=np.float32)
    one_spectrum = values.ndim == 1
    if one_spectrum:
        values = values[None, :]
    if values.ndim != 2:
        raise ValueError("spectra must have shape (m/z,) or (spectra, m/z)")
    if not np.all(np.isfinite(values)):
        raise ValueError("spectra contain non-finite values")
    if np.any(values < 0):
        raise ValueError("spectra contain negative intensities")

    totals = values.sum(axis=1, keepdims=True, dtype=np.float64)
    normalized = np.zeros_like(values, dtype=np.float32)
    np.divide(values, totals, out=normalized, where=totals != 0)
    return normalized[0] if one_spectrum else normalized


def build_square_neighbour_slots(x_coordinates, y_coordinates, window_size=3):
    """Return measured indices in an odd window; -1 denotes a missing position."""
    offsets = square_neighbour_offsets(window_size)
    x = np.asarray(x_coordinates, dtype=np.int64).reshape(-1)
    y = np.asarray(y_coordinates, dtype=np.int64).reshape(-1)
    if len(x) == 0 or len(x) != len(y):
        raise ValueError("x and y must be non-empty arrays of equal length")
    if np.any(x < 1) or np.any(y < 1):
        raise ValueError("coordinates must be one-based positive integers")

    coordinate_to_index = {}
    for index, coordinate in enumerate(zip(x.tolist(), y.tolist())):
        if coordinate in coordinate_to_index:
            raise ValueError(f"duplicate measured coordinate: {coordinate}")
        coordinate_to_index[coordinate] = index

    slots = np.full((len(x), len(offsets)), -1, dtype=np.int64)
    for centre_x, centre_y in zip(x.tolist(), y.tolist()):
        centre_index = coordinate_to_index[(centre_x, centre_y)]
        for slot, (dx, dy) in enumerate(offsets):
            slots[centre_index, slot] = coordinate_to_index.get(
                (centre_x + dx, centre_y + dy), -1
            )
    return slots


def build_moore_neighbour_slots(x_coordinates, y_coordinates):
    """Backward-compatible eight-slot 3x3 interface."""
    return build_square_neighbour_slots(x_coordinates, y_coordinates, 3)


def build_moore_neighbours(x_coordinates, y_coordinates):
    """Return the valid measured neighbours for each centre (legacy interface)."""
    slots = build_moore_neighbour_slots(x_coordinates, y_coordinates)
    return tuple(row[row >= 0] for row in slots)


class H5SpatialContextDataset:
    """Stream central spectra and their mean measured-neighbour contexts from HDF5."""

    def __init__(self, path, include_neighbourhood=False, window_size=3):
        self.path = Path(path).expanduser().resolve()
        self.offsets = square_neighbour_offsets(window_size)
        self.window_size = int(window_size)
        self.include_neighbourhood = bool(include_neighbourhood)
        self._handle = None
        self._data = None

        with h5py.File(self.path, "r") as handle:
            required = ("Data", "mzArray", "xLocation", "yLocation")
            missing = [name for name in required if name not in handle]
            if missing:
                raise KeyError(f"missing HDF5 datasets: {missing}")
            self.data_shape = tuple(handle["Data"].shape)
            self.mz_values = np.asarray(handle["mzArray"], dtype=np.float32).reshape(-1)
            self.x = np.asarray(handle["xLocation"], dtype=np.int64).reshape(-1)
            self.y = np.asarray(handle["yLocation"], dtype=np.int64).reshape(-1)

        self.n_pixels = len(self.x)
        self.n_mz = len(self.mz_values)
        if self.data_shape == (self.n_mz, self.n_pixels):
            self.mz_first = True
        elif self.data_shape == (self.n_pixels, self.n_mz):
            self.mz_first = False
        else:
            raise ValueError(
                f"cannot orient Data shape {self.data_shape} for "
                f"{self.n_pixels} pixels and {self.n_mz} m/z bins"
            )
        if np.any(np.diff(self.mz_values) <= 0):
            raise ValueError("m/z values must be strictly increasing")

        self.neighbour_slots = build_square_neighbour_slots(self.x, self.y, self.window_size)
        self.neighbour_indices = tuple(
            row[row >= 0] for row in self.neighbour_slots
        )

    def __len__(self):
        return self.n_pixels

    def _ensure_open(self):
        if self._handle is None:
            self._handle = h5py.File(self.path, "r")
            self._data = self._handle["Data"]

    def _read_spectra(self, indices):
        """Read arbitrary pixel indices while satisfying h5py's sorted-index rule."""
        self._ensure_open()
        indices = np.asarray(indices, dtype=np.int64)
        order = np.argsort(indices)
        sorted_indices = indices[order]
        if self.mz_first:
            sorted_spectra = np.asarray(self._data[:, sorted_indices], dtype=np.float32).T
        else:
            sorted_spectra = np.asarray(self._data[sorted_indices, :], dtype=np.float32)
        inverse_order = np.argsort(order)
        return sorted_spectra[inverse_order]

    def __getitem__(self, index):
        if not 0 <= index < self.n_pixels:
            raise IndexError(index)
        slots = self.neighbour_slots[index]
        valid_mask = slots >= 0
        neighbours = slots[valid_mask]
        requested = np.concatenate(([index], neighbours))
        normalized = tic_normalize(self._read_spectra(requested))
        central = normalized[0]
        if len(neighbours):
            context = normalized[1:].mean(axis=0, dtype=np.float32)
        else:
            context = np.zeros(self.n_mz, dtype=np.float32)
        combined = np.concatenate((central, context)).astype(np.float32, copy=False)
        sample = {
            "input": combined,
            "target": central,
            "context": context,
            "index": np.int64(index),
            "x": np.int64(self.x[index]),
            "y": np.int64(self.y[index]),
            "neighbour_count": np.int64(len(neighbours)),
        }
        if self.include_neighbourhood:
            neighbour_spectra = np.zeros(
                (len(self.offsets), self.n_mz), dtype=np.float32
            )
            neighbour_spectra[valid_mask] = normalized[1:]
            sample["neighbours"] = neighbour_spectra
            sample["neighbour_mask"] = valid_mask
        return sample

    def close(self):
        if self._handle is not None:
            self._handle.close()
            self._handle = None
            self._data = None

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_handle"] = None
        state["_data"] = None
        return state

    def __del__(self):
        self.close()


class CachedH5SpatialContextDataset(H5SpatialContextDataset):
    """Use the existing sample logic with one in-memory float32 HDF5 read.

    This is opt-in for equivalence and speed testing; production training still
    uses ``H5SpatialContextDataset`` unless explicitly changed elsewhere.
    TIC normalization remains in the inherited ``__getitem__`` method so the
    numerical operation and neighbour construction are unchanged.
    """

    def __init__(self, path, include_neighbourhood=False, window_size=3):
        super().__init__(path, include_neighbourhood=include_neighbourhood, window_size=window_size)
        with h5py.File(self.path, "r") as handle:
            raw = handle["Data"][...]
        oriented = raw.T if self.mz_first else raw
        self._spectra = np.ascontiguousarray(oriented, dtype=np.float32)

    def _read_spectra(self, indices):
        # NumPy preserves the requested order, including repeated indices.
        return self._spectra[np.asarray(indices, dtype=np.int64)]
