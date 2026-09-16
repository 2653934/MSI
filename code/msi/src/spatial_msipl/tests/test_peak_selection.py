"""Tests for matched-count and peak-window selection."""

import unittest

import numpy as np

from spatial_msipl.peak_selection import (
    balanced_round_robin_rankings,
    ppm_nonmaximum_suppression,
)


class PeakSelectionTests(unittest.TestCase):
    def test_round_robin_is_balanced_unique_and_deterministic(self):
        rankings = {
            0: np.array([4, 2, 1, 0]),
            1: np.array([4, 3, 2, 5]),
        }
        selected, sources = balanced_round_robin_rankings(rankings, 5)
        np.testing.assert_array_equal(selected, np.array([4, 3, 2, 5, 1]))
        np.testing.assert_array_equal(sources, np.array([0, 1, 0, 1, 0]))
        self.assertEqual(len(set(selected.tolist())), 5)

    def test_ppm_suppression_keeps_highest_ranked_representative(self):
        mz = np.array([500.0000, 500.0030, 500.0200, 700.0000])
        # At 500 m/z, 10 ppm is 0.005 m/z: bins 0 and 1 form one window.
        selected = ppm_nonmaximum_suppression(
            np.array([1, 0, 2, 3]), mz, tolerance_ppm=10.0
        )
        np.testing.assert_array_equal(selected, np.array([1, 2, 3]))

    def test_ppm_suppression_can_limit_candidate_count(self):
        mz = np.array([100.0, 200.0, 300.0])
        selected = ppm_nonmaximum_suppression(
            np.array([2, 1, 0]), mz, tolerance_ppm=5.0, count=2
        )
        np.testing.assert_array_equal(selected, np.array([2, 1]))


if __name__ == "__main__":
    unittest.main()
