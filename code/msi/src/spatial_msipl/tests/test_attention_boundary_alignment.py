"""Same-label mass uses valid slots and preserves equal-mean comparator."""

import unittest

from audit_attention_boundary_alignment import same_label_mass


class SameLabelMassTests(unittest.TestCase):
    def test_prefers_same_label_neighbour(self):
        attention, uniform = same_label_mass(
            [[.75, .25, 0]], [[True, True, False]], [[1, 2, 0]], [1]
        )
        self.assertAlmostEqual(attention[0], .75)
        self.assertAlmostEqual(uniform[0], .5)

    def test_rejects_invalid_weight_sum(self):
        with self.assertRaisesRegex(ValueError, "sum to one"):
            same_label_mass([[.4, .4]], [[True, True]], [[1, 2]], [1])

    def test_ignores_unmeasured_slot_label(self):
        attention, uniform = same_label_mass(
            [[.25, .75, 0]], [[True, True, False]], [[1, 2, 1]], [1]
        )
        self.assertAlmostEqual(attention[0], .25)
        self.assertAlmostEqual(uniform[0], .5)


if __name__ == "__main__":
    unittest.main()
