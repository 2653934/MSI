"""Small numerical tests for the Spatial-msiPL data contract."""

import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np

from spatial_msipl.preprocessing import (
    CachedH5SpatialContextDataset,
    H5SpatialContextDataset,
    tic_normalize,
)


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

            neighbourhood_dataset = H5SpatialContextDataset(
                path, include_neighbourhood=True
            )
            neighbourhood_sample = neighbourhood_dataset[0]
            self.assertEqual(neighbourhood_sample["neighbours"].shape, (8, 3))
            self.assertEqual(neighbourhood_sample["neighbour_mask"].shape, (8,))
            self.assertEqual(int(neighbourhood_sample["neighbour_mask"].sum()), 2)
            # For the top-left centre, right and below are slots 4 and 6 in the
            # documented row-major Moore ordering.
            self.assertTrue(neighbourhood_sample["neighbour_mask"][[4, 6]].all())
            np.testing.assert_allclose(
                neighbourhood_sample["neighbours"][[4, 6]],
                tic_normalize(spectra[[1, 3]]),
                rtol=1e-6,
            )
            neighbourhood_dataset.close()

    def test_cached_loader_exactly_matches_streaming_loader(self):
        coordinates = [
            (1, 1), (2, 1), (3, 1),
            (1, 2),         (3, 2),
            (1, 3), (2, 3), (3, 3),
        ]
        spectra = np.asarray(
            [[index + 1.25, index + 0.5, 2.75] for index in range(8)],
            dtype=np.float64,
        )
        spectra[4] = 0  # Zero-TIC handling must also remain identical.
        for mz_first in (True, False):
            for include_neighbourhood in (True, False):
                with self.subTest(mz_first=mz_first, neighbourhood=include_neighbourhood):
                    with tempfile.TemporaryDirectory() as temporary_directory:
                        path = Path(temporary_directory) / "tiny.h5"
                        data = spectra.T if mz_first else spectra
                        with h5py.File(path, "w") as handle:
                            handle.create_dataset("Data", data=data, chunks=data.shape)
                            handle.create_dataset("mzArray", data=[100, 101, 102])
                            handle.create_dataset(
                                "xLocation", data=[x for x, _ in coordinates]
                            )
                            handle.create_dataset(
                                "yLocation", data=[y for _, y in coordinates]
                            )
                        streaming = H5SpatialContextDataset(
                            path, include_neighbourhood=include_neighbourhood
                        )
                        cached = CachedH5SpatialContextDataset(
                            path, include_neighbourhood=include_neighbourhood
                        )
                        try:
                            for index in range(len(streaming)):
                                reference = streaming[index]
                                candidate = cached[index]
                                self.assertEqual(reference.keys(), candidate.keys())
                                for key in reference:
                                    np.testing.assert_array_equal(
                                        reference[key], candidate[key],
                                        err_msg=f"index={index}, key={key}",
                                    )
                        finally:
                            streaming.close()
                            cached.close()


if __name__ == "__main__":
    unittest.main()
