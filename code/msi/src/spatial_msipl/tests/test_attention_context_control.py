"""Small wiring checks for a matched real-versus-shuffled attention run."""

import tempfile
import unittest
from pathlib import Path

import torch

from run_spatial_msipl_gmm_integrated_gradients import load_model
from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.neighbourhood import AttentionNeighbourhood
from spatial_msipl.preprocessing import checkpoint_input_spec
from train_spatial_msipl_production import variant_input_spec
from validate_spatial_window_cache import cache_context_mode


class AttentionContextControlTests(unittest.TestCase):
    def test_both_arms_use_identical_attention_architecture(self):
        self.assertEqual(variant_input_spec("attention"), ("attention", "measured"))
        self.assertEqual(
            variant_input_spec("attention_shuffled"), ("attention", "shuffled")
        )
        self.assertEqual(cache_context_mode("real_attention"), "measured")
        self.assertEqual(cache_context_mode("shuffled_attention"), "shuffled")

    def test_attention_weights_depend_on_the_central_spectrum(self):
        module = AttentionNeighbourhood(4, attention_dim=2, input_scale="sqrt_bins")
        with torch.no_grad():
            module.projection.weight.zero_()
            module.projection.bias.zero_()
            module.projection.weight[0, 0] = 3.0
            module.projection.weight[1, 1] = 3.0
        neighbours = torch.zeros(2, 8, 4)
        neighbours[:, 0, 0] = 1.0
        neighbours[:, 1, 1] = 1.0
        mask = torch.zeros(2, 8, dtype=torch.bool)
        mask[:, :2] = True
        central = torch.tensor([[1.0, 0, 0, 0], [0, 1.0, 0, 0]])
        _, weights = module(central, neighbours, mask)
        self.assertGreater(float(weights[0, 0]), float(weights[0, 1]))
        self.assertGreater(float(weights[1, 1]), float(weights[1, 0]))
        self.assertEqual(float(weights[:, 2:].sum()), 0.0)

    def test_shuffled_checkpoint_requires_shuffled_evaluation_variant(self):
        model = NeighbourhoodSpatialVAE(
            4, neighbourhood="attention", hidden_dim=8, latent_dim=2,
            attention_dim=2, attention_input_scale="sqrt_bins", window_size=3,
        )
        checkpoint = {
            "completed_epochs": 100,
            "model_configuration": model.configuration(),
            "model_state_dict": model.state_dict(),
            "resume_signature": {
                "dataset_window_size": 3,
                "context_mode": "shuffled",
                "context_seed": 1701,
                "context_permutation_sha256": "test-permutation",
            },
        }
        self.assertEqual(checkpoint_input_spec(checkpoint)["context_seed"], 1701)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "checkpoint.pt"
            loaded, _ = load_model(
                path, 4, "attention_shuffled", torch.device("cpu"),
                checkpoint=checkpoint,
            )
            self.assertEqual(loaded.configuration()["neighbourhood"]["name"], "attention")
            with self.assertRaisesRegex(ValueError, "measured-context"):
                load_model(
                    path, 4, "attention", torch.device("cpu"),
                    checkpoint=checkpoint,
                )


if __name__ == "__main__":
    unittest.main()
