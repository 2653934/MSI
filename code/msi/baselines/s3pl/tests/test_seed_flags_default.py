"""Investigation 21 Part C (protocol 18 Section 6.7): the opt-in seed flags of 3624b56b
leave the released training path unchanged.

With neither ``initialization_seed`` nor ``sample_order_seed`` set, the current
``train.py`` must behave exactly like the frozen copy in ``fixtures/pre_seed_flags``
(the current file with only the 3624b56b hunks reversed):

- text level (no torch): the two files differ only by the 3624b56b lines;
- run level (torch): a tiny CPU training on a synthetic HDF5 section gives identical
  loss history, weights, saved config and picked peaks, and writes no vote diagnostics.
  A controlled run (init 1, order 1) is also made, to show the comparison can fail.
"""

import difflib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

S3PL_ROOT = Path(__file__).resolve().parents[1]
if str(S3PL_ROOT) not in sys.path:
    sys.path.insert(0, str(S3PL_ROOT))
FROZEN = Path(__file__).resolve().parent / "fixtures" / "pre_seed_flags" / "train.py"

# Lines 3624b56b replaced in train.py (frozen -> current).
REPLACED = {
    "np.random.seed(random_seed)": "np.random.seed(random_seed if sample_order_seed is None else sample_order_seed)",
    "train_sampler = SubsetRandomSampler(train_indices)":
        "train_sampler = SubsetRandomSampler(train_indices, generator=sampler_generator)",
}
# Lines 3624b56b added to train.py (stripped).
ADDED = {
    'initialization_seed = config.get("initialization_seed")',
    'sample_order_seed = config.get("sample_order_seed")',
    "if (initialization_seed is None) != (sample_order_seed is None):",
    'raise ValueError("Set both initialization_seed and sample_order_seed for a controlled seed experiment")',
    "if initialization_seed is not None and (",
    "not isinstance(initialization_seed, int)",
    "or not isinstance(sample_order_seed, int)",
    "or min(initialization_seed, sample_order_seed) < 0",
    "):",
    'raise ValueError("Controlled seeds must be nonnegative integers")',
    "# The released-code path keeps the global RNG behaviour exactly as before.",
    "# In a controlled experiment, the sampler has its own stream so changing",
    "# model initialisation cannot silently change the mini-batch order.",
    "sampler_generator = None",
    "if sample_order_seed is not None:",
    "sampler_generator = torch.Generator().manual_seed(sample_order_seed)",
    "",
    "if initialization_seed is not None:",
    "torch.manual_seed(initialization_seed)",
    "torch.cuda.manual_seed(initialization_seed)",
    "print('controlled initialization seed: ' + str(initialization_seed))",
    "print('controlled sample-order seed: ' + str(sample_order_seed))",
}


class TextDiffTests(unittest.TestCase):
    def test_current_differs_from_frozen_only_by_the_seed_flag_lines(self):
        old = FROZEN.read_text().splitlines()
        new = (S3PL_ROOT / "train.py").read_text().splitlines()
        replaced, added = {}, []
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
            if tag == "equal":
                continue
            self.assertIn(tag, ("insert", "replace"), f"lines removed from frozen copy: {old[i1:i2]}")
            removed = [line.strip() for line in old[i1:i2]]
            inserted = [line.strip() for line in new[j1:j2]]
            for line in removed:
                self.assertIn(line, REPLACED, f"unexpected change to frozen line {line!r}")
                self.assertIn(REPLACED[line], inserted)
                replaced[line] = REPLACED[line]
                inserted.remove(REPLACED[line])
            added += inserted
        self.assertEqual(replaced, REPLACED)
        self.assertTrue(set(added) <= ADDED, set(added) - ADDED)
        # 22 nonblank added lines; "if initialization_seed is not None:" occurs twice.
        self.assertEqual(len([line for line in added if line]), 22)

    def test_default_branches_are_guarded(self):
        # Every new statement that changes RNG use runs only when a flag is set.
        new = (S3PL_ROOT / "train.py").read_text()
        self.assertIn("    sampler_generator = None\n    if sample_order_seed is not None:\n"
                      "        sampler_generator = torch.Generator().manual_seed(sample_order_seed)", new)
        self.assertIn("    if initialization_seed is not None:\n        torch.manual_seed(initialization_seed)", new)


def write_section(path, seed=0, width=10, height=8, bins=24):
    import h5py
    rng = np.random.default_rng(seed)
    xs, ys = np.meshgrid(np.arange(1, width + 1), np.arange(1, height + 1))
    spectra = rng.gamma(2.0, 1.0, (xs.size, bins)).astype(np.float32)
    with h5py.File(path, "w") as handle:
        handle["Data"] = spectra.T
        handle["mzArray"] = np.linspace(100, 123, bins).astype(np.float32)
        handle["xLocation"] = xs.ravel().astype(np.int32)
        handle["yLocation"] = ys.ravel().astype(np.int32)


class DefaultRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import h5py  # noqa: F401
            import torch
            import train as current
        except ImportError as error:
            raise unittest.SkipTest(f"S3PL training stack not importable: {error}")
        # The identity gate is CPU-only (chat 2026-10-21 09:36); a visible GPU fails the class.
        assert not torch.cuda.is_available(), "run with CUDA_VISIBLE_DEVICES=\"\""
        spec = importlib.util.spec_from_file_location("pre_seed_flags_train", FROZEN)
        frozen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(frozen)
        cls.torch, cls.current, cls.frozen = torch, current, frozen
        cls.tmp = Path(tempfile.mkdtemp())
        cls.data = cls.tmp / "toy.h5"
        write_section(cls.data)
        cls.runs = {
            "frozen": cls.train_once(frozen, "frozen"),
            "default": cls.train_once(current, "default"),
            "controlled": cls.train_once(current, "controlled", initialization_seed=1, sample_order_seed=1),
        }

    @classmethod
    def train_once(cls, module, name, **seeds):
        root = cls.tmp / name
        config = {"data_dir": str(cls.data), "artifact_root": str(root), "number_classes": 2,
                  "evaluate_peak_picking": False, "number_peaks": 6, "peaks_per_spectral_patch": 3,
                  "spectral_patch_size": 3, "kernel_depth_d1": 5, "kernel_depth_d2": 1,
                  "n_epochs": 2, "batch_size": 8, "learning_rate": 1e-2, "dropout": 0,
                  "random_seed": 1, "normalization": "reference_spatial_max", **seeds}
        module.train(config)
        name_ = config["training_name"]
        log = json.loads((root / "logs" / "s3pl" / f"{name_}.json").read_text())
        log.pop("artifact_root")
        results = root / "results" / "baselines" / "s3pl" / name_
        (peaks,) = results.glob("picked_peaks_*.csv")
        weights = cls.torch.load(root / "checkpoints" / "baselines" / "s3pl" / f"{name_}.pt")
        return {"log": log, "peaks": peaks.read_bytes(), "weights": weights,
                "votes": (results / "peak_vote_diagnostics.csv").exists()}

    def same_weights(self, a, b):
        return a.keys() == b.keys() and all(self.torch.equal(a[k], b[k]) for k in a)

    def test_default_path_is_bit_identical_to_the_frozen_copy(self):
        old, new = self.runs["frozen"], self.runs["default"]
        self.assertEqual(new["log"]["train_history"], old["log"]["train_history"])
        self.assertEqual(new["log"], old["log"])
        self.assertTrue(self.same_weights(new["weights"], old["weights"]))
        self.assertEqual(new["peaks"], old["peaks"])
        self.assertFalse(new["votes"])
        self.assertNotIn("initialization_seed", new["log"])

    def test_controlled_run_is_detected_as_different(self):
        old, controlled = self.runs["frozen"], self.runs["controlled"]
        self.assertTrue(controlled["votes"])
        self.assertFalse(controlled["log"]["train_history"] == old["log"]["train_history"]
                         and self.same_weights(controlled["weights"], old["weights"]))


if __name__ == "__main__":
    unittest.main()
