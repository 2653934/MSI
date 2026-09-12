"""Small numerical tests for the Spatial-msiPL data contract."""

import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np

from spatial_msipl.preprocessing import H5SpatialContextDataset, tic_normalize


class PreprocessingTests(unittest.TestCase):
    def test_tic_normalization_and_zero_spectrum(self):
        spectra = np.asarray([[1, 1, 2], [0, 0, 0]], dtype=np.float32)
        actual = tic_normalize(spectra)
        np.testing.assert_allclose(actual[0], [0.25, 0.25, 0.5])
        np.testing.assert_array_equal(actual[1], [0, 0, 0])

    def test_measured_neighbours_boundaries_and_shapes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "tiny.h5"
            # A 3x3 grid with the centre missing. The top-left pixel therefore
            # has only two measured neighbours: (2,1) and (1,2).
            coordinates = [
                (1, 1), (2, 1), (3, 1),
                (1, 2),         (3, 2),
                (1, 3), (2, 3), (3, 3),
            ]
            spectra = np.asarray(
                [[index + 1, 1, 2] for index in range(len(coordinates))],
                dtype=np.float32,
            )
            with h5py.File(path, "w") as handle:
                handle.create_dataset("Data", data=spectra.T)
                handle.create_dataset("mzArray", data=[100, 101, 102])
                handle.create_dataset("xLocation", data=[x for x, _ in coordinates])
                handle.create_dataset("yLocation", data=[y for _, y in coordinates])

            dataset = H5SpatialContextDataset(path)
            sample = dataset[0]
            expected = tic_normalize(spectra[[1, 3]]).mean(axis=0)

            self.assertEqual(len(dataset), 8)
            self.assertEqual(sample["neighbour_count"], 2)
            self.assertEqual(sample["input"].shape, (6,))
            self.assertEqual(sample["target"].shape, (3,))
            self.assertEqual(sample["context"].shape, (3,))
            self.assertAlmostEqual(float(sample["target"].sum()), 1.0, places=6)
            np.testing.assert_allclose(sample["context"], expected, rtol=1e-6)
            dataset.close()


if __name__ == "__main__":
    unittest.main()
