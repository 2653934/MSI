"""Tests for the three controlled neighbourhood aggregation variants."""

import unittest

import torch

from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.neighbourhood import (
    AttentionNeighbourhood,
    DepthwiseNeighbourhood,
    UniformMeanNeighbourhood,
)


class NeighbourhoodTests(unittest.TestCase):
    def setUp(self):
        self.central = torch.tensor([[0.2, 0.3, 0.5]], dtype=torch.float32)
        self.neighbours = torch.zeros(1, 8, 3)
        self.neighbours[0, 1] = torch.tensor([0.1, 0.3, 0.6])
        self.neighbours[0, 6] = torch.tensor([0.3, 0.3, 0.4])
        self.mask = torch.tensor(
            [[False, True, False, False, False, False, True, False]]
        )

    def test_uniform_mean_ignores_missing_slots(self):
        context, weights = UniformMeanNeighbourhood()(
            self.central, self.neighbours, self.mask
        )
        torch.testing.assert_close(context, torch.tensor([[0.2, 0.3, 0.5]]))
        torch.testing.assert_close(weights[0, [1, 6]], torch.tensor([0.5, 0.5]))
        self.assertEqual(float(weights[0, ~self.mask[0]].sum()), 0.0)

    def test_depthwise_starts_as_uniform_and_receives_gradients(self):
        aggregator = DepthwiseNeighbourhood(spectral_dim=3)
        context, weights = aggregator(self.central, self.neighbours, self.mask)
        expected, _ = UniformMeanNeighbourhood()(
            self.central, self.neighbours, self.mask
        )
        torch.testing.assert_close(context, expected)
        context[0, 0].backward()
        self.assertIsNotNone(aggregator.position_logits.grad)
        self.assertTrue(torch.isfinite(aggregator.position_logits.grad).all())
        self.assertEqual(tuple(weights.shape), (1, 8, 3))

    def test_attention_is_orientation_free_and_masks_missing_slots(self):
        torch.manual_seed(3)
        aggregator = AttentionNeighbourhood(spectral_dim=3, attention_dim=2)
        context, weights = aggregator(self.central, self.neighbours, self.mask)

        permutation = torch.tensor([7, 6, 5, 4, 3, 2, 1, 0])
        permuted_context, _ = aggregator(
            self.central,
            self.neighbours[:, permutation],
            self.mask[:, permutation],
        )
        torch.testing.assert_close(context, permuted_context)
        self.assertEqual(float(weights[0, ~self.mask[0]].sum()), 0.0)
        context.sum().backward()
        self.assertIsNotNone(aggregator.projection.weight.grad)

    def test_isolated_pixel_produces_zero_context_without_nan(self):
        empty_neighbours = torch.zeros_like(self.neighbours)
        empty_mask = torch.zeros_like(self.mask)
        aggregators = (
            UniformMeanNeighbourhood(),
            DepthwiseNeighbourhood(spectral_dim=3),
            AttentionNeighbourhood(spectral_dim=3, attention_dim=2),
        )
        for aggregator in aggregators:
            context, weights = aggregator(
                self.central, empty_neighbours, empty_mask
            )
            self.assertTrue(torch.isfinite(context).all())
            self.assertTrue(torch.isfinite(weights).all())
            self.assertEqual(float(context.abs().sum()), 0.0)
            self.assertEqual(float(weights.abs().sum()), 0.0)

    def test_all_variants_share_the_same_vae_output_contract(self):
        batch_central = self.central.repeat(2, 1)
        batch_neighbours = self.neighbours.repeat(2, 1, 1)
        batch_mask = self.mask.repeat(2, 1)
        for name in ("uniform_mean", "depthwise", "attention"):
            model = NeighbourhoodSpatialVAE(
                spectral_dim=3,
                neighbourhood=name,
                hidden_dim=4,
                latent_dim=2,
                attention_dim=2,
            )
            model.eval()
            reconstruction, mean, log_variance, context, _ = model(
                batch_central, batch_neighbours, batch_mask
            )
            self.assertEqual(tuple(reconstruction.shape), (2, 3))
            self.assertEqual(tuple(mean.shape), (2, 2))
            self.assertEqual(tuple(log_variance.shape), (2, 2))
            self.assertEqual(tuple(context.shape), (2, 3))


if __name__ == "__main__":
    unittest.main()
