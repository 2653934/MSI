"""Pure distance checks for frozen attention versus equal-weight context."""

import unittest

import numpy as np

from audit_attention_vs_uniform import context_distances


class ContextDistanceTests(unittest.TestCase):
    def test_identical_contexts(self):
        distance, cosine = context_distances([[.75, .25]], [[.75, .25]])
        self.assertAlmostEqual(distance[0], 0)
        self.assertAlmostEqual(cosine[0], 1)

    def test_distinct_contexts(self):
        distance, cosine = context_distances([[1, 0]], [[0, 1]])
        self.assertAlmostEqual(distance[0], 1)
        self.assertAlmostEqual(cosine[0], 0)

    def test_mismatched_shape_rejected(self):
        with self.assertRaisesRegex(ValueError, "matching"):
            context_distances([[1, 0]], [[1]])


if __name__ == "__main__":
    unittest.main()
