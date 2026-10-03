"""Small-data checks for the real-versus-shuffled input diagnostic."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np

from spatial_msipl.preprocessing import H5SpatialContextDataset


sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from audit_spatial_context_information import compare_section, cosine


class SpatialContextInformationTests(unittest.TestCase):
    def test_cosine_and_zero_vector(self):
        self.assertAlmostEqual(cosine(np.array([1., 0.]), np.array([1., 0.])), 1.)
        self.assertIsNone(cosine(np.array([1., 0.]), np.array([0., 0.])))

    def test_tiny_h5_matches_seeded_shuffled_input(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            path = root / "toy.h5"
            x = np.tile(np.arange(1, 6), 5)
            y = np.repeat(np.arange(1, 6), 5)
            labels = (x > 2).astype(np.int64)
            spectra = np.arange(25 * 4, dtype=np.float32).reshape(25, 4) + 1
            with h5py.File(path, "w") as handle:
                handle["Data"] = spectra
                handle["mzArray"] = np.arange(4, dtype=np.float32) + 100
                handle["xLocation"] = x
                handle["yLocation"] = y
                handle["Class_Label"] = labels
            shuffled = H5SpatialContextDataset(
                path, window_size=3, context_mode="shuffled", context_seed=1701
            )
            try:
                expected_hash = shuffled.context_permutation_sha256
            finally:
                shuffled.close()
            metadata = root / "metadata.json"
            metadata.write_text(json.dumps({"experiment": {
                "context_seed": 1701,
                "context_permutation_sha256": expected_hash,
            }}), encoding="utf-8")
            result = compare_section(path, metadata, root / "output", 2, 23)
            self.assertEqual(result["status"], "valid")
            self.assertEqual(result["context_permutation_sha256"], expected_hash)
            self.assertEqual(len(result["streamed_vs_cached_canary_max_abs_errors"]), 3)
            self.assertLessEqual(
                max(result["streamed_vs_cached_canary_max_abs_errors"]), 1e-6
            )
            self.assertGreater(result["groups"]["boundary"]["sampled_centres"], 0)
            self.assertGreater(result["groups"]["interior"]["sampled_centres"], 0)


if __name__ == "__main__":
    unittest.main()
