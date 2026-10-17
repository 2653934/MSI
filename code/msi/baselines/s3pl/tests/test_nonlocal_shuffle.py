"""Test N (protocol 18 Section 6.5): shuffled nonlocal neighbours for S3PL patches.

Checks that the centre stays real, that the map is a permutation of the measured
pixels with no local sources, that it matches the VAE shuffled_p3 construction,
that the global RNG stream is untouched, and that the default (released) patch
path is bit-identical to the frozen pre-change copy of utils/data_source.py.
"""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

S3PL_ROOT = Path(__file__).resolve().parents[1]
if str(S3PL_ROOT) not in sys.path:
    sys.path.insert(0, str(S3PL_ROOT))
REPO_SRC = S3PL_ROOT.parents[1] / "src"

from utils.data_source import H5SpectrumPatchDataset, SpectrumTable, build_patch_dataset
from utils.nonlocal_shuffle import (NONLOCAL_SHUFFLE_SEED, NonlocalShuffleM2aiaMixin,
                                    nonlocal_map, nonlocal_source, shuffle_patch_indices)

try:
    import h5py
except ImportError:  # pragma: no cover
    h5py = None


def load_frozen_data_source():
    path = Path(__file__).resolve().parent / "fixtures" / "pre_test_n" / "data_source.py"
    spec = importlib.util.spec_from_file_location("pre_test_n_data_source", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def irregular_table(seed=0, width=13, height=11, bins=6):
    """A section with holes, so some windows have unmeasured positions."""
    rng = np.random.default_rng(seed)
    xs, ys = np.meshgrid(np.arange(1, width + 1), np.arange(1, height + 1))
    keep = rng.random(xs.size) > 0.15
    x, y = xs.ravel()[keep].astype(np.int32), ys.ravel()[keep].astype(np.int32)
    spectra = rng.gamma(2.0, 1.0, (len(x), bins)).astype(np.float32)
    spectra[:, 0] = np.arange(len(x))      # channel 0 identifies the source pixel
    return SpectrumTable(spectra=spectra, mz_values=np.arange(100, 100 + bins, dtype=np.float32),
                         x=x, y=y)


class MapTests(unittest.TestCase):
    def test_map_is_a_derangement_and_one_cycle(self):
        mapping = nonlocal_map(57)
        self.assertEqual(sorted(mapping.tolist()), list(range(57)))
        self.assertFalse(np.any(mapping == np.arange(57)))
        seen, current = set(), 0
        for _ in range(57):
            seen.add(current)
            current = int(mapping[current])
        self.assertEqual(len(seen), 57)          # a single cycle visits every pixel

    def test_map_equals_the_vae_shuffled_context_construction(self):
        order = np.random.default_rng(1701).permutation(40)
        expected = np.empty(40, dtype=np.int64)
        expected[order] = np.roll(order, 1)
        np.testing.assert_array_equal(nonlocal_map(40), expected)
        self.assertEqual(NONLOCAL_SHUFFLE_SEED, 1701)

    def test_map_leaves_the_global_rng_untouched(self):
        np.random.seed(5)
        before = np.random.get_state()[1].copy()
        nonlocal_map(100)
        np.testing.assert_array_equal(np.random.get_state()[1], before)

    def test_source_walk_leaves_the_window(self):
        mapping = nonlocal_map(30)
        forbidden = set(range(10))
        for neighbour in range(30):
            self.assertNotIn(nonlocal_source(mapping, neighbour, forbidden), forbidden)
        with self.assertRaises(ValueError):
            nonlocal_source(mapping, 0, set(range(30)))

    def test_patch_indices_keep_centre_and_unmeasured_slots(self):
        mapping = nonlocal_map(50)
        row = np.array([3, -1, 4, 5, 7, -1, 8, 9, 10])
        shuffled = shuffle_patch_indices(row, 4, set(row[row >= 0].tolist()), mapping)
        self.assertEqual(shuffled[4], 7)
        np.testing.assert_array_equal(shuffled[row < 0], -1)
        others = [s for k, s in enumerate(shuffled) if k != 4 and row[k] >= 0]
        self.assertTrue(all(s not in set(row.tolist()) for s in others))


@unittest.skipIf(h5py is None, "h5py is required")
class H5PathTests(unittest.TestCase):
    def setUp(self):
        self.table = irregular_table()

    def test_default_patches_are_bit_identical_to_the_frozen_copy(self):
        frozen = load_frozen_data_source()
        old = frozen.H5SpectrumPatchDataset(frozen.SpectrumTable(**vars(self.table)), 9)
        new = H5SpectrumPatchDataset(self.table, 9)
        self.assertIsNone(new.patch_sources)
        for index in range(len(new)):
            np.testing.assert_array_equal(new[index][0], old[index][0])

    def test_build_patch_dataset_default_matches_the_frozen_copy_on_an_h5_file(self):
        frozen = load_frozen_data_source()
        path = Path(tempfile.mkdtemp()) / "s.h5"
        with h5py.File(path, "w") as handle:
            handle["Data"] = self.table.spectra.T
            handle["mzArray"] = self.table.mz_values
            handle["xLocation"] = self.table.x
            handle["yLocation"] = self.table.y
        new, mz_new = build_patch_dataset(path, 9)
        old, mz_old = frozen.build_patch_dataset(path, 9)
        np.testing.assert_array_equal(mz_new, mz_old)
        for index in range(0, len(new), 7):
            np.testing.assert_array_equal(new[index][0], old[index][0])

    def test_shuffled_patches(self):
        real = H5SpectrumPatchDataset(self.table, 9)
        shuffled = H5SpectrumPatchDataset(self.table, 9, neighbour_shuffle_seed=1701)
        centre = 40
        for index in range(len(real)):
            a, b = real[index][0], shuffled[index][0]
            # Centre spectrum unchanged.
            np.testing.assert_array_equal(a.reshape(a.shape[1], -1)[:, centre],
                                          b.reshape(b.shape[1], -1)[:, centre])
            row = real.patch_indices[index]
            sources = shuffled.patch_sources[index]
            self.assertEqual(sources[centre], index)
            np.testing.assert_array_equal(sources[row < 0], -1)       # unmeasured stays empty
            window = set(row[row >= 0].tolist())
            for slot in range(81):
                if slot != centre and row[slot] >= 0:
                    self.assertNotIn(int(sources[slot]), window)        # nonlocal
            # The patch is built from the sources: channel 0 is the source pixel id.
            ids = b.reshape(b.shape[1], -1)[0]
            np.testing.assert_array_equal(ids[sources >= 0], sources[sources >= 0])


class FakeImage:
    def __init__(self, table):
        self.table = table

    def GetShape(self):
        return (int(self.table.x.max()) + 1, int(self.table.y.max()) + 1)

    def GetSpectra(self, ids):
        return self.table.spectra[np.asarray(ids)]


class FakeSpectrumDataset:
    """The parts of m2aia.SpectrumDataset.getitems that S3PL uses, copied as a stand-in."""

    def __init__(self, table, shape, transform_data=None):
        self.images = [FakeImage(table)]
        self.shape = shape
        self.spectrum_mask_indices = None
        self.transform_data = transform_data
        self.x_hws = shape[-1] // 2
        self.y_hws = shape[-2] // 2
        self.spectrum_depth = table.spectra.shape[1]
        self.buffer = [(np.zeros(len(table.x), dtype=bool),
                        np.zeros(table.spectra.shape, dtype=np.float32))]
        index_image = -np.ones((1,) + self.images[0].GetShape()[::-1], dtype=np.int32)
        # m2aia positions are zero-based (x, y, z).
        self.elements = []
        for spectrum_id, (x, y) in enumerate(zip(table.x - 1, table.y - 1)):
            index_image[0, y, x] = spectrum_id
            self.elements.append((0, spectrum_id, (int(x), int(y), 0), 0))
        self.index_images = [index_image]

    def __len__(self):
        return len(self.elements)

    def __getitem__(self, index):
        return self.getitems([index])

    def getitems(self, dataset_query_indices):
        query, labels = [], []
        for index in dataset_query_indices:
            image_id, spectrum_id, (x, y, z), label = self.elements[index]
            shape = self.images[image_id].GetShape()
            left, right = np.clip(x - self.x_hws, 0, shape[0]), np.clip(x + self.x_hws + 1, 0, shape[0])
            bottom, top = np.clip(y - self.y_hws, 0, shape[1]), np.clip(y + self.y_hws + 1, 0, shape[1])
            indices = self.index_images[image_id][0, bottom:top, left:right].flatten()
            if any(indices < 0):
                choices = np.random.choice(indices[indices >= 0], len(indices[indices < 0]))
                indices[indices < 0] = choices
            expected = (2 * self.x_hws + 1) * (2 * self.y_hws + 1)
            if len(indices) < expected:
                indices = np.concatenate([indices, np.random.choice(indices, expected - len(indices))])
            query.append(indices)
            labels.append(label)
        indices = np.array(query, dtype=np.int32)
        flags, data = self.buffer[0]
        missing = indices[~flags[indices]]
        if len(missing):
            data[missing] = self.images[0].GetSpectra(missing).astype(np.float32)
            flags[missing] = True
        batch = np.swapaxes(np.reshape(data[indices], (-1,) + self.shape + (self.spectrum_depth,)), 1, 3)
        if self.transform_data is not None:
            batch = self.transform_data(batch)
        return batch, np.array(labels, np.int32)


class FakeShuffled(NonlocalShuffleM2aiaMixin, FakeSpectrumDataset):
    pass


class M2aiaMixinTests(unittest.TestCase):
    def setUp(self):
        self.table = irregular_table(seed=2)

    def test_rng_stream_centre_and_nonlocal_sources(self):
        real = FakeSpectrumDataset(self.table, (9, 9))
        shuffled = FakeShuffled(self.table, (9, 9))
        shuffled._init_nonlocal()
        centre = 40
        np.random.seed(11)
        real_batches = [real[i][0] for i in range(len(real))]
        state_after_real = np.random.get_state()[1].copy()
        np.random.seed(11)
        shuffled_batches = [shuffled[i][0] for i in range(len(shuffled))]
        # The global RNG advanced exactly as in the real run.
        np.testing.assert_array_equal(np.random.get_state()[1], state_after_real)
        for index, (a, b) in enumerate(zip(real_batches, shuffled_batches)):
            a_flat = np.swapaxes(a, 1, 3).reshape(81, -1)
            b_flat = np.swapaxes(b, 1, 3).reshape(81, -1)
            np.testing.assert_array_equal(a_flat[centre], b_flat[centre])
            x, y = self.table.x[index] - 1, self.table.y[index] - 1
            window = {int(s) for s in shuffled.index_images[0][0, max(y - 4, 0):y + 5,
                                                               max(x - 4, 0):x + 5].ravel() if s >= 0}
            for slot in range(81):
                if slot != centre:
                    self.assertNotIn(int(b_flat[slot, 0]), window | {index})

    def test_transform_is_applied_once_after_the_shuffle(self):
        calls = []

        def transform(batch):
            calls.append(batch.shape)
            return batch * 2

        shuffled = FakeShuffled(self.table, (9, 9), transform_data=transform)
        shuffled._init_nonlocal()
        plain = FakeShuffled(self.table, (9, 9))
        plain._init_nonlocal()
        np.random.seed(3)
        doubled = shuffled[5][0]
        np.random.seed(3)
        np.testing.assert_array_equal(doubled, plain[5][0] * 2)
        self.assertEqual(len(calls), 1)

    def test_a_drifted_index_rule_is_detected(self):
        shuffled = FakeShuffled(self.table, (9, 9))
        shuffled._init_nonlocal()
        shuffled.x_hws = 3            # re-derived indices no longer match the parent
        with self.assertRaises(Exception):
            shuffled[0]


class Captured(Exception):
    pass


class TrainingAndInferenceCallTests(unittest.TestCase):
    """The patch builder is called exactly as before unless the mode is shuffle_nonlocal."""

    @classmethod
    def setUpClass(cls):
        try:
            import torch  # noqa: F401
            import train as train_module
            import test as test_module
        except ImportError as error:
            raise unittest.SkipTest(f"S3PL training stack not importable: {error}")
        cls.train_module, cls.test_module = train_module, test_module

    def capture(self, module, call):
        calls = []

        def fake(*args, **kwargs):
            calls.append((args, kwargs))
            raise Captured()

        original = module.build_patch_dataset
        module.build_patch_dataset = fake
        try:
            with self.assertRaises(Captured):
                call()
        finally:
            module.build_patch_dataset = original
        return calls[0]

    def config(self, mode):
        root = Path(tempfile.mkdtemp())
        config = {"data_dir": str(root / "x.h5"), "artifact_root": str(root), "random_seed": 1,
                  "spectral_patch_size": 9, "normalization": "reference_spatial_max"}
        if mode is not None:
            config["input_context_mode"] = mode
        return config

    def test_training_calls(self):
        for mode in (None, "none", "tile_centre"):
            args, kwargs = self.capture(self.train_module,
                                        lambda: self.train_module.train(self.config(mode)))
            self.assertEqual((len(args), kwargs), (3, {}), mode)
        config = self.config("shuffle_nonlocal")
        args, kwargs = self.capture(self.train_module, lambda: self.train_module.train(config))
        self.assertEqual(kwargs, {"neighbour_shuffle_seed": 1701})
        self.assertEqual(config["neighbour_shuffle_seed"], 1701)
        self.assertIn("shuffled", config["reconstruction_target"])

    def test_unknown_mode_is_refused(self):
        with self.assertRaises(ValueError):
            self.train_module.train(self.config("shuffle_local"))


class M2aiaRealTests(unittest.TestCase):
    """Runs where m2aia and pyimzml are installed (the cluster's s3pl_env)."""

    @classmethod
    def setUpClass(cls):
        try:
            import m2aia  # noqa: F401
            from pyimzml.ImzMLWriter import ImzMLWriter  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("m2aia/pyimzml not installed")

    def test_real_m2aia_reproduces_and_shuffles(self):
        import m2aia as m2
        from pyimzml.ImzMLWriter import ImzMLWriter
        from utils.nonlocal_shuffle import nonlocal_spectrum_dataset

        table = irregular_table(seed=4)
        path = Path(tempfile.mkdtemp()) / "synthetic.imzML"
        with ImzMLWriter(str(path), mode="continuous") as writer:
            for spectrum, x, y in zip(table.spectra, table.x, table.y):
                writer.addSpectrum(table.mz_values.astype(np.float64), spectrum.astype(np.float64),
                                   (int(x), int(y), 1))
        real = m2.SpectrumDataset([m2.ImzMLReader(str(path))], shape=(9, 9), buffer_type="memory")
        shuffled = nonlocal_spectrum_dataset(m2.ImzMLReader(str(path)), (9, 9), None)
        np.random.seed(21)
        real_batches = [real[i][0] for i in range(len(real))]
        np.random.seed(21)
        shuffled_batches = [shuffled[i][0] for i in range(len(shuffled))]
        changed = 0
        for a, b in zip(real_batches, shuffled_batches):
            a_flat = np.swapaxes(a, 1, 3).reshape(81, -1)
            b_flat = np.swapaxes(b, 1, 3).reshape(81, -1)
            np.testing.assert_array_equal(a_flat[40], b_flat[40])
            changed += int(not np.array_equal(a_flat, b_flat))
        self.assertEqual(changed, len(real_batches))


if __name__ == "__main__":
    unittest.main()
