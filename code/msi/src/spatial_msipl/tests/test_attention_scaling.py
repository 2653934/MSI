"""Regression checks for temporary scaling and the gradient diagnostic."""

import importlib.util
from pathlib import Path
import unittest

import torch

from spatial_msipl.model import NeighbourhoodSpatialVAE

path = Path(__file__).resolve().parents[3] / "scripts/check_spatial_attention_scaling.py"
spec = importlib.util.spec_from_file_location("scaling_diagnostic", path)
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


class AttentionScalingTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(3)
        self.model = NeighbourhoodSpatialVAE(6, "attention", hidden_dim=4, latent_dim=2)
        central = torch.rand(4, 6)
        neighbours = torch.rand(4, 8, 6)
        self.batch = {
            "target": central / central.sum(-1, keepdim=True),
            "neighbours": neighbours / neighbours.sum(-1, keepdim=True),
            "neighbour_mask": torch.ones(4, 8, dtype=torch.bool),
        }
        self.batch["neighbour_mask"][0, 0] = False

    def test_scaling_changes_projection_only_and_restores_on_exception(self):
        central = self.batch["target"]
        neighbours = self.batch["neighbours"]
        mask = self.batch["neighbour_mask"]
        model = self.model
        original_context, original_weights = model.aggregator(central, neighbours, mask)
        with self.assertRaisesRegex(RuntimeError, "intentional"):
            with diagnostic.projection_scale(model, 1.0):
                context, weights = model.aggregator(central, neighbours, mask)
                torch.testing.assert_close(weights.sum(1), torch.ones(4))
                self.assertEqual(float(weights[0, 0]), 0)
                # Context must still be the weighted ORIGINAL spectra.
                expected = (neighbours * weights[:, :, None]).sum(1)
                expected /= expected.sum(1, keepdim=True)
                torch.testing.assert_close(context, expected)
                raise RuntimeError("intentional")
        restored_context, restored_weights = model.aggregator(central, neighbours, mask)
        torch.testing.assert_close(restored_context, original_context)
        torch.testing.assert_close(restored_weights, original_weights)

    def test_original_scale_preserves_original_outputs(self):
        before = diagnostic.measure(self.model, self.batch)
        with diagnostic.projection_scale(self.model, 6.0):
            after = diagnostic.measure(self.model, self.batch)
        self.assertEqual(before, after)

    def test_short_run_reports_actual_projection_gradients(self):
        history = diagnostic.run_candidate(self.model, [self.batch], 1.0, 2)
        self.assertEqual([r["step"] for r in history], [0, 1, 2])
        self.assertGreater(history[1]["projection_gradient_norm"], 0)
        self.assertEqual(history[-1]["pixels_with_at_least_two_neighbours"], 4)


if __name__ == "__main__":
    unittest.main()
