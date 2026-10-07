"""Independent numerical and causal checks for the VAE training contract."""

import math
import tempfile
import unittest

import numpy as np
import torch
from torch.utils.data import Dataset

from spatial_msipl.model import CentralOnlyVAE, NeighbourhoodSpatialVAE, SpatialVAE
from spatial_msipl.training import msipl_vae_loss, train_vae


class RepeatedCentreDataset(Dataset):
    """A tiny, label-free learning problem with an intentionally easy target."""

    path = "synthetic-constant-centre"

    def __len__(self):
        return 8

    def __getitem__(self, index):
        del index
        centre = torch.tensor([0.7, 0.1, 0.1, 0.1], dtype=torch.float32)
        return {
            "target": centre,
            "neighbours": torch.zeros(8, 4, dtype=torch.float32),
            "neighbour_mask": torch.zeros(8, dtype=torch.bool),
        }


class ModelFoundationAuditTests(unittest.TestCase):
    def test_loss_and_derivative_match_independent_numpy_calculation(self):
        prediction = torch.tensor([[0.2, 0.3, 0.4], [0.6, 0.2, 0.4]],
                                  dtype=torch.float64, requires_grad=True)
        target = torch.tensor([[0.5, 0.3, 0.2], [0.1, 0.2, 0.7]], dtype=torch.float64)
        mean = torch.tensor([[0.3, -0.2], [0.1, 0.4]], dtype=torch.float64,
                            requires_grad=True)
        log_variance = torch.tensor([[0.1, -0.3], [0.2, 0.0]],
                                    dtype=torch.float64, requires_grad=True)
        beta = 0.7
        total, reconstruction, kl = msipl_vae_loss(
            prediction, target, mean, log_variance, beta=beta)

        p = prediction.detach().numpy()
        t = target.numpy()
        mu = mean.detach().numpy()
        lv = log_variance.detach().numpy()
        expected_reconstruction = np.mean(-np.sum(t * np.log(p / p.sum(axis=1, keepdims=True)), axis=1) * 3)
        expected_kl = np.mean(-0.5 * np.sum(1 + lv - mu ** 2 - np.exp(lv), axis=1))
        self.assertAlmostEqual(reconstruction.item(), expected_reconstruction, places=11)
        self.assertAlmostEqual(kl.item(), expected_kl, places=11)
        self.assertAlmostEqual(total.item(), expected_reconstruction + beta * expected_kl, places=11)

        total.backward()
        self.assertTrue(torch.isfinite(prediction.grad).all())
        self.assertTrue(torch.isfinite(mean.grad).all())
        self.assertTrue(torch.isfinite(log_variance.grad).all())
        step = 1e-6
        plus = p.copy()
        minus = p.copy()
        plus[0, 0] += step
        minus[0, 0] -= step
        def numpy_reconstruction(values):
            return np.mean(-np.sum(t * np.log(values / values.sum(axis=1, keepdims=True)), axis=1) * 3)
        finite_difference = (numpy_reconstruction(plus) - numpy_reconstruction(minus)) / (2 * step)
        self.assertAlmostEqual(prediction.grad[0, 0].item(), finite_difference, places=7)

    def test_parameter_counts_match_linear_layer_formula(self):
        spectral_dim, hidden_dim, latent_dim = 7, 5, 2
        def expected(input_spectra):
            return ((input_spectra * spectral_dim * hidden_dim + hidden_dim)
                    + 2 * hidden_dim
                    + 2 * (hidden_dim * latent_dim + latent_dim)
                    + (latent_dim * hidden_dim + hidden_dim)
                    + 2 * hidden_dim
                    + (hidden_dim * spectral_dim + spectral_dim))
        centre = CentralOnlyVAE(spectral_dim, hidden_dim, latent_dim)
        context = NeighbourhoodSpatialVAE(spectral_dim, "uniform_mean", hidden_dim, latent_dim)
        self.assertEqual(sum(p.numel() for p in centre.parameters()), expected(1))
        self.assertEqual(sum(p.numel() for p in context.parameters()), expected(2))
        self.assertEqual(expected(2) - expected(1), spectral_dim * hidden_dim)

    def test_invalid_slots_cannot_change_context_or_receive_gradient(self):
        central = torch.tensor([[0.2, 0.3, 0.5]], dtype=torch.float32)
        neighbours = torch.tensor([[[0.1, 0.2, 0.7]] + [[0.4, 0.4, 0.2]] * 7],
                                  dtype=torch.float32, requires_grad=True)
        mask = torch.tensor([[True] + [False] * 7])
        changed = neighbours.detach().clone()
        changed[:, 1:] = torch.rand_like(changed[:, 1:])
        for method in ("uniform_mean", "attention"):
            with self.subTest(method=method):
                model = NeighbourhoodSpatialVAE(3, neighbourhood=method,
                                                hidden_dim=5, latent_dim=2,
                                                attention_input_scale="sqrt_bins")
                contextual, context, weights = model.build_contextual_input(
                    central, neighbours, mask)
                changed_contextual, changed_context, changed_weights = model.build_contextual_input(
                    central, changed, mask)
                torch.testing.assert_close(contextual, changed_contextual)
                torch.testing.assert_close(context, changed_context)
                torch.testing.assert_close(weights, changed_weights)
                self.assertTrue(torch.count_nonzero(weights[:, 1:]) == 0)
                model.zero_grad(set_to_none=True)
                if neighbours.grad is not None:
                    neighbours.grad.zero_()
                (context * torch.tensor([[1.0, 2.0, 3.0]])).sum().backward()
                self.assertTrue(torch.count_nonzero(neighbours.grad[:, 1:]) == 0)
                self.assertTrue(torch.count_nonzero(neighbours.grad[:, :1]) > 0)

    def test_tiny_label_free_training_reduces_reconstruction_loss(self):
        torch.random.default_generator.manual_seed(41)
        model = CentralOnlyVAE(spectral_dim=4, hidden_dim=8, latent_dim=2)
        with tempfile.TemporaryDirectory() as temporary:
            _, history = train_vae(model, RepeatedCentreDataset(), temporary,
                                   epochs=40, batch_size=4, learning_rate=0.01,
                                   seed=41, device="cpu", save_checkpoint=False)
        first = sum(row["reconstruction_loss"] for row in history[:5]) / 5
        last = sum(row["reconstruction_loss"] for row in history[-5:]) / 5
        self.assertEqual(len(history), 40)
        self.assertTrue(all(math.isfinite(row["total_loss"]) for row in history))
        self.assertLess(last, first - 0.1)


if __name__ == "__main__":
    unittest.main()
