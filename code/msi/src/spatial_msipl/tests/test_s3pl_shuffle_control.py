"""Test N summariser and job scripts (protocol 18 Section 6.5). No S3PL run needed."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import summarise_s3pl_cac_shuffle_control as s  # noqa: E402


def record(differences):
    return s.seed_record(list(differences))


class DecisionRuleTests(unittest.TestCase):
    def test_depends_needs_seven_of_eight_and_mean_in_both_seeds(self):
        good = [0.05] * 7 + [0.0]
        self.assertEqual(s.decide({1: record(good), 2: record(good)}), s.DEPENDS)
        six = [0.05] * 6 + [0.0] * 2
        self.assertEqual(s.decide({1: record(good), 2: record(six)}), s.MIXED)
        low_mean = [0.021] * 7 + [-0.2]
        self.assertEqual(s.decide({1: record(good), 2: record(low_mean)}), s.MIXED)

    def test_not_specific_and_boundaries(self):
        small = [0.019] * 4 + [-0.019] * 4
        self.assertEqual(s.decide({1: record(small), 2: record(small)}), s.NOT_SPECIFIC)
        exact = [0.02] * 8
        self.assertEqual(s.decide({1: record(exact), 2: record(exact)}), s.DEPENDS)
        self.assertEqual(s.decide({1: record(exact), 2: record([0.02] * 7)}),
                         "incomplete; no verdict (seed 1: 8/8, seed 2: 7/8)")


class ShuffledRunTests(unittest.TestCase):
    def write(self, root, seed, section="40TopL", count=315, **overrides):
        name = f"{s.base_name(section)}_train_shuffle_nonlocal"
        seed_root = root / s.SEEDS[seed]["root"]
        (seed_root / "logs" / "s3pl").mkdir(parents=True, exist_ok=True)
        results = seed_root / "results" / "baselines" / "s3pl" / name
        results.mkdir(parents=True, exist_ok=True)
        config = {"input_context_mode": "shuffle_nonlocal", "neighbour_shuffle_seed": 1701,
                  "random_seed": 1, "n_epochs": 10, "spectral_patch_size": 9,
                  "number_peaks": count, "peaks_per_spectral_patch": 256, "batch_size": 16,
                  "normalization": "reference_spatial_max"}
        if seed == 2:
            config.update(initialization_seed=2, sample_order_seed=1)
        config.update(overrides)
        (seed_root / "logs" / "s3pl" / f"{name}.json").write_text(json.dumps(config))
        (results / "metrics.json").write_text(json.dumps({
            "number_picked_peaks": count, "training_input_context_mode": "shuffle_nonlocal",
            "source_training_name": name, "mSCF1": 0.3,
            "mixed_f1": {"0.3": 0.3, "0.4": 0.3, "0.5": 0.3, "0.6": 0.3}}))

    def test_predeclared_run_is_read_and_missing_is_none(self):
        root = Path(tempfile.mkdtemp())
        self.assertIsNone(s.shuffled_value("40TopL", 315, 1, root))
        for seed in (1, 2):
            self.write(root, seed)
            self.assertAlmostEqual(s.shuffled_value("40TopL", 315, seed, root), 0.3)

    def test_wrong_configuration_is_refused(self):
        cases = ({"neighbour_shuffle_seed": 7}, {"input_context_mode": "tile_centre"},
                 {"n_epochs": 100}, {"initialization_seed": 3}, {"number_peaks": 300},
                 {"normalization": "paper_tic"})
        for index, override in enumerate(cases):
            root = Path(tempfile.mkdtemp())
            self.write(root, 1 if "initialization_seed" not in override else 2, **override)
            seed = 1 if "initialization_seed" not in override else 2
            with self.assertRaises(SystemExit, msg=str(override)):
                s.shuffled_value("40TopL", 315, seed, root)


class LocalArtifactTests(unittest.TestCase):
    @unittest.skipUnless(s.CONTROLS.exists() and s.SEED2_REAL.exists(),
                         "local S3PL artifacts not present")
    def test_saved_real_column_reproduces_and_no_shuffled_run_gives_incomplete(self):
        rows, decision = s.build(shuffle_root=Path(tempfile.mkdtemp()))
        self.assertEqual(len(rows), 16)
        self.assertTrue(decision["verdict"].startswith("incomplete"))


class JobScriptTests(unittest.TestCase):
    def test_runner_and_submitter(self):
        runner = (ROOT / "slurm_jobs" / "run_s3pl_cac_shuffle_control.sh").read_text(encoding="utf-8")
        self.assertIn("--input-context-mode shuffle_nonlocal", runner)
        self.assertIn("seed_arguments=(--initialization_seed 2 --sample_order_seed 1)", runner)
        self.assertIn("seed1_released", runner)
        self.assertIn("seed2_init2_order1", runner)
        self.assertIn("reproducibility/s3pl_cac_shuffle_control", runner)
        self.assertIn("counts=(315 210 221 255 245 247 133 232)", runner)
        self.assertIn("refusing to overwrite", runner)
        self.assertIn("CUDA warm-up", runner)
        submit = (ROOT / "slurm_jobs" / "submit_s3pl_cac_shuffle_control.sh").read_text(
            encoding="utf-8")
        self.assertIn('--exclude="$exclude"', submit)
        self.assertNotIn("SBATCH_EXCLUDE=", submit)
        self.assertIn("concurrency=2", submit)


if __name__ == "__main__":
    unittest.main()
