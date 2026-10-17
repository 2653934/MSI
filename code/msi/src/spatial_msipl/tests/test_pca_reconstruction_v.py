"""Tests for the predeclared Test V PCA reconstruction addendum."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

try:
    import h5py
except ImportError:  # pragma: no cover - production and cluster test env have h5py
    h5py = None

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

if h5py is not None:
    import evaluate_pca_reconstruction_v as evaluator
    import summarise_pca_reconstruction_v as summariser
    from spatial_msipl.provenance import file_record


@unittest.skipIf(h5py is None, "h5py is not installed")
class Metrics(unittest.TestCase):
    def test_tiny_rank_one_reconstruction_has_hand_checked_error(self):
        # PCA-1 keeps the x axis. The two y-axis rows reconstruct to zero:
        # squared and absolute error sums are both 2 over 8 entries; per-pixel
        # cosine values are 1, 1, 0, 0.
        matrix = np.array([[2.0, 0.0], [-2.0, 0.0], [0.0, 1.0], [0.0, -1.0]],
                          dtype=np.float32)
        metrics, ratio = evaluator.pca_reconstruction(matrix, 1, metric_chunk_size=2)
        raw = metrics["primary_raw_inverse_transform"]
        self.assertAlmostEqual(raw["mean_squared_error"], 0.25, places=6)
        self.assertAlmostEqual(raw["mean_absolute_error"], 0.25, places=6)
        self.assertAlmostEqual(raw["cosine_similarity"], 0.5, places=6)
        self.assertAlmostEqual(ratio, 0.8, places=6)

    def test_secondary_matches_decoder_tic_contract_and_entry_weighting(self):
        target = np.array([[0.75, 0.25], [0.0, 1.0]], dtype=np.float32)
        raw = np.array([[3.0, 1.0], [-2.0, 4.0]], dtype=np.float32)
        normalized = evaluator.decoder_tic_normalize(np.maximum(raw, 0.0))
        expected_mse = float(np.square(target - normalized).mean())
        expected_mae = float(np.abs(target - normalized).mean())
        metrics = evaluator.reconstruction_metrics(target, raw, postprocess=True, chunk_size=1)
        self.assertAlmostEqual(metrics["mean_squared_error"], expected_mse, places=12)
        self.assertAlmostEqual(metrics["mean_absolute_error"], expected_mae, places=12)

    def test_explained_variance_mismatch_records_not_done_without_metrics(self):
        folder = Path(tempfile.mkdtemp())
        path = folder / "tiny.h5"
        rng = np.random.default_rng(2)
        with h5py.File(path, "w") as handle:
            handle["Data"] = rng.random((25, 20), dtype=np.float32)
            handle["mzArray"] = np.arange(20)
            handle["xLocation"] = np.arange(25)
            handle["yLocation"] = np.zeros(25)
        test_v = folder / "test_v.json"
        test_v.write_text(json.dumps({
            "status": "complete", "dataset": "tiny",
            "provenance": {"source_artifacts": {"input": file_record(path)}},
            "pca": {"pca5": {"explained_variance_ratio_sum": 0.5},
                    "pca20": {"explained_variance_ratio_sum": 1.0}},
        }), encoding="utf-8")
        fake_metrics = {name: 0.0 for name in evaluator.METRICS} if hasattr(
            evaluator, "METRICS") else {"mean_squared_error": 0.0,
                                         "mean_absolute_error": 0.0,
                                         "cosine_similarity": 0.0}
        values = ({"primary_raw_inverse_transform": fake_metrics,
                   "secondary_clip_zero_then_tic": fake_metrics}, 0.1)
        with mock.patch.object(evaluator, "pca_reconstruction", return_value=values):
            evaluator.main(["--input", str(path), "--test-v-summary", str(test_v),
                            "--output", str(folder / "out"), "--allow-outside-slurm"])
        saved = json.loads((folder / "out" / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], "not_done")
        self.assertNotIn("metrics", saved)


@unittest.skipIf(h5py is None, "scientific Python dependencies are not installed locally")
class Summary(unittest.TestCase):
    def test_counts_and_median_ratios_for_both_metric_conventions(self):
        rows = []
        for collection in ("GBM", "CAC"):
            for index in range(8):
                row = {"collection": collection, "section": f"{collection}{index}",
                       "status": "complete"}
                for convention in summariser.CONVENTIONS:
                    row[f"pca5_{convention}_mean_squared_error"] = 2.0 if index < 6 else 0.5
                row["vae_central_only_mean_squared_error"] = 1.0
                row["vae_uniform_mean_mean_squared_error"] = 2.0
                rows.append(row)
        summary = summariser.aggregate(rows, sections={"GBM": (), "CAC": ()})
        for collection in ("GBM", "CAC"):
            for convention in summariser.CONVENTIONS:
                central = summary[collection]["mse_comparisons"][convention]["central_only"]
                self.assertEqual(central["pca5_mse_exceeds_vae_count"], 6)
                self.assertEqual(central["median_pca5_to_vae_mse_ratio"], 2.0)
        self.assertTrue(summary["fixed_wording"].startswith("PCA-5 reconstructs worse"))

    def test_rcc_not_done_does_not_block_gbm_cac_wording(self):
        rows = []
        for collection in ("GBM", "CAC"):
            for index in range(8):
                row = {"collection": collection, "section": f"{collection}{index}",
                       "status": "complete"}
                for convention in summariser.CONVENTIONS:
                    row[f"pca5_{convention}_mean_squared_error"] = 0.5
                row["vae_central_only_mean_squared_error"] = 1.0
                row["vae_uniform_mean_mean_squared_error"] = 1.0
                rows.append(row)
        rows.append({"collection": "RCC", "section": "RCC0", "status": "not_done"})
        rows.append({"collection": "RCC", "section": "RCC1", "status": "complete"})
        summary = summariser.aggregate(rows, sections={"GBM": (), "CAC": (), "RCC": ()})
        self.assertEqual(summary["fixed_wording"],
                         "Reconstruction error does not separate PCA-5 from the VAE.")
        self.assertEqual(summary["RCC"]["sections_complete"], 1)
        self.assertEqual(summary["RCC"]["sections_expected"], 2)
        self.assertNotIn("mse_comparisons", summary["RCC"])
        self.assertIn("reported alone", summary["RCC"]["comparison"])
        self.assertTrue(any("Cosine" in note for note in summary["notes"]))

    def test_incomplete_gbm_gives_not_done_wording(self):
        rows = [{"collection": "GBM", "section": "GBM0", "status": "not_done"},
                {"collection": "CAC", "section": "CAC0", "status": "complete",
                 **{f"pca5_{c}_mean_squared_error": 2.0 for c in summariser.CONVENTIONS},
                 "vae_central_only_mean_squared_error": 1.0,
                 "vae_uniform_mean_mean_squared_error": 1.0}]
        summary = summariser.aggregate(rows, sections={"GBM": (), "CAC": ()})
        self.assertTrue(summary["fixed_wording"].startswith("not done"))

    def test_mixed_code_is_refused(self):
        root = Path(tempfile.mkdtemp())
        for section, code in (("RCC0", "a"), ("RCC1", "b")):
            folder = root / "RCC" / f"{section}_seed1"
            folder.mkdir(parents=True)
            (folder / "summary.json").write_text(json.dumps({
                "status": "not_done", "not_done_reason": "test",
                "provenance": {"version": 1, "protocol": "p", "parameters": {},
                               "code": code}}))
        sections = {"RCC": ("RCC0", "RCC1")}
        with self.assertRaisesRegex(ValueError, "different code"):
            summariser.collect(root, vae_roots={}, sections=sections)
        (root / "RCC" / "RCC1_seed1" / "summary.json").write_text(json.dumps({
            "status": "not_done", "not_done_reason": "test",
            "provenance": {"version": 1, "protocol": "p", "parameters": {}, "code": "a"}}))
        self.assertEqual(len(summariser.collect(root, vae_roots={}, sections=sections)), 2)


class JobScripts(unittest.TestCase):
    def test_batch_job_uses_test_v_inputs_and_new_root(self):
        runner = (ROOT / "slurm_jobs" / "run_pca_reconstruction_v.sh").read_text(
            encoding="utf-8")
        self.assertIn("#SBATCH --partition=batch", runner)
        self.assertIn("segmentation_control_V", runner)
        self.assertIn("pca_reconstruction_V", runner)
        self.assertNotIn("--allow-outside-slurm", runner)

    def test_cluster_compatibility_job_runs_this_module(self):
        test_job = (ROOT / "slurm_jobs" / "run_fair_scoring_tests.sh").read_text(
            encoding="utf-8")
        self.assertIn("spatial_msipl.tests.test_pca_reconstruction_v", test_job)


if __name__ == "__main__":
    unittest.main()
