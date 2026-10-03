"""Small independent geometry checks for the cluster topology diagnostic."""

import sys
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from audit_spatial_window_topology import audit_window, independent_reference_slots


class WindowTopologyAuditTests(unittest.TestCase):
    def test_full_three_by_three_and_cross_class_edges(self):
        x = np.tile(np.arange(1, 4), 3)
        y = np.repeat(np.arange(1, 4), 3)
        labels = np.zeros(9, dtype=np.int64)
        labels[4] = 1

        three = audit_window(x, y, labels, 3)
        five = audit_window(x, y, labels, 5)

        self.assertEqual(three["valid_directed_edges"], 40)
        self.assertEqual(three["cross_class_directed_edges"], 16)
        self.assertEqual(three["max_valid_neighbours"], 8)
        self.assertEqual(five["valid_directed_edges"], 72)
        self.assertEqual(five["cross_class_directed_edges"], 16)
        self.assertTrue(three["reference_matches_production"])

    def test_missing_position_is_not_a_neighbour(self):
        x = np.array([1, 3, 1, 2, 3, 1, 2, 3])
        y = np.array([1, 1, 2, 2, 2, 3, 3, 3])
        slots = independent_reference_slots(x, y, 3)
        # The absent (2, 1) grid position never acquires a measured index.
        self.assertEqual(int(np.count_nonzero(slots[0] >= 0)), 2)
        self.assertEqual(int(np.count_nonzero(slots[3] >= 0)), 7)

    def test_duplicate_coordinates_fail(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            independent_reference_slots(
                np.array([1, 1]), np.array([1, 1]), 3
            )


if __name__ == "__main__":
    unittest.main()
