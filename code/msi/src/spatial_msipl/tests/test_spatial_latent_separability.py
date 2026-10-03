"""Checkpoint-free checks for post-hoc latent-versus-GMM diagnostics."""

import sys
import unittest
from pathlib import Path

import numpy as np
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from audit_spatial_latent_separability import evaluate_latent, neighbour_label_purity


class LatentSeparabilityTests(unittest.TestCase):
    def test_perfectly_separated_classes(self):
        rng = np.random.default_rng(13)
        latent = np.concatenate((
            rng.normal(loc=-4.0, scale=0.3, size=(20, 2)),
            rng.normal(loc=4.0, scale=0.3, size=(20, 2)),
        ))
        labels = np.repeat([0, 1], 20)
        standardized = StandardScaler().fit_transform(latent)
        saved = GaussianMixture(
            n_components=2, covariance_type="full", n_init=2, random_state=1
        ).fit_predict(standardized)
        result = evaluate_latent(
            latent, labels, saved, seeds=(1, 2), gmm_n_init=2
        )
        self.assertAlmostEqual(result["saved_gmm_class_ari"], 1.0)
        self.assertAlmostEqual(result["linear_probe"]["balanced_accuracy"], 1.0)
        self.assertAlmostEqual(
            result["gmm_refits"][0]["agreement_ari_with_saved_components"], 1.0
        )
        self.assertAlmostEqual(
            result["ten_nearest_latent_neighbours_same_class_fraction"], 1.0
        )

    def test_neighbour_purity_excludes_centre(self):
        latent = np.asarray([[0.], [0.1], [10.], [10.1]])
        labels = np.asarray([0, 0, 1, 1])
        self.assertAlmostEqual(neighbour_label_purity(latent, labels, neighbours=1), 1.0)


if __name__ == "__main__":
    unittest.main()
