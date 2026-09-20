"""Tests for nonlinear cluster-posterior attribution."""

import unittest

import torch
from torch import nn

from spatial_msipl.attribution import (
    first_layer_l2_importance,
    gmm_posterior,
    integrated_gradients_cluster_posterior,
)
from spatial_msipl.model import CentralOnlyVAE


class TinyContextEncoder(nn.Module):
    """Small nonlinear encoder with the production encode contract."""

    def encode(self, central, neighbours, neighbour_mask):
        weights = neighbour_mask.to(central.dtype)
        context = (neighbours * weights.unsqueeze(2)).sum(dim=1)
        context = context / weights.sum(dim=1, keepdim=True).clamp_min(1.0)
        latent = torch.tanh(
            1.4 * central[:, :1] - 0.7 * central[:, 1:2]
            + 0.9 * context[:, :1]
        )
        return latent, torch.zeros_like(latent), context, weights


class TinyCentralEncoder(nn.Module):
    """Centre-only encoder that accepts the shared attribution interface."""

    def encode(self, central, neighbours=None, neighbour_mask=None):
        del neighbours, neighbour_mask
        latent = torch.tanh(1.4 * central[:, :1] - 0.7 * central[:, 1:2])
        return latent, torch.zeros_like(latent)


def tiny_gmm_parameters():
    return {
        "scaler_mean": torch.tensor([0.0]),
        "scaler_scale": torch.tensor([1.0]),
        "mixture_weights": torch.tensor([0.5, 0.5]),
        "component_means": torch.tensor([[-0.8], [0.8]]),
        "precision_cholesky": torch.tensor([[[1.0]], [[1.0]]]),
    }


class AttributionTests(unittest.TestCase):
    def test_central_only_first_layer_has_zero_context_importance(self):
        model = CentralOnlyVAE(spectral_dim=6, hidden_dim=4, latent_dim=2)
        central, context = first_layer_l2_importance(model)
        self.assertEqual(tuple(central.shape), (6,))
        torch.testing.assert_close(context, torch.zeros_like(context))

    def test_central_only_integrated_gradients_has_zero_neighbour_path(self):
        model = TinyCentralEncoder()
        central = torch.tensor([[0.7, 0.3]])
        central_baseline = torch.tensor([[0.5, 0.5]])
        neighbours = torch.rand(1, 8, 2)
        neighbour_baseline = torch.zeros_like(neighbours)
        mask = torch.ones(1, 8, dtype=torch.bool)

        central_attr, neighbour_attr, diagnostics = (
            integrated_gradients_cluster_posterior(
                model,
                central,
                neighbours,
                mask,
                central_baseline,
                neighbour_baseline,
                target_component=1,
                gmm_parameters=tiny_gmm_parameters(),
                steps=256,
                internal_batch_size=32,
            )
        )
        self.assertGreater(float(central_attr.abs().sum()), 0.0)
        self.assertEqual(float(neighbour_attr.abs().sum()), 0.0)
        self.assertLess(abs(diagnostics["completeness_residual"]), 1e-4)

    def test_gmm_posterior_is_normalized_and_differentiable(self):
        latent = torch.tensor([[-0.4], [0.7]], requires_grad=True)
        posterior = gmm_posterior(latent, **tiny_gmm_parameters())
        torch.testing.assert_close(posterior.sum(dim=1), torch.ones(2))
        posterior[:, 1].sum().backward()
        self.assertIsNotNone(latent.grad)
        self.assertTrue(torch.isfinite(latent.grad).all())

    def test_integrated_gradients_is_complete_and_separates_paths(self):
        model = TinyContextEncoder()
        central = torch.tensor([[0.7, 0.3]])
        central_baseline = torch.tensor([[0.5, 0.5]])
        neighbours = torch.zeros(1, 8, 2)
        neighbour_baseline = torch.zeros_like(neighbours)
        mask = torch.tensor([[True, True, False, False, False, False, False, False]])
        neighbours[0, 0] = torch.tensor([0.8, 0.2])
        neighbours[0, 1] = torch.tensor([0.6, 0.4])
        neighbour_baseline[0, :2] = central_baseline

        central_attr, neighbour_attr, diagnostics = (
            integrated_gradients_cluster_posterior(
                model,
                central,
                neighbours,
                mask,
                central_baseline,
                neighbour_baseline,
                target_component=1,
                gmm_parameters=tiny_gmm_parameters(),
                steps=256,
                internal_batch_size=32,
            )
        )
        self.assertEqual(tuple(central_attr.shape), (1, 2))
        self.assertEqual(tuple(neighbour_attr.shape), (1, 8, 2))
        self.assertGreater(float(central_attr.abs().sum()), 0.0)
        self.assertGreater(float(neighbour_attr.abs().sum()), 0.0)
        self.assertLess(abs(diagnostics["completeness_residual"]), 1e-4)

    def test_identical_input_and_baseline_have_zero_attribution(self):
        model = TinyContextEncoder()
        central = torch.tensor([[0.5, 0.5]])
        neighbours = central[:, None, :].repeat(1, 8, 1)
        mask = torch.ones(1, 8, dtype=torch.bool)
        central_attr, neighbour_attr, diagnostics = (
            integrated_gradients_cluster_posterior(
                model,
                central,
                neighbours,
                mask,
                central,
                neighbours,
                target_component=0,
                gmm_parameters=tiny_gmm_parameters(),
                steps=8,
            )
        )
        self.assertEqual(float(central_attr.abs().sum()), 0.0)
        self.assertEqual(float(neighbour_attr.abs().sum()), 0.0)
        self.assertEqual(diagnostics["completeness_residual"], 0.0)


if __name__ == "__main__":
    unittest.main()
