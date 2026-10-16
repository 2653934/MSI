"""S3PL-on-RCC adapter gate (supervisor chat 2026-10-16 22:07, overnight item 3).

Stages a synthetic three-class RCC export as S3PL expects it and checks that
check_s3pl_rcc_labels.py passes when S3PL's own label creation reproduces our
|R@0.5|, fails with exit 4 when it does not, and never overwrites a differing
staged file. No S3PL code is changed, so GBM/CAC loading is untouched.
Requires h5py, sklearn and matplotlib (cluster env).
"""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from spatial_msipl.tests.test_rcc_pipeline import DEPENDENCIES, ROOT, build_section, run

RUN = "MH0204_33"  # a real num_GT_peaks key, so data_configs resolves it


@unittest.skipUnless(DEPENDENCIES, "h5py/sklearn/matplotlib not installed")
class S3plRccAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.tmp.name)
        cls.source = root / "rcc_cardinal"
        cls.source.mkdir()
        h5, _, labels, _, _ = build_section(cls.source, f"RCC_{RUN}", 3, seed=7)
        import h5py
        with h5py.File(h5, "r") as handle:
            x = np.asarray(handle["xLocation"]).reshape(-1)
            y = np.asarray(handle["yLocation"]).reshape(-1)
        mask = np.full((int(y.max()), int(x.max())), -1, dtype=np.int64)
        mask[y - 1, x - 1] = labels
        np.save(cls.source / f"RCC_{RUN}_mask.npy", mask)
        cls.budget_root = root / "budgets"
        cls.budget = cls.budget_root / f"RCC_{RUN}_seed1" / "released_target_budget.json"
        run("compute_reference_budget.py", "--input", h5, "--output", cls.budget,
            "--chunk-size", 64, "--released-target-config",
            ROOT / "baselines" / "s3pl" / "data_configs.py",
            "--released-target-key", RUN, "--allow-outside-slurm")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def gate(self, staging, output, budget_root=None, check=True):
        return run("check_s3pl_rcc_labels.py", "--source-dir", self.source,
                   "--staging-dir", staging, "--budget-root", budget_root or self.budget_root,
                   "--runs", RUN, "--output", output, "--stage", "--allow-outside-slurm",
                   check=check)

    def test_gate_passes_when_s3pl_labels_reproduce_our_reference_set(self):
        staging = self.root / "stage_ok"
        self.gate(staging, self.root / "gate_ok.json")
        summary = json.loads((self.root / "gate_ok.json").read_text())
        record = summary["runs"][RUN]
        self.assertEqual(summary["status"], "passed")
        self.assertTrue(record["equal_to_ours"])
        self.assertEqual(record["s3pl_R_at_0.5"],
                         json.loads(self.budget.read_text())["reference_set_sizes_all_classes"]["0.5"])
        self.assertTrue((staging / f"{RUN}.h5").exists())
        self.assertTrue((staging / "labels" / f"{RUN}_class2_ranking.npy").exists())
        self.assertEqual(record["staged"][f"{RUN}.h5"]["sha256"],
                         __import__("hashlib").sha256(
                             (self.source / f"RCC_{RUN}.h5").read_bytes()).hexdigest())
        # Staging again with identical files is allowed.
        self.gate(staging, self.root / "gate_ok_again.json")

    def test_gate_fails_with_exit_4_when_reference_sizes_differ(self):
        budget = json.loads(self.budget.read_text())
        budget["released_target"]["our_R_at_0.5"] += 1
        other = self.root / "budgets_wrong" / f"RCC_{RUN}_seed1"
        other.mkdir(parents=True)
        (other / "released_target_budget.json").write_text(json.dumps(budget))
        result = self.gate(self.root / "stage_bad", self.root / "gate_bad.json",
                           budget_root=self.root / "budgets_wrong", check=False)
        self.assertEqual(result.returncode, 4)
        self.assertEqual(json.loads((self.root / "gate_bad.json").read_text())["status"], "failed")

    def test_a_differing_staged_file_is_never_overwritten(self):
        staging = self.root / "stage_conflict"
        staging.mkdir()
        (staging / f"{RUN}.h5").write_bytes(b"not the export")
        result = self.gate(staging, self.root / "gate_conflict.json", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("move it aside", result.stderr)
        self.assertEqual((staging / f"{RUN}.h5").read_bytes(), b"not the export")


if __name__ == "__main__":
    unittest.main()
