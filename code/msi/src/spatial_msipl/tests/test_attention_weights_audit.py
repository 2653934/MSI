"""Unit tests for attention concentration summaries."""

import unittest

import numpy as np

from audit_attention_weights import weight_statistics


class WeightStatisticsTests(unittest.TestCase):
    def test_uniform_valid_weights_have_unit_normalized_entropy(self):
        result = weight_statistics([[.5, .5, 0]], [[True, True, False]])
        self.assertAlmostEqual(result["normalized_entropy"][0], 1)
        self.assertAlmostEqual(result["effective_neighbours"][0], 2)

    def test_single_weight_has_zero_entropy(self):
        result = weight_statistics([[1, 0, 0]], [[True, True, False]])
        self.assertAlmostEqual(result["normalized_entropy"][0], 0)
        self.assertAlmostEqual(result["max_weight"][0], 1)

    def test_rejects_invalid_normalization(self):
        with self.assertRaisesRegex(ValueError, "sum to one"):
            weight_statistics([[.4, .4]], [[True, True]])


if __name__ == "__main__":
    unittest.main()
