"""Test N: S3PL patches with shuffled nonlocal neighbours (protocol 18 Section 6.5).

Every non-central position of a p x p patch is replaced by the spectrum of a
nonlocal measured pixel; the central position is left exactly as the released
code builds it. The source of a neighbour j of pixel i follows the VAE
``shuffled_p3`` construction (src/spatial_msipl/preprocessing.py,
``H5SpatialContextDataset`` with ``context_mode="shuffled"``):

- a fixed global map of the measured pixels, ``mapping[order] = roll(order, 1)``
  with ``order = default_rng(seed).permutation(n)``: one n-cycle, so no pixel
  maps to itself;
- ``source = mapping[j]``, advanced along the map while it lies in the pixel's
  own window (its measured window pixels, and i itself), so every source is
  nonlocal. For S3PL the window is the p x p patch.

The map uses its own generator and draws nothing from the global NumPy RNG, so
the released code's random fill of unmeasured positions (m2aia) sees exactly the
same random stream as the real run.
"""

import numpy as np

NONLOCAL_SHUFFLE_SEED = 1701


def nonlocal_map(n, seed=NONLOCAL_SHUFFLE_SEED):
    """The VAE shuffled-context map over n measured pixels (positions 0..n-1)."""
    if n < 2:
        raise ValueError("a nonlocal shuffle needs at least two measured pixels")
    order = np.random.default_rng(seed).permutation(n)
    mapping = np.empty(n, dtype=np.int64)
    mapping[order] = np.roll(order, 1)
    return mapping


def nonlocal_source(mapping, neighbour, forbidden):
    """Follow the map from ``mapping[neighbour]`` until it leaves ``forbidden``."""
    if len(forbidden) >= len(mapping):
        raise ValueError("no measured pixel lies outside the window")
    candidate = int(mapping[neighbour])
    while candidate in forbidden:
        candidate = int(mapping[candidate])
    return candidate


def shuffle_patch_indices(patch_indices, centre_slot, forbidden, mapping):
    """Replace every non-central measured index; -1 (unmeasured) stays -1."""
    shuffled = np.array(patch_indices, dtype=np.int64, copy=True)
    for slot, neighbour in enumerate(shuffled):
        if slot != centre_slot and neighbour >= 0:
            shuffled[slot] = nonlocal_source(mapping, int(neighbour), forbidden)
    return shuffled


class NonlocalShuffleM2aiaMixin:
    """Mixin for ``m2aia.SpectrumDataset`` (shape (p, p), memory buffer, full spectra).

    ``getitems`` builds the real patch through the parent class, re-derives the
    parent's index list (same global RNG draws, then the RNG state is restored so
    the parent draws them again), checks that those indices reproduce the parent's
    patch exactly, and returns the patch built from the shuffled indices. The
    data transform is applied afterwards, as the parent would.
    """

    def _init_nonlocal(self, seed=NONLOCAL_SHUFFLE_SEED):
        if len(self.images) != 1 or self.spectrum_mask_indices is not None:
            raise ValueError("the nonlocal shuffle supports one image and full spectra")
        if not self.shape or len(self.shape) != 2 or self.shape[0] != self.shape[1]:
            raise ValueError("the nonlocal shuffle needs a square patch shape")
        measured = np.asarray(sorted(e[1] for e in self.elements), dtype=np.int64)
        self._position = {int(s): k for k, s in enumerate(measured)}
        self._measured = measured
        self._mapping = nonlocal_map(len(measured), seed)
        self._centre_slot = (self.shape[0] * self.shape[1]) // 2
        self.nonlocal_seed = seed

    def _real_indices(self, index):
        """The parent's index list for one element (draws from the global RNG)."""
        image_id, spectrum_id, (x, y, _z), _label = self.elements[index]
        image_shape = self.images[image_id].GetShape()
        left = np.clip(x - self.x_hws, 0, image_shape[0])
        right = np.clip(x + self.x_hws + 1, 0, image_shape[0])
        bottom = np.clip(y - self.y_hws, 0, image_shape[1])
        top = np.clip(y + self.y_hws + 1, 0, image_shape[1])
        indices = self.index_images[image_id][0, bottom:top, left:right].flatten()
        window = set(int(i) for i in indices[indices >= 0]) | {int(spectrum_id)}
        if any(indices < 0):
            choices = np.random.choice(indices[indices >= 0], len(indices[indices < 0]))
            indices[indices < 0] = choices
        expected = (2 * self.x_hws + 1) * (2 * self.y_hws + 1)
        if len(indices) < expected:
            indices = np.concatenate([indices, np.random.choice(indices, expected - len(indices))])
        return np.asarray(indices, dtype=np.int64), window

    def _spectra(self, indices):
        """Spectra through the parent's memory buffer, loading misses as it does."""
        indices = np.asarray(indices, dtype=np.int32)
        buffered, data = self.buffer[0]
        missing = indices[~buffered[indices]]
        if len(missing):
            data[missing] = self.images[0].GetSpectra(missing).astype(np.float32)
            buffered[missing] = True
        return data[indices]

    def _assemble(self, indices):
        spectra = self._spectra(indices)
        data = np.reshape(spectra, (-1,) + tuple(self.shape) + (self.spectrum_depth,))
        return np.swapaxes(data, 1, 3)

    def _shuffled(self, indices, window):
        forbidden = {self._position[s] for s in window}
        positions = np.array([self._position[int(s)] for s in indices], dtype=np.int64)
        shuffled = shuffle_patch_indices(positions, self._centre_slot, forbidden, self._mapping)
        return self._measured[shuffled]

    def getitems(self, dataset_query_indices):
        transform, self.transform_data = self.transform_data, None
        try:
            real_parts, shuffled_parts, labels = [], [], []
            for index in dataset_query_indices:
                state = np.random.get_state()
                indices, window = self._real_indices(index)
                np.random.set_state(state)
                real, label = super().getitems([index])
                rebuilt = self._assemble(indices)
                if not np.array_equal(real, rebuilt):
                    raise RuntimeError("re-derived patch indices do not reproduce m2aia's patch")
                shuffled_parts.append(self._assemble(self._shuffled(indices, window)))
                real_parts.append(real)
                labels.append(label)
        finally:
            self.transform_data = transform
        data = np.concatenate(shuffled_parts)
        if self.transform_data is not None:
            data = self.transform_data(data)
        return data, np.concatenate(labels)


def nonlocal_spectrum_dataset(image, shape, transform, seed=NONLOCAL_SHUFFLE_SEED):
    """An m2aia SpectrumDataset whose patches carry shuffled nonlocal neighbours."""
    import m2aia as m2

    class NonlocalShuffledSpectrumDataset(NonlocalShuffleM2aiaMixin, m2.SpectrumDataset):
        pass

    dataset = NonlocalShuffledSpectrumDataset([image], shape=shape, buffer_type="memory",
                                              transform_data=transform)
    dataset._init_nonlocal(seed)
    return dataset
