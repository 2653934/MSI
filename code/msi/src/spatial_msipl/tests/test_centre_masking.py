"""Item G (15 October): training-only random centre masking.

Predeclared checks (supervisor chat, 2026-10-15 13:30): masking applies only
in training; the reconstruction target is the unmasked centre; masked rows get
no gradient through the centre input; with p = 0 a run reproduces the existing
training step for step on a synthetic example.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

from spatial_msipl import training
from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.neighbourhood import AttentionNeighbourhood
from spatial_msipl.tests.test_neighbourhood import TinyNeighbourhoodDataset
from spatial_msipl.training import (
    _atomic_torch_save,
    apply_centre_mask,
    msipl_vae_loss,
    set_random_seed,
    train_vae,
)

TIMING_KEYS = {"epoch_seconds", "samples_per_second"}


def build(neighbourhood="attention"):
    set_random_seed(1)
    return NeighbourhoodSpatialVAE(
        spectral_dim=6, neighbourhood=neighbourhood, hidden_dim=4,
        latent_dim=2, attention_dim=2,
    )


def without_timing(history):
    return [{k: v for k, v in record.items() if k not in TIMING_KEYS} for record in history]


class RecordingModel(NeighbourhoodSpatialVAE):
    """Records the centre spectra the training loop passes to the model."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_central = []

    def forward(self, central, neighbours, neighbour_mask):
        self.seen_central.append(central.detach().clone())
        return super().forward(central, neighbours, neighbour_mask)


class CentreMaskTests(unittest.TestCase):
    def train(self, model, directory, **options):
        return train_vae(model=model, dataset=TinyNeighbourhoodDataset(),
                         output_directory=directory, epochs=2, batch_size=4,
                         seed=1, save_checkpoint=False, **options)

    def test_helper_zeroes_whole_rows_and_leaves_input_untouched(self):
        central = torch.rand(64, 5, generator=torch.Generator().manual_seed(3)) + 0.1
        original = central.clone()
        masked_input, masked = apply_centre_mask(
            central, 0.5, torch.Generator().manual_seed(9))
        torch.testing.assert_close(central, original)
        self.assertTrue(torch.all(masked_input[masked] == 0))
        torch.testing.assert_close(masked_input[~masked], central[~masked])
        self.assertTrue(0 < int(masked.sum()) < 64)
        again, masked_again = apply_centre_mask(
            central, 0.5, torch.Generator().manual_seed(9))
        self.assertTrue(torch.equal(masked, masked_again))
        torch.testing.assert_close(again, masked_input)

    def test_p0_reproduces_existing_training_step_for_step(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline_model = build()
            _, baseline = self.train(baseline_model, Path(directory) / "a")
            state_after_baseline = torch.get_rng_state()
            p0_model = build()
            metadata, p0 = self.train(p0_model, Path(directory) / "b",
                                      centre_mask_probability=0.0, centre_mask_seed=5)
            state_after_p0 = torch.get_rng_state()
        self.assertEqual(without_timing(p0), without_timing(baseline))
        self.assertNotIn("centre_masking", metadata)
        self.assertNotIn("centre_masked_fraction", p0[0])
        for name, tensor in baseline_model.state_dict().items():
            self.assertTrue(torch.equal(tensor, p0_model.state_dict()[name]), name)
        self.assertTrue(torch.equal(state_after_baseline, state_after_p0))

    def test_target_is_always_the_unmasked_centre(self):
        dataset_centres = TinyNeighbourhoodDataset().central
        targets = []

        def recording_loss(reconstruction, target, mean, log_variance, beta=1.0):
            targets.append(target.detach().clone())
            return msipl_vae_loss(reconstruction, target, mean, log_variance, beta=beta)

        set_random_seed(1)
        model = RecordingModel(spectral_dim=6, neighbourhood="attention",
                               hidden_dim=4, latent_dim=2, attention_dim=2)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(training, "msipl_vae_loss", side_effect=recording_loss):
            metadata, history = self.train(model, directory,
                                           centre_mask_probability=0.5, centre_mask_seed=5)
        target_rows = torch.cat(targets)
        seen_rows = torch.cat(model.seen_central)
        # Every target is a real centre spectrum (none zeroed).
        for row in target_rows:
            self.assertTrue(any(torch.equal(row, centre) for centre in dataset_centres))
        zeroed = (seen_rows == 0).all(dim=1)
        self.assertGreater(int(zeroed.sum()), 0)
        self.assertLess(int(zeroed.sum()), len(seen_rows))
        torch.testing.assert_close(seen_rows[~zeroed], target_rows[~zeroed])
        self.assertEqual(sum(r["centre_masked_samples"] for r in history), int(zeroed.sum()))
        self.assertEqual(metadata["centre_masking"]["masked_samples_total"], int(zeroed.sum()))
        self.assertEqual(metadata["centre_masking"]["seed"], 5)

    def test_masked_rows_receive_no_gradient_through_the_centre_input(self):
        model = build()
        model.train()
        dataset = TinyNeighbourhoodDataset()
        centre = dataset.central.clone().requires_grad_(True)
        target = dataset.central.clone()
        encoder_input, masked = apply_centre_mask(
            centre, 0.5, torch.Generator().manual_seed(4))
        self.assertTrue(0 < int(masked.sum()) < len(masked))
        reconstruction, mean, log_variance = model(
            encoder_input, dataset.neighbours, dataset.mask)[:3]
        loss = msipl_vae_loss(reconstruction, target, mean, log_variance)[0]
        loss.backward()
        self.assertTrue(torch.all(centre.grad[masked] == 0))
        self.assertTrue(torch.all(centre.grad[~masked].abs().sum(dim=1) > 0))

    def test_masked_row_attention_depends_only_on_neighbours_and_bias(self):
        # Supervisor chat 2026-10-15 15:35, point 2(a): the masked query is
        # tanh(bias), a learned constant, so masked-row weights are chosen by
        # neighbour content alone and are not forced to be uniform.
        set_random_seed(3)
        aggregator = AttentionNeighbourhood(6, attention_dim=2, input_scale="sqrt_bins")
        with torch.no_grad():
            aggregator.projection.bias.copy_(torch.tensor([1.5, -0.8]))
        dataset = TinyNeighbourhoodDataset()
        other_centres = torch.rand(8, 6, generator=torch.Generator().manual_seed(21))
        all_rows = torch.Generator().manual_seed(0)
        weights = []
        for centres in (dataset.central, other_centres / other_centres.sum(1, keepdim=True)):
            masked_input, masked = apply_centre_mask(centres, 1.0, all_rows)
            self.assertTrue(bool(masked.all()))
            weights.append(aggregator(masked_input, dataset.neighbours, dataset.mask)[1])
        torch.testing.assert_close(weights[0], weights[1])
        self.assertGreater(float((weights[0] - 1 / 8).abs().max()), 1e-4)
        unmasked = aggregator(dataset.central, dataset.neighbours, dataset.mask)[1]
        self.assertFalse(torch.allclose(unmasked, weights[0]))

    def test_masking_lives_only_in_the_training_loop(self):
        # The model carries no masking state, so evaluation, GMM and IG see
        # the unmasked centre exactly as before.
        with tempfile.TemporaryDirectory() as directory:
            model = build()
            configuration_before = model.configuration()
            self.train(model, directory, centre_mask_probability=0.5, centre_mask_seed=5)
        self.assertEqual(model.configuration(), configuration_before)
        model.eval()
        dataset = TinyNeighbourhoodDataset()
        with torch.no_grad():
            first = model.encode(dataset.central, dataset.neighbours, dataset.mask)[0]
            second = model.encode(dataset.central, dataset.neighbours, dataset.mask)[0]
            zeroed = model.encode(torch.zeros_like(dataset.central),
                                  dataset.neighbours, dataset.mask)[0]
        # Evaluation is deterministic and uses the real centre, not a zeroed one.
        torch.testing.assert_close(first, second)
        self.assertFalse(torch.allclose(first, zeroed))

    def test_masking_is_seeded_and_requires_an_explicit_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            _, first = self.train(build(), Path(directory) / "a",
                                  centre_mask_probability=0.5, centre_mask_seed=5)
            _, second = self.train(build(), Path(directory) / "b",
                                   centre_mask_probability=0.5, centre_mask_seed=5)
            with self.assertRaisesRegex(ValueError, "explicit centre_mask_seed"):
                self.train(build(), Path(directory) / "c", centre_mask_probability=0.5)
            with self.assertRaisesRegex(ValueError, r"\[0, 1\]"):
                self.train(build(), Path(directory) / "d",
                           centre_mask_probability=1.5, centre_mask_seed=5)
        self.assertEqual(without_timing(first), without_timing(second))

    def test_masked_run_resumes_exactly(self):
        options = {"epochs": 3, "batch_size": 4, "seed": 1, "checkpoint_interval": 1,
                   "centre_mask_probability": 0.5, "centre_mask_seed": 5}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            full_model = build()
            _, full = train_vae(model=full_model, dataset=TinyNeighbourhoodDataset(),
                                output_directory=root / "full",
                                checkpoint_directory=root / "full_ckpt", **options)

            def save_then_interrupt(value, path):
                _atomic_torch_save(value, path)
                raise RuntimeError("simulated interruption")

            with patch("spatial_msipl.training._atomic_torch_save",
                       side_effect=save_then_interrupt):
                with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                    train_vae(model=build(), dataset=TinyNeighbourhoodDataset(),
                              output_directory=root / "cut",
                              checkpoint_directory=root / "cut_ckpt", **options)
            resumed_model = build()
            metadata, resumed = train_vae(
                model=resumed_model, dataset=TinyNeighbourhoodDataset(),
                output_directory=root / "resumed", checkpoint_directory=root / "cut_ckpt",
                resume_checkpoint=root / "cut_ckpt" / "checkpoint_latest.pt", **options)
            with self.assertRaisesRegex(ValueError, "does not match"):
                train_vae(model=build(), dataset=TinyNeighbourhoodDataset(),
                          output_directory=root / "wrong",
                          checkpoint_directory=root / "cut_ckpt",
                          resume_checkpoint=root / "full_ckpt" / "checkpoint.pt",
                          **{**options, "centre_mask_seed": 6})
        self.assertEqual(metadata["resumed_from_epoch"], 1)
        self.assertEqual(without_timing(resumed), without_timing(full))
        for name, tensor in full_model.state_dict().items():
            self.assertTrue(torch.equal(tensor, resumed_model.state_dict()[name]), name)


if __name__ == "__main__":
    unittest.main()
