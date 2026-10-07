"""Synthetic positive and negative controls for the independent data audit."""

import sys
import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from audit_spatial_msipl_data_contract import audit


class DataContractAuditTests(unittest.TestCase):
    def make_inputs(self, root, collection="cac", mz_first=False):
        coordinates = [(1, 1), (2, 1), (1, 2), (2, 2), (3, 2), (1, 3)]
        labels = np.array([0, 1, 2, 0, 1, 2], dtype=np.int64)
        if collection == "gbm":
            labels = np.array([1, 2, 1, 2, 1, 2], dtype=np.int64)
        mask = np.full((3, 3), -1, dtype=np.int64)
        for (x, y), label in zip(coordinates, labels):
            mask[y - 1, x - 1] = label - 1 if collection == "gbm" else label
        mask_path = root / "mask.npy"
        np.save(mask_path, mask)
        spectra = np.array([[i + 1, 2, 3, 4] for i in range(len(labels))], dtype=np.float32)
        spectra[-1] = 0
        h5_path = root / "section.h5"
        with h5py.File(h5_path, "w") as handle:
            handle.create_dataset("Data", data=spectra.T if mz_first else spectra)
            handle.create_dataset("mzArray", data=[100., 101., 102., 103.])
            handle.create_dataset("xLocation", data=[point[0] for point in coordinates])
            handle.create_dataset("yLocation", data=[point[1] for point in coordinates])
            handle.create_dataset("Class_Label", data=labels)
        return h5_path, mask_path

    def test_valid_partial_grid_both_orientations_and_collections(self):
        for collection in ("cac", "gbm"):
            for mz_first in (False, True):
                with self.subTest(collection=collection, mz_first=mz_first):
                    with tempfile.TemporaryDirectory() as temporary:
                        root = Path(temporary)
                        h5_path, mask_path = self.make_inputs(root, collection, mz_first)
                        audit(h5_path, mask_path, root / "audit", collection)
                        self.assertTrue((root / "audit" / "spotcheck.png").is_file())
                        self.assertIn('"status": "valid"',
                                      (root / "audit" / "summary.json").read_text())

    def test_misaligned_mask_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            h5_path, mask_path = self.make_inputs(root)
            mask = np.load(mask_path)
            mask[0, 0] = 2
            np.save(mask_path, mask)
            with self.assertRaisesRegex(AssertionError, "mask and HDF5 labels disagree"):
                audit(h5_path, mask_path, root / "audit", "cac")

    def test_duplicate_coordinates_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            h5_path, mask_path = self.make_inputs(root)
            with h5py.File(h5_path, "r+") as handle:
                handle["xLocation"][1] = 1
            with self.assertRaisesRegex(ValueError, "duplicate measured coordinates"):
                audit(h5_path, mask_path, root / "audit", "cac")


if __name__ == "__main__":
    unittest.main()
