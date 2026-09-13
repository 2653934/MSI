"""Tests for leakage-resistant spatial evaluation helpers."""

import unittest

import numpy as np

from spatial_msipl.evaluation import morans_i, spatial_tile_folds
from spatial_msipl.preprocessing import build_moore_neighbour_slots


class SpatialEvaluationTests(unittest.TestCase):
    def test_tiles_cover_each_pixel_once_and_exclude_immediate_halo(self):
        x, y = np.meshgrid(np.arange(1, 9), np.arange(1, 9))
        x = x.reshape(-1)
        y = y.reshape(-1)
        folds = spatial_tile_folds(x, y, rows=2, columns=2, halo=1)

        tested = np.concatenate([fold["test"] for fold in folds])
        np.testing.assert_array_equal(np.sort(tested), np.arange(len(x)))
        coordinates = np.column_stack((x, y))
        for fold in folds:
            test_coordinates = coordinates[fold["test"]]
            for train_index in fold["train"]:
                distances = np.max(
                    np.abs(test_coordinates - coordinates[train_index]), axis=1
                )
                self.assertTrue(np.all(distances > 1))

    def test_morans_i_is_positive_for_a_smooth_spatial_gradient(self):
        x, y = np.meshgrid(np.arange(1, 6), np.arange(1, 6))
        x = x.reshape(-1)
        y = y.reshape(-1)
        neighbours = build_moore_neighbour_slots(x, y)
        self.assertGreater(morans_i(x.astype(float), neighbours), 0.5)

    def test_morans_i_is_undefined_for_constant_values(self):
        neighbours = np.asarray([[1], [0]])
        self.assertTrue(np.isnan(morans_i([1.0, 1.0], neighbours)))


if __name__ == "__main__":
    unittest.main()
