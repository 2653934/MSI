"""Small invariants for the frozen S3PL input intervention."""

import sys
import unittest
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test import ablate_patch_context


class FrozenPatchContextTests(unittest.TestCase):
    def test_zeroing_preserves_centre_without_mutating_input(self):
        patch = torch.arange(2 * 1 * 4 * 3 * 3, dtype=torch.float32).reshape(2, 1, 4, 3, 3)
        original = patch.clone()
        ablated = ablate_patch_context(patch, "zero_noncentral")
        self.assertTrue(torch.equal(patch, original))
        self.assertTrue(torch.equal(ablated[..., 1, 1], patch[..., 1, 1]))
        ablated[..., 1, 1] = 0
        self.assertEqual(torch.count_nonzero(ablated), 0)

    def test_none_is_identity(self):
        patch = torch.ones(1, 1, 2, 5, 5)
        self.assertIs(ablate_patch_context(patch, "none"), patch)

    def test_invalid_input_is_rejected(self):
        with self.assertRaises(ValueError):
            ablate_patch_context(torch.ones(1, 1, 2, 4, 4), "zero_noncentral")
        with self.assertRaises(ValueError):
            ablate_patch_context(torch.ones(1, 1, 2, 3, 3), "shuffle")


if __name__ == "__main__":
    unittest.main()
