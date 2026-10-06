"""Small label-free checks for the centre–context shift screen."""

import unittest

import numpy as np

from audit_attention_context_shift import describe, input_similarity


class AttentionContextShiftTests(unittest.TestCase):
    def test_identical_spectra_have_unit_cosine_and_zero_distance(self):
        score = input_similarity([0.75, 0.25], [0.75, 0.25])
        self.assertAlmostEqual(score[0], 1.0)
        self.assertAlmostEqual(score[1], 0.0)

    def test_disjoint_spectra_have_zero_cosine(self):
        score = input_similarity([1.0, 0.0], [0.0, 1.0])
        self.assertAlmostEqual(score[0], 0.0)
        self.assertAlmostEqual(score[1], 1.0)

    def test_zero_context_is_excluded(self):
        self.assertIsNone(input_similarity([1.0, 0.0], [0.0, 0.0]))

    def test_paired_direction_and_tail_fraction(self):
        result = describe([0.8, 0.9, 1.0], [0.1, 0.2, 0.3])
        self.assertLess(result["median_paired_change_shuffled_minus_real"], 0)
        self.assertEqual(result["shuffled_below_real_5th_fraction"], 1.0)

    def test_nonfinite_values_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-finite"):
            describe([1.0, np.nan], [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()
