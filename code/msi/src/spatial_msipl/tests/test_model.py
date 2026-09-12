"""Small, fast tests for the Spatial-msiPL VAE and its loss."""

import tempfile
import unittest
from pathlib import Path

import torch
from torch.utils.data import Dataset

from spatial_msipl.model import SpatialVAE
from spatial_msipl.training import msipl_vae_loss, train_vae


class TinyContextDataset(Dataset):
    """Deterministic synthetic spectra used only to test the training plumbing."""

    path = "synthetic-test-data"

    def __init__(self, size=8):
        generator = torch.Generator().manual_seed(7)
        central = torch.rand(size, 6, generator=generator)
        self.central = central / central.sum(dim=1, keepdim=True)
        context = torch.rand(size, 6, generator=generator)
        self.contextual = torch.cat((self.central, context), dim=1)

    def __len__(self):
        return len(self.central)

    def __getitem__(self, index):
        return {"input": self.contextual[index], "target": self.central[index]}


class SpatialVAETests(unittest.TestCase):
    def test_encoder_and_decoder_dimensions(self):
        model = SpatialVAE(spectral_dim=12, hidden_dim=8, latent_dim=3)
        model.eval()
        contextual = torch.rand(4, 24)
        with torch.no_grad():
            reconstruction, mean, log_variance = model(contextual)

        self.assertEqual(tuple(mean.shape), (4, 3))
        self.assertEqual(tuple(log_variance.shape), (4, 3))
        self.assertEqual(tuple(reconstruction.shape), (4, 12))
        self.assertTrue(torch.all(reconstruction >= 0))
        self.assertTrue(torch.all(reconstruction <= 1))

    def test_loss_returns_finite_separate_terms(self):
        model = SpatialVAE(spectral_dim=12, hidden_dim=8, latent_dim=3)
        model.eval()
        central = torch.rand(4, 12)
        central = central / central.sum(dim=1, keepdim=True)
        context = torch.rand(4, 12)
        contextual = torch.cat((central, context), dim=1)

        reconstruction, mean, log_variance = model(contextual)
        total, reconstruction_loss, kl_loss = msipl_vae_loss(
            reconstruction, central, mean, log_variance
        )

        self.assertTrue(torch.isfinite(total))
        self.assertTrue(torch.isfinite(reconstruction_loss))
        self.assertTrue(torch.isfinite(kl_loss))
        self.assertAlmostEqual(float(total), float(reconstruction_loss + kl_loss), places=4)

    def test_training_records_losses_and_saves_checkpoint(self):
        model = SpatialVAE(spectral_dim=6, hidden_dim=4, latent_dim=2)
        with tempfile.TemporaryDirectory() as temporary_directory:
            metadata, history = train_vae(
                model=model,
                dataset=TinyContextDataset(),
                output_directory=temporary_directory,
                epochs=1,
                batch_size=4,
                seed=1,
            )
            output = Path(temporary_directory)
            self.assertEqual(metadata["status"], "complete")
            self.assertIn("reconstruction_loss", history[0])
            self.assertIn("kl_loss", history[0])
            self.assertTrue((output / "checkpoint.pt").is_file())
            self.assertTrue((output / "training_history.json").is_file())
            self.assertTrue((output / "metadata.json").is_file())

    def test_training_can_measure_without_saving_checkpoint(self):
        model = SpatialVAE(spectral_dim=6, hidden_dim=4, latent_dim=2)
        with tempfile.TemporaryDirectory() as temporary_directory:
            metadata, _ = train_vae(
                model=model,
                dataset=TinyContextDataset(),
                output_directory=temporary_directory,
                epochs=1,
                batch_size=4,
                seed=1,
                save_checkpoint=False,
            )
            output = Path(temporary_directory)
            self.assertFalse(metadata["checkpoint_saved"])
            self.assertIsNone(metadata["checkpoint"])
            self.assertGreater(metadata["training_seconds"], 0)
            self.assertFalse((output / "checkpoint.pt").exists())

    def test_training_keeps_a_multi_sample_final_batch(self):
        model = SpatialVAE(spectral_dim=6, hidden_dim=4, latent_dim=2)
        with tempfile.TemporaryDirectory() as temporary_directory:
            metadata, history = train_vae(
                model=model,
                dataset=TinyContextDataset(size=10),
                output_directory=temporary_directory,
                epochs=1,
                batch_size=4,
                seed=1,
                save_checkpoint=False,
            )
            self.assertFalse(metadata["drop_last"])
            self.assertEqual(history[0]["samples_seen"], 10)


if __name__ == "__main__":
    unittest.main()
