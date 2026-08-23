import sys
import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np


S3PL_ROOT = Path(__file__).resolve().parents[1]
if str(S3PL_ROOT) not in sys.path:
    sys.path.insert(0, str(S3PL_ROOT))

from utils.create_pearson_labels import create_pearson_labels
from utils.data_source import H5SpectrumPatchDataset, load_massnet_h5


class MassNetH5AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.path = self.root / "synthetic.h5"

        self.mz = np.array([100.0, 101.0, 102.0, 103.0, 104.0], dtype=np.float32)
        self.x = np.array([1, 3, 2, 1], dtype=np.int32)
        self.y = np.array([1, 1, 2, 3], dtype=np.int32)
        self.spectra = np.array(
            [
                [0.0, 10.0, 5.0, 0.0, 2.0],
                [10.0, 0.0, 5.0, 1.0, 3.0],
                [10.0, 0.0, 5.0, 0.0, 4.0],
                [0.0, 10.0, 5.0, 1.0, 5.0],
            ],
            dtype=np.float32,
        )

        with h5py.File(self.path, "w") as handle:
            # Use the MassNet orientation (m/z, pixels) to exercise transposition.
            handle.create_dataset("Data", data=self.spectra.T)
            handle.create_dataset("mzArray", data=self.mz)
            handle.create_dataset("xLocation", data=self.x)
            handle.create_dataset("yLocation", data=self.y)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_loader_orients_massnet_data(self):
        table = load_massnet_h5(self.path)
        np.testing.assert_array_equal(table.spectra, self.spectra)
        np.testing.assert_array_equal(table.mz_values, self.mz)
        np.testing.assert_array_equal(table.x, self.x)
        np.testing.assert_array_equal(table.y, self.y)

    def test_patches_use_only_real_spectra_as_centres(self):
        table = load_massnet_h5(self.path)
        dataset = H5SpectrumPatchDataset(table, patch_size=3)

        self.assertEqual(len(dataset), 4)
        patch, centre_index = dataset[2]
        self.assertEqual(centre_index, 2)
        self.assertEqual(patch.shape, (1, 5, 3, 3))

        np.testing.assert_array_equal(patch[0, :, 1, 1], self.spectra[2])
        np.testing.assert_array_equal(patch[0, :, 0, 0], self.spectra[0])
        np.testing.assert_array_equal(patch[0, :, 0, 2], self.spectra[1])
        np.testing.assert_array_equal(patch[0, :, 2, 0], self.spectra[3])
        np.testing.assert_array_equal(patch[0, :, 1, 0], np.zeros(5))

    def test_pearson_labels_ignore_unmeasured_grid_locations(self):
        mask_dir = self.root / "masks"
        mask_dir.mkdir()
        mask = np.zeros((3, 3), dtype=np.uint8)
        mask[self.y - 1, self.x - 1] = np.array([0, 1, 1, 0], dtype=np.uint8)
        np.save(mask_dir / "synthetic_mask.npy", mask)

        create_pearson_labels(
            "synthetic",
            str(self.root),
            num_classes=2,
            data_path=self.path,
        )

        class_zero = np.load(self.root / "labels" / "synthetic_class0_ranking.npy")
        class_one = np.load(self.root / "labels" / "synthetic_class1_ranking.npy")
        correlations = np.load(
            self.root / "labels" / "synthetic_class1_pearson_ranking.npy"
        )

        self.assertEqual(class_zero[0], 1)
        self.assertEqual(class_one[0], 0)
        self.assertEqual(len(class_one), len(self.mz))
        self.assertAlmostEqual(correlations[0], 1.0)


if __name__ == "__main__":
    unittest.main()
