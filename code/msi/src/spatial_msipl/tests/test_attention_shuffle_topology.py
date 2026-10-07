"""Geometry and overlap tests for the label-free frozen-shuffle audit."""

import unittest

import numpy as np

from audit_attention_shuffle_topology import adjacent_pairs, distant_pairs, jaccard


class ShuffleTopologyTests(unittest.TestCase):
    def test_jaccard_ignores_unmeasured_slots(self):
        self.assertAlmostEqual(jaccard([1, 2, -1], [2, 3, -1]), 1 / 3)

    def test_adjacent_pairs_are_unique(self):
        x = np.array([0, 1, 0, 1])
        y = np.array([0, 0, 1, 1])
        pairs = adjacent_pairs(x, y)
        self.assertEqual(len(pairs), 6)
        self.assertTrue(np.all(pairs[:, 0] < pairs[:, 1]))

    def test_distant_pairs_do_not_overlap_local_window(self):
        x = np.arange(10)
        y = np.zeros(10, dtype=int)
        pairs = distant_pairs(x, y, 30, 4)
        self.assertTrue(np.all(np.abs(x[pairs[:, 0]] - x[pairs[:, 1]]) > 2))


if __name__ == "__main__":
    unittest.main()
