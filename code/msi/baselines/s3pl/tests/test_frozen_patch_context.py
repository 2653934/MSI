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

    def test_tiling_preserves_centre_and_fills_all_slots(self):
        patch = torch.arange(1 * 1 * 4 * 3 * 3, dtype=torch.float32).reshape(1, 1, 4, 3, 3)
        tiled = ablate_patch_context(patch, "tile_centre")
        self.assertTrue(torch.equal(tiled[..., 1, 1], patch[..., 1, 1]))
        for row in range(3):
            for column in range(3):
                self.assertTrue(torch.equal(tiled[..., row, column], patch[..., 1, 1]))
        self.assertTrue(torch.equal(patch, torch.arange(36, dtype=torch.float32).reshape(1, 1, 4, 3, 3)))

    def test_rotation_preserves_centre_and_all_values(self):
        patch = torch.arange(25, dtype=torch.float32).reshape(1, 1, 1, 5, 5)
        rotated = ablate_patch_context(patch, "rotate_90")
        self.assertTrue(torch.equal(rotated[..., 2, 2], patch[..., 2, 2]))
        self.assertEqual(sorted(rotated.flatten().tolist()), sorted(patch.flatten().tolist()))
        self.assertTrue(torch.equal(patch, torch.arange(25, dtype=torch.float32).reshape(1, 1, 1, 5, 5)))

    def test_ring_permutation_preserves_centre_and_each_ring_multiset(self):
        patch = torch.arange(25, dtype=torch.float32).reshape(1, 1, 1, 5, 5)
        changed = ablate_patch_context(patch, "permute_within_rings")
        self.assertTrue(torch.equal(changed[..., 2, 2], patch[..., 2, 2]))
        self.assertFalse(torch.equal(changed, patch))
        for radius in (1, 2):
            positions = [
                (row, column)
                for row in range(5)
                for column in range(5)
                if max(abs(row - 2), abs(column - 2)) == radius
            ]
            before = sorted(float(patch[..., row, col].item()) for row, col in positions)
            after = sorted(float(changed[..., row, col].item()) for row, col in positions)
            self.assertEqual(after, before)
        self.assertTrue(torch.equal(patch, torch.arange(25, dtype=torch.float32).reshape(1, 1, 1, 5, 5)))

    def test_invalid_input_is_rejected(self):
        with self.assertRaises(ValueError):
            ablate_patch_context(torch.ones(1, 1, 2, 4, 4), "zero_noncentral")
        with self.assertRaises(ValueError):
            ablate_patch_context(torch.ones(1, 1, 2, 3, 3), "shuffle")


if __name__ == "__main__":
    unittest.main()
