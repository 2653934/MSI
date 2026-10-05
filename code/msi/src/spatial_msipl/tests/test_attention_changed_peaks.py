"""CPU-only checks for the frozen attention changed-peak audit."""

import unittest

import numpy as np

from audit_spatial_attention_changed_peaks import changed_indices, positive_sets


class ChangedPeakAuditTests(unittest.TestCase):
    def test_symmetric_difference_preserves_each_ranking_order(self):
        gained, lost = changed_indices([4, 1, 2, 8], [2, 9, 4, 6])
        self.assertEqual(gained, [9, 6])
        self.assertEqual(lost, [1, 8])

    def test_duplicate_or_mismatched_peak_lists_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            changed_indices([1, 1], [1, 2])
        with self.assertRaisesRegex(ValueError, "different peak counts"):
            changed_indices([1], [1, 2])

    def test_reference_sets_follow_existing_positive_pcc_rule(self):
        correlations = {
            0: np.array([0.8, 0.4, 0.1, -0.2]),
            1: np.array([0.0, 0.7, 0.2, -0.4]),
        }
        results = positive_sets(correlations)
        self.assertEqual(results["0.3"], {0, 1})
        self.assertEqual(results["0.6"], {0})


if __name__ == "__main__":
    unittest.main()
