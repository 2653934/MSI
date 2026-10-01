"""TIC normalization and measured-neighbour context for Spatial-msiPL."""

import hashlib
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


def checkpoint_input_spec(checkpoint):
    """Recover the exact dataset inputs required by a saved model run."""
    configuration = checkpoint["model_configuration"]
    signature = checkpoint.get("resume_signature", {})
    window_size = int(signature.get("dataset_window_size", configuration.get("window_size", 3)))
    square_neighbour_offsets(window_size)
    if "neighbourhood" in configuration and int(configuration.get("window_size", 3)) != window_size:
        raise ValueError("checkpoint model and dataset window sizes disagree")
    context_mode = signature.get("context_mode", "measured")
    if context_mode not in ("measured", "shuffled"):
        raise ValueError(f"unsupported checkpoint context mode: {context_mode}")
    if context_mode == "shuffled" and "context_seed" not in signature:
        raise ValueError("shuffled checkpoint lacks its context seed")
    return {
        "window_size": window_size,
        "context_mode": context_mode,
        "context_seed": signature.get("context_seed"),
        "context_permutation_sha256": signature.get("context_permutation_sha256"),
    }


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

    def __init__(self, path, include_neighbourhood=False, window_size=3,
                 context_mode="measured", context_seed=None):
        self.path = Path(path).expanduser().resolve()
        self.offsets = square_neighbour_offsets(window_size)
        self.window_size = int(window_size)
        if context_mode not in ("measured", "shuffled"):
            raise ValueError("context_mode must be measured or shuffled")
        if context_mode == "shuffled" and (isinstance(context_seed, bool) or
                                             not isinstance(context_seed, (int, np.integer))):
            raise ValueError("shuffled context requires an integer context_seed")
        self.context_mode = context_mode
        self.context_seed = int(context_seed) if context_mode == "shuffled" else None
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
        self.context_permutation = None
        self.context_permutation_sha256 = None
        if self.context_mode == "shuffled":
            # Map every measured index to another measured index. A cyclic shift
            # of a seeded random ordering has no fixed points when N > 1.
            order = np.random.default_rng(self.context_seed).permutation(self.n_pixels)
            mapping = np.empty(self.n_pixels, dtype=np.int64)
            mapping[order] = np.roll(order, 1)
            self.context_permutation = mapping
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
        self.context_source_slots = None
        if self.context_mode == "shuffled":
            sources = self.neighbour_slots.copy()
            for index, row in enumerate(self.neighbour_slots):
                forbidden = set(row[row >= 0].tolist()) | {index}
                if len(forbidden) == self.n_pixels and np.any(row >= 0):
                    raise ValueError("shuffled context needs a measured pixel outside every local window")
                for slot, neighbour in enumerate(row):
                    if neighbour < 0:
                        continue
                    candidate = self.context_permutation[neighbour]
                    while candidate in forbidden:
                        candidate = self.context_permutation[candidate]
                    sources[index, slot] = candidate
            self.context_source_slots = sources
            self.context_permutation_sha256 = hashlib.sha256(
                sources.astype("<i8", copy=False).tobytes()
            ).hexdigest()

    def __len__(self):
        return self.n_pixels

    def _ensure_open(self):
        if self._handle is None:
            self._handle = h5py.File(self.path, "r")
            self._data = self._handle["Data"]

    def _read_spectra(self, indices):
        """Read arbitrary indices, including repeated shuffled sources, in order."""
        self._ensure_open()
        indices = np.asarray(indices, dtype=np.int64)
        if self.context_mode == "measured":
            # Keep the historical 3x3/5x5 read path unchanged. Measured slots
            # are unique, whereas shuffled slots may repeat a source index.
            order = np.argsort(indices)
            sorted_indices = indices[order]
            if self.mz_first:
                sorted_spectra = np.asarray(self._data[:, sorted_indices], dtype=np.float32).T
            else:
                sorted_spectra = np.asarray(self._data[sorted_indices, :], dtype=np.float32)
            return sorted_spectra[np.argsort(order)]
        unique_indices, reconstruction = np.unique(indices, return_inverse=True)
        if self.mz_first:
            unique_spectra = np.asarray(self._data[:, unique_indices], dtype=np.float32).T
        else:
            unique_spectra = np.asarray(self._data[unique_indices, :], dtype=np.float32)
        return unique_spectra[reconstruction]

    def __getitem__(self, index):
        if not 0 <= index < self.n_pixels:
            raise IndexError(index)
        slots = self.neighbour_slots[index]
        valid_mask = slots >= 0
        neighbours = slots[valid_mask]
        source_neighbours = (
            self.context_source_slots[index][valid_mask]
            if self.context_mode == "shuffled" else neighbours
        )
        requested = np.concatenate(([index], source_neighbours))
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

    def __init__(self, path, include_neighbourhood=False, window_size=3,
                 context_mode="measured", context_seed=None):
        super().__init__(path, include_neighbourhood=include_neighbourhood,
                         window_size=window_size, context_mode=context_mode,
                         context_seed=context_seed)
        with h5py.File(self.path, "r") as handle:
            raw = handle["Data"][...]
        oriented = raw.T if self.mz_first else raw
        self._spectra = np.ascontiguousarray(oriented, dtype=np.float32)

    def _read_spectra(self, indices):
        # NumPy preserves the requested order, including repeated indices.
        return self._spectra[np.asarray(indices, dtype=np.int64)]
