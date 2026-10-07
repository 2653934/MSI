"""Boundary sampling remains label-only and paired across model arms."""

import unittest

import numpy as np

from audit_attention_boundary import select_groups


class AttentionBoundaryTests(unittest.TestCase):
    def test_selects_boundary_and_interior_with_two_neighbours(self):
        slots = np.array([[1, 2], [0, 2], [0, 1], [4, 5], [3, 5], [3, 4]])
        labels = np.array([0, 0, 1, 1, 1, 1])
        groups, population = select_groups(slots, labels, per_class=2, seed=3)
        self.assertEqual(population, {"boundary": 3, "interior": 3})
        self.assertEqual(set(groups["boundary"]), {0, 1, 2})
        self.assertEqual(len(groups["interior"]), 2)
        self.assertTrue(set(groups["interior"]).issubset({3, 4, 5}))

    def test_sampling_is_repeatable(self):
        slots = np.array([[1, 2], [0, 2], [0, 1], [4, 5], [3, 5], [3, 4]])
        labels = np.array([0, 0, 1, 1, 1, 1])
        a, _ = select_groups(slots, labels, 2, 7)
        b, _ = select_groups(slots, labels, 2, 7)
        self.assertTrue(all(np.array_equal(a[key], b[key]) for key in a))


if __name__ == "__main__":
    unittest.main()
