"""Small checks for frozen-latent clustering comparisons."""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from audit_spatial_unsupervised_clusterers import (
    GMM_COVARIANCES, fit_candidates, summarize_records,
)


class UnsupervisedClustererTests(unittest.TestCase):
    def test_selection_uses_bic_before_expert_labels(self):
        rng = np.random.default_rng(31)
        latent = np.concatenate((
            rng.normal(loc=-3, scale=0.4, size=(20, 2)),
            rng.normal(loc=3, scale=0.4, size=(20, 2)),
        ))
        records, selected = fit_candidates(latent, 2, seeds=(1, 2), n_init=2)
        self.assertEqual(len(records), 2 * (len(GMM_COVARIANCES) + 1))
        self.assertEqual(
            selected["bic"], min(
                record["bic"] for record in records if record["method"].startswith("gmm_")
            ),
        )
        labels = np.repeat([0, 1], 20)
        first = summarize_records(records, selected, labels, records[0]["predicted"])
        second = summarize_records(records, selected, labels[::-1], records[0]["predicted"])
        self.assertEqual(
            first["selected_gmm_by_bic"]["method"],
            second["selected_gmm_by_bic"]["method"],
        )
        self.assertEqual(
            first["selected_gmm_by_bic"]["bic"],
            second["selected_gmm_by_bic"]["bic"],
        )
        self.assertEqual(len(first["candidates"]), len(records))
        self.assertTrue(all("predicted" not in row for row in first["candidates"]))


if __name__ == "__main__":
    unittest.main()
