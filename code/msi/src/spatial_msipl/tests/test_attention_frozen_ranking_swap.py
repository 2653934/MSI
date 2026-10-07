"""Small non-GPU checks for the frozen attention ranking intervention."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import torch

from evaluate_spatial_attention_frozen_ranking_swap import (
    completeness_summary,
    component_rankings,
    selected_pixel_indices,
    validate_gmm_provenance,
)
from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.neighbourhood import UniformMeanNeighbourhood


class FrozenRankingSwapTests(unittest.TestCase):
    def test_uniform_weight_override_preserves_model_state_and_real_inputs(self):
        torch.manual_seed(7)
        model = NeighbourhoodSpatialVAE(4, neighbourhood="attention", hidden_dim=8,
                                        latent_dim=2, attention_dim=3,
                                        attention_input_scale="sqrt_bins")
        model.eval()
        central = torch.rand(2, 4)
        neighbours = torch.rand(2, 8, 4)
        mask = torch.tensor([[True, True, False, False, False, False, False, False],
                             [True, False, False, False, False, False, False, False]])
        before = {name: value.clone() for name, value in model.state_dict().items()}
        model.aggregator.forward = UniformMeanNeighbourhood().forward
        contextual, context, weights = model.build_contextual_input(central, neighbours, mask)
        expected_context, expected_weights = UniformMeanNeighbourhood()(central, neighbours, mask)
        torch.testing.assert_close(context, expected_context)
        torch.testing.assert_close(weights, expected_weights)
        torch.testing.assert_close(contextual[:, :4], central)
        for name, value in model.state_dict().items():
            torch.testing.assert_close(value, before[name])

    def test_selected_pixels_reuse_frozen_components(self):
        labels = np.array([1, 0, 1, 0])
        records = [
            {"pixel_index": 0, "component": 1},
            {"pixel_index": 1, "component": 0},
        ]
        self.assertEqual(selected_pixel_indices(records, labels, [0, 1], 1), {0: [1], 1: [0]})
        records[1]["component"] = 1
        with self.assertRaisesRegex(ValueError, "target disagrees"):
            selected_pixel_indices(records, labels, [0, 1], 1)

    def test_component_round_robin_is_deterministic(self):
        scores = {0: np.array([4.0, 1.0, 2.0, 0.0]),
                  1: np.array([0.0, 5.0, 1.0, 2.0])}
        first = component_rankings(scores, 4)
        second = component_rankings(scores, 4)
        np.testing.assert_array_equal(first, second)
        self.assertEqual(set(first.tolist()), set(range(4)))

    def test_completeness_thresholds_match_production(self):
        checks = [{"completeness_residual": 0.001, "score_delta": 0.1}] * 4
        self.assertTrue(completeness_summary(checks)["passed"])
        checks[0] = {"completeness_residual": 0.1, "score_delta": 0.1}
        self.assertFalse(completeness_summary(checks)["passed"])

    def test_input_swap_gmm_provenance_is_explicit(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            attribution = root / "attribution"
            attribution.mkdir()
            original = attribution / "gmm_parameters.npz"
            original.touch()
            separate = root / "fixed_real_input_gmm.npz"
            separate.touch()
            self.assertTrue(validate_gmm_provenance(
                {"source": "pre-existing real-input attribution", "parameters": str(original)},
                attribution,
            ))
            self.assertFalse(validate_gmm_provenance(
                {"source": "fit once on real-input latent vectors", "parameters": str(separate)},
                attribution,
            ))
            with self.assertRaisesRegex(ValueError, "different attribution GMM"):
                validate_gmm_provenance(
                    {"source": "pre-existing real-input attribution", "parameters": str(separate)},
                    attribution,
                )


if __name__ == "__main__":
    unittest.main()
