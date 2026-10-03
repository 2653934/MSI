"""Small, checkpoint-free tests for the frozen context-swap diagnostic."""

import sys
import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np
import torch

from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.preprocessing import CachedH5SpatialContextDataset, H5SpatialContextDataset
from spatial_msipl.training import msipl_vae_loss

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from audit_spatial_context_model_sensitivity import aggregate, context_batches, scored_outputs


class ContextModelSensitivityTests(unittest.TestCase):
    def test_context_batches_match_production_samples(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "toy.h5"
            with h5py.File(path, "w") as handle:
                handle["Data"] = np.arange(25 * 4, dtype=np.float32).reshape(25, 4) + 1
                handle["mzArray"] = np.arange(4, dtype=np.float32) + 100
                handle["xLocation"] = np.tile(np.arange(1, 6), 5)
                handle["yLocation"] = np.repeat(np.arange(1, 6), 5)
            measured = CachedH5SpatialContextDataset(path, include_neighbourhood=True)
            shuffled = H5SpatialContextDataset(
                path, include_neighbourhood=True,
                context_mode="shuffled", context_seed=1701,
            )
            try:
                selected = [{"index": "12", "group": "interior"}]
                _, central, mask, contexts = context_batches(
                    measured, shuffled.context_source_slots, selected, 0, 1,
                )
                np.testing.assert_allclose(central[0], measured[12]["target"])
                np.testing.assert_array_equal(mask[0], shuffled[12]["neighbour_mask"])
                np.testing.assert_allclose(
                    contexts["shuffled"][0], shuffled[12]["neighbours"], atol=1e-7
                )
                self.assertTrue(np.all(contexts["zero"] == 0))
            finally:
                measured.close()
                shuffled.close()

    def test_scoring_is_deterministic_and_uses_training_loss_scale(self):
        torch.manual_seed(7)
        model = NeighbourhoodSpatialVAE(spectral_dim=4, hidden_dim=8, latent_dim=2)
        model.eval()
        central = torch.tensor([[0.1, 0.2, 0.3, 0.4]], dtype=torch.float32)
        neighbours = torch.zeros((1, 8, 4), dtype=torch.float32)
        mask = torch.zeros((1, 8), dtype=torch.bool)
        with torch.inference_mode():
            first_mean, first_loss = scored_outputs(model, central, neighbours, mask)
            second_mean, second_loss = scored_outputs(model, central, neighbours, mask)
            mean, log_variance, _, _ = model.encode(central, neighbours, mask)
            reconstruction = model.vae.decode(mean)
            _, training_reconstruction_loss, _ = msipl_vae_loss(
                reconstruction, central, mean, log_variance
            )
        torch.testing.assert_close(first_mean, second_mean)
        torch.testing.assert_close(first_loss, second_loss)
        torch.testing.assert_close(first_loss.mean(), training_reconstruction_loss)
        self.assertTrue(torch.isfinite(first_loss).all())

    def test_aggregate_preserves_paired_delta(self):
        one = {
            "trained_on": "real", "group": "boundary",
            "real_cross_entropy": 3.0, "shuffled_cross_entropy": 5.0,
            "zero_cross_entropy": 6.0,
            "shuffled_minus_real_cross_entropy": 2.0,
            "zero_minus_real_cross_entropy": 3.0,
            "real_shuffled_latent_l2": 0.4, "real_zero_latent_l2": 0.7,
        }
        summary = aggregate([one])
        self.assertEqual(summary["real"]["boundary"]["mean_shuffled_minus_real_cross_entropy"], 2.0)
        self.assertIsNone(summary["shuffled"]["all"]["mean_real_cross_entropy"])


if __name__ == "__main__":
    unittest.main()
