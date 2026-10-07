"""Check the differentiable GMM target and IG against a closed-form toy case."""

import math
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import torch

attribution_path = Path(__file__).resolve().parents[1] / "attribution.py"
spec = importlib.util.spec_from_file_location("spatial_msipl_attribution", attribution_path)
attribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(attribution)
gmm_posterior = attribution.gmm_posterior
integrated_gradients_cluster_posterior = attribution.integrated_gradients_cluster_posterior
audit_path = Path(__file__).resolve().parents[3] / "scripts/audit_spatial_ig_ranking_provenance.py"
audit_spec = importlib.util.spec_from_file_location("spatial_ig_ranking_audit", audit_path)
audit = importlib.util.module_from_spec(audit_spec)
audit_spec.loader.exec_module(audit)


class LinearLatentEncoder:
    def encode(self, central, neighbours, neighbour_mask):
        valid_first_slot = neighbour_mask[:, :1].to(central.dtype)
        mean = 1.2 * central[:, :1] - 0.4 * neighbours[:, 0, :1] * valid_first_slot
        return mean, torch.zeros_like(mean)


def two_equal_gaussians():
    # N(-1, 1) and N(+1, 1), both with prior 0.5.
    # Their component-1 posterior is analytically sigmoid(2 * latent).
    return {
        "scaler_mean": torch.tensor([0.0], dtype=torch.float64),
        "scaler_scale": torch.tensor([1.0], dtype=torch.float64),
        "mixture_weights": torch.tensor([0.5, 0.5], dtype=torch.float64),
        "component_means": torch.tensor([[-1.0], [1.0]], dtype=torch.float64),
        "precision_cholesky": torch.ones(2, 1, 1, dtype=torch.float64),
    }


def logistic(value):
    return 1.0 / (1.0 + math.exp(-value))


class AnalyticAttributionReferenceTests(unittest.TestCase):
    def test_independent_audit_reference_and_balanced_collision(self):
        parameters = {
            "scaler_mean": np.array([0.0]),
            "scaler_scale": np.array([1.0]),
            "mixture_weights": np.array([0.5, 0.5]),
            "component_means": np.array([[-1.0], [1.0]]),
            "covariances": np.array([[[1.0]], [[1.0]]]),
        }
        latent = np.array([[-0.8], [0.0], [0.7]])
        posterior = audit.independent_gmm_posterior(latent, parameters)
        np.testing.assert_allclose(posterior[:, 1],
                                   [logistic(2 * x) for x in latent[:, 0]],
                                   rtol=1e-12, atol=1e-12)
        indices, sources = audit.independent_balanced_order({
            0: np.array([0.9, 0.8, 0.1]),
            1: np.array([0.95, 0.7, 0.6]),
        }, 3)
        np.testing.assert_array_equal(indices, [0, 1, 2])
        np.testing.assert_array_equal(sources, [0, 1, 0])

    def test_gmm_probability_and_derivative_match_logistic_reference(self):
        latent = torch.tensor([[-0.8], [0.0], [0.7]], dtype=torch.float64,
                              requires_grad=True)
        probability = gmm_posterior(latent, **two_equal_gaussians())[:, 1]
        expected = torch.tensor([logistic(2 * value) for value in (-0.8, 0.0, 0.7)],
                                dtype=torch.float64)
        torch.testing.assert_close(probability, expected, rtol=1e-12, atol=1e-12)
        probability.sum().backward()
        torch.testing.assert_close(latent.grad[:, 0], 2 * expected * (1 - expected),
                                   rtol=1e-12, atol=1e-12)

    def test_ig_paths_match_closed_form_integral(self):
        model = LinearLatentEncoder()
        central = torch.tensor([[0.6, 0.4]], dtype=torch.float64)
        baseline = torch.tensor([[0.2, 0.8]], dtype=torch.float64)
        neighbours = torch.zeros(1, 8, 2, dtype=torch.float64)
        neighbour_baseline = torch.zeros_like(neighbours)
        neighbours[0, 0, 0] = 0.8
        neighbour_baseline[0, 0, 0] = 0.1
        # This masked-out slot changes along the path but must contribute zero.
        neighbours[0, 1, 0] = 0.9
        mask = torch.tensor([[True] + [False] * 7])
        central_ig, neighbour_ig, checks = integrated_gradients_cluster_posterior(
            model, central, neighbours, mask, baseline, neighbour_baseline,
            target_component=1, gmm_parameters=two_equal_gaussians(),
            steps=512, internal_batch_size=32)
        z_start = 1.2 * 0.2 - 0.4 * 0.1
        z_end = 1.2 * 0.6 - 0.4 * 0.8
        average_derivative = (logistic(2 * z_end) - logistic(2 * z_start)) / (z_end - z_start)
        expected_central = (0.6 - 0.2) * 1.2 * average_derivative
        expected_neighbour = (0.8 - 0.1) * -0.4 * average_derivative
        self.assertAlmostEqual(central_ig[0, 0].item(), expected_central, places=6)
        self.assertAlmostEqual(neighbour_ig[0, 0, 0].item(), expected_neighbour, places=6)
        self.assertEqual(torch.count_nonzero(central_ig[0, 1:]).item(), 0)
        self.assertEqual(torch.count_nonzero(neighbour_ig[0, 1:]).item(), 0)
        self.assertLess(abs(checks["completeness_residual"]), 1e-6)


if __name__ == "__main__":
    unittest.main()
