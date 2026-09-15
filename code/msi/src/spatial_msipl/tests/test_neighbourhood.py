"""Tests for the three controlled neighbourhood aggregation variants."""

import unittest
import tempfile
from pathlib import Path

import torch
from torch.utils.data import Dataset

from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.neighbourhood import (
    AttentionNeighbourhood,
    DepthwiseNeighbourhood,
    UniformMeanNeighbourhood,
)
from spatial_msipl.training import set_random_seed, train_vae


class TinyNeighbourhoodDataset(Dataset):
    """Synthetic measured neighbours for testing the shared training loop."""

    path = "synthetic-neighbourhood-data"

    def __init__(self):
        generator = torch.Generator().manual_seed(11)
        central = torch.rand(8, 6, generator=generator)
        self.central = central / central.sum(dim=1, keepdim=True)
        neighbours = torch.rand(8, 8, 6, generator=generator)
        self.neighbours = neighbours / neighbours.sum(dim=2, keepdim=True)
        self.mask = torch.ones(8, 8, dtype=torch.bool)

    def __len__(self):
        return len(self.central)

    def __getitem__(self, index):
        return {
            "target": self.central[index],
            "neighbours": self.neighbours[index],
            "neighbour_mask": self.mask[index],
            "x": index % 4 + 1,
            "y": index // 4 + 1,
        }


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

    def test_attention_scale_is_explicit_and_default_is_backward_compatible(self):
        torch.manual_seed(5)
        default = AttentionNeighbourhood(spectral_dim=3, attention_dim=2)
        torch.manual_seed(5)
        explicit = AttentionNeighbourhood(
            spectral_dim=3,
            attention_dim=2,
            input_scale="spectral_bins",
        )
        default_weights = default(self.central, self.neighbours, self.mask)[1]
        explicit_weights = explicit(self.central, self.neighbours, self.mask)[1]
        torch.testing.assert_close(default_weights, explicit_weights)
        self.assertNotIn("input_scale", default.configuration())
        sqrt_scaled = AttentionNeighbourhood(
            spectral_dim=9,
            attention_dim=2,
            input_scale="sqrt_bins",
        )
        self.assertEqual(sqrt_scaled.configuration()["input_scale"], 3.0)

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

    def test_seeded_variants_start_with_identical_vae_weights(self):
        states = []
        for name in ("uniform_mean", "depthwise", "attention"):
            set_random_seed(17)
            model = NeighbourhoodSpatialVAE(
                spectral_dim=6,
                neighbourhood=name,
                hidden_dim=4,
                latent_dim=2,
                attention_dim=2,
            )
            states.append(model.vae.state_dict())
        for parameter_name in states[0]:
            torch.testing.assert_close(states[0][parameter_name], states[1][parameter_name])
            torch.testing.assert_close(states[0][parameter_name], states[2][parameter_name])

    def test_neighbourhood_model_uses_shared_training_loop(self):
        set_random_seed(1)
        model = NeighbourhoodSpatialVAE(
            spectral_dim=6,
            neighbourhood="attention",
            hidden_dim=4,
            latent_dim=2,
            attention_dim=2,
        )
        initial_attention_weights = model.aggregator.projection.weight.detach().clone()
        with tempfile.TemporaryDirectory() as temporary_directory:
            metadata, history = train_vae(
                model=model,
                dataset=TinyNeighbourhoodDataset(),
                output_directory=temporary_directory,
                epochs=1,
                batch_size=4,
                seed=1,
            )
            self.assertEqual(metadata["model"], "NeighbourhoodSpatialVAE")
            self.assertEqual(metadata["selected_indices"], list(range(8)))
            self.assertTrue(Path(temporary_directory, "checkpoint.pt").is_file())
            self.assertTrue(torch.isfinite(torch.tensor(history[0]["total_loss"])))
            self.assertFalse(
                torch.equal(
                    initial_attention_weights,
                    model.aggregator.projection.weight.detach(),
                )
            )

    def test_training_logs_spatial_loss_separately(self):
        set_random_seed(1)
        model = NeighbourhoodSpatialVAE(
            spectral_dim=6,
            neighbourhood="uniform_mean",
            hidden_dim=4,
            latent_dim=2,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            metadata, history = train_vae(
                model=model,
                dataset=TinyNeighbourhoodDataset(),
                output_directory=temporary_directory,
                epochs=1,
                batch_size=8,
                seed=1,
                spatial_lambda=0.1,
                save_checkpoint=False,
            )
        self.assertEqual(metadata["spatial_lambda"], 0.1)
        self.assertGreater(history[0]["spatial_pairs"], 0)
        self.assertGreaterEqual(history[0]["spatial_loss"], 0.0)
        self.assertAlmostEqual(
            history[0]["total_loss"],
            history[0]["vae_loss"] + history[0]["weighted_spatial_loss"],
            places=4,
        )


if __name__ == "__main__":
    unittest.main()
