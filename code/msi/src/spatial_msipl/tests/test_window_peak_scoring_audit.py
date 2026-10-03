"""Synthetic checks for the independent window peak-score audit."""

import sys
import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from audit_window_peak_scoring import (
    correlations_from_h5,
    counts_and_f1,
    threshold_reference_sets,
)


class WindowPeakScoringAuditTests(unittest.TestCase):
    def test_pearson_handles_both_h5_orientations_and_constant_bins(self):
        pixels_by_bin = np.array(
            [[0.0, 5.0], [0.0, 5.0], [1.0, 5.0], [1.0, 5.0]]
        )
        for data in (pixels_by_bin, pixels_by_bin.T):
            with self.subTest(shape=data.shape), tempfile.TemporaryDirectory() as root:
                path = Path(root) / "sample.h5"
                with h5py.File(path, "w") as handle:
                    handle["Data"] = data
                    handle["Class_Label"] = np.array([0, 0, 1, 1])
                    handle["mzArray"] = np.array([100.0, 200.0])
                classes, correlations = correlations_from_h5(path, chunk_size=1)
                self.assertEqual(classes.tolist(), [0, 1])
                np.testing.assert_allclose(correlations[:, 0], [-1.0, 1.0])
                np.testing.assert_array_equal(correlations[:, 1], [0.0, 0.0])

    def test_ranked_threshold_and_f1(self):
        sets, mixed = threshold_reference_sets(
            np.array([[0.9, 0.7, 0.2], [0.1, 0.9, 0.5]]), 0.6
        )
        self.assertEqual(sets, [{0}, {1}])
        self.assertEqual(mixed, {0, 1})
        scored = counts_and_f1({0, 1}, {1, 2}, 4)
        self.assertEqual(
            [scored[key] for key in (
                "true_positive", "false_positive", "false_negative", "true_negative"
            )],
            [1, 1, 1, 1],
        )
        self.assertEqual(scored["F1"], 0.5)


if __name__ == "__main__":
    unittest.main()
