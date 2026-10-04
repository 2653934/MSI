"""Synthetic checks for the frozen, paired attention input intervention."""

import unittest

import numpy as np
import torch

from audit_spatial_attention_input_swap import evaluate_pair, reconstruction_errors
from spatial_msipl.attribution import gmm_posterior


class TinyDataset:
    def __init__(self, shuffled=False):
        self.mz_values = np.array([100.0, 200.0], dtype=np.float32)
        self.neighbour_slots = np.array([[1], [0]], dtype=np.int64)
        self.centres = torch.tensor([[0.8, 0.2], [0.2, 0.8]])
        self.neighbours = torch.tensor([[[0.2, 0.8]], [[0.8, 0.2]]])
        if shuffled:
            self.neighbours = torch.flip(self.neighbours, dims=(0,))

    def __len__(self):
        return 2

    def __getitem__(self, index):
        return {
            "index": index,
            "target": self.centres[index],
            "neighbours": self.neighbours[index],
            "neighbour_mask": torch.tensor([True]),
        }


class TinyModel:
    class Decoder:
        @staticmethod
        def decode(latent):
            return torch.sigmoid(latent)

    def __init__(self):
        self.vae = self.Decoder()

    @staticmethod
    def encode(central, neighbours, mask):
        del mask
        return (central + neighbours[:, 0],)


class AttentionInputSwapTests(unittest.TestCase):
    def test_reconstruction_errors_are_zero_for_identical_normalized_spectra(self):
        target = torch.tensor([[0.8, 0.2]])
        mse, cross_entropy = reconstruction_errors(target, target)
        self.assertAlmostEqual(float(mse[0]), 0.0)
        self.assertGreater(float(cross_entropy[0]), 0.0)

    def test_paired_intervention_uses_original_model_and_gmm(self):
        real, shuffled, model = TinyDataset(), TinyDataset(True), TinyModel()
        gmm = {
            "scaler_mean": torch.zeros(2),
            "scaler_scale": torch.ones(2),
            "mixture_weights": torch.tensor([0.5, 0.5]),
            "component_means": torch.tensor([[1.0, 1.0], [0.0, 0.0]]),
            "precision_cholesky": torch.stack([torch.eye(2), torch.eye(2)]),
        }
        latent = np.stack([
            model.encode(real[index]["target"][None], real[index]["neighbours"][None], None)[0][0].numpy()
            for index in range(2)
        ])
        probabilities = gmm_posterior(torch.as_tensor(latent), **gmm).numpy()
        labels = probabilities.argmax(axis=1)
        confidence = probabilities[np.arange(2), labels]
        metrics = evaluate_pair(
            model, real, shuffled, gmm, batch_size=2, device=torch.device("cpu"),
            original_labels=labels, original_latent=latent, original_confidence=confidence,
        )
        self.assertEqual(metrics["pixels"], 2)
        self.assertEqual(metrics["changed_context_fraction"], 1.0)
        self.assertGreater(metrics["mean_latent_l2_change"], 0.0)

    def test_paired_intervention_rejects_central_change(self):
        real, shuffled = TinyDataset(), TinyDataset(True)
        shuffled.centres[0, 0] = 0.7
        with self.assertRaisesRegex(ValueError, "central spectra changed"):
            evaluate_pair(
                TinyModel(), real, shuffled, {}, 2, torch.device("cpu"),
                np.zeros(2), np.zeros((2, 2)), np.zeros(2),
            )


if __name__ == "__main__":
    unittest.main()
