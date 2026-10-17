"""Ranking-stage timing (supervisor chat 2026-10-17 09:48, item 2).

Each timed stage must produce exactly the ranking the fair-scoring evaluator
produces from the same section, so the timings are of the real computation.
Synthetic data only.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import numpy as np

try:
    import h5py
except ImportError:  # pragma: no cover - the cluster test job has h5py
    h5py = None

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

if h5py is not None:
    import evaluate_fair_scoring_baselines as evaluator
    import evaluate_spatial_msipl_attributed_peaks as attributed
    import summarise_ranking_stage_runtime as summariser
    import time_ranking_stages as timing
    from spatial_msipl.provenance import array_sha256
    from spatial_msipl.simple_baselines import (
        gmm_posterior_numpy, moore_edges, nan_to_lowest, one_hot_maps,
        posterior_pcc_rankings, rank_descending, supervised_oracle_ranking)

WIDTH, HEIGHT, BINS, CHUNK = 7, 6, 53, 16


def write_section(folder, pixels_first=True, seed=0):
    rng = np.random.default_rng(seed)
    x, y = np.meshgrid(np.arange(WIDTH), np.arange(HEIGHT))
    x, y = x.ravel(), y.ravel()
    labels = (x >= WIDTH // 2).astype(np.int64) + (y == 0)   # three classes
    data = rng.gamma(2.0, 1.0, size=(len(x), BINS))
    data[:, :5] += 4.0 * labels[:, None]
    data[3, :] = 0.0                                           # one zero-TIC pixel
    path = folder / "section.h5"
    with h5py.File(path, "w") as handle:
        handle["Data"] = data if pixels_first else data.T
        handle["mzArray"] = np.linspace(100.0, 200.0, BINS)
        handle["Class_Label"] = labels
        handle["xLocation"] = x
        handle["yLocation"] = y
    latent = np.column_stack([x + rng.normal(0, 0.1, len(x)), rng.normal(0, 1, len(x))])
    gmm = {"scaler_mean": latent.mean(axis=0), "scaler_scale": latent.std(axis=0),
           "mixture_weights": np.array([0.5, 0.5]),
           "component_means": np.array([[-1.0, 0.0], [1.0, 0.0]]),
           "precision_cholesky": np.stack([np.eye(2), np.eye(2)])}
    attribution = folder / "attribution"
    attribution.mkdir()
    np.save(attribution / "latent_mean.npy", latent)
    np.savez(attribution / "gmm_parameters.npz", **gmm)
    posterior = gmm_posterior_numpy(latent, **gmm)
    component = np.argmax(posterior, axis=1)
    np.savez(attribution / "coordinates_and_gmm.npz", x=x, y=y, component=component,
             assigned_posterior=posterior[np.arange(len(x)), component].astype(np.float32))
    (attribution / "summary.json").write_text(json.dumps(
        {"status": "valid", "attribution_version": 2, "runtime_seconds": 12.5}),
        encoding="utf-8")
    return path, attribution


def evaluator_rankings(path, attribution):
    """The fair-scoring evaluator's own computation, as in its main()."""
    mz, labels, x, y, pixels_first = attributed.read_h5_metadata(path)
    latent = np.load(attribution / "latent_mean.npy")
    posterior = gmm_posterior_numpy(latent, **dict(np.load(attribution / "gmm_parameters.npz")))
    component = np.load(attribution / "coordinates_and_gmm.npz")["component"]
    sources, targets = moore_edges(x, y)
    maps = {"soft": posterior, "hard": one_hot_maps(component, posterior.shape[1])}
    stats, pcc, _ = evaluator.tic_statistics(path, pixels_first, len(mz), CHUNK, maps,
                                             sources, targets)
    correlations = attributed.load_correlations(path, labels, len(mz), pixels_first, CHUNK)
    return {
        "posterior_abs_pcc_balanced":
            posterior_pcc_rankings(pcc["soft"], pcc["hard"])["posterior_abs_pcc_balanced"],
        "morans_i": rank_descending(nan_to_lowest(stats["morans_i"])),
        "mean_intensity": rank_descending(stats["mean_intensity"]),
        "oracle": supervised_oracle_ranking(correlations),
    }


def write_fair_summary(folder, path, rankings, tamper=None):
    record = {name: {"full_ranking_sha256": array_sha256(r)} for name, r in rankings.items()}
    if tamper:
        record[tamper]["full_ranking_sha256"] = "0" * 64
    summary = {"status": "complete", "provenance": {"input": {"path": str(path)}},
               "rankings": record}
    target = folder / "fair_summary.json"
    target.write_text(json.dumps(summary), encoding="utf-8")
    return target


def run_main(arguments):
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
        timing.main(arguments + ["--allow-outside-slurm"])
    return stdout.getvalue()


@unittest.skipIf(h5py is None, "h5py is not installed")
class StagesMatchTheEvaluator(unittest.TestCase):
    def test_every_stage_reproduces_the_evaluator_in_both_orientations(self):
        for pixels_first in (True, False):
            folder = Path(tempfile.mkdtemp())
            path, attribution = write_section(folder, pixels_first)
            expected = evaluator_rankings(path, attribution)
            mz, labels, x, y, raw, stored_pixels_first = timing.load_section(path)
            self.assertEqual(stored_pixels_first, pixels_first)
            tic_chunks = timing.tic_normalise(raw, pixels_first, CHUNK)
            gmm = dict(np.load(attribution / "gmm_parameters.npz"))
            outputs, seconds = timing.run_stages(raw, pixels_first, tic_chunks, labels, x, y,
                                                 np.load(attribution / "latent_mean.npy"),
                                                 gmm, CHUNK)
            self.assertEqual(set(seconds), set(timing.STAGES))
            self.assertTrue(all(value >= 0 for value in seconds.values()))
            for stage, name in timing.SAVED_NAME.items():
                np.testing.assert_array_equal(outputs[stage], expected[name], err_msg=stage)

    def test_values_are_bit_identical_to_the_evaluator_at_a_realistic_size(self):
        """Run 69985 failed on m/z-first files: a contiguous copy changed NumPy's
        summation order. Compare the values themselves, not just the rankings."""
        rng = np.random.default_rng(0)
        width, height, bins, chunk = 30, 20, 3000, 1024
        x, y = [a.ravel() for a in np.meshgrid(np.arange(1, width + 1), np.arange(1, height + 1))]
        data = rng.gamma(0.5, 1.0, (len(x), bins)).astype(np.float32)
        posterior = rng.dirichlet([1, 1], len(x))
        for pixels_first in (True, False):
            path = Path(tempfile.mkdtemp()) / "s.h5"
            with h5py.File(path, "w") as handle:
                handle["Data"] = data if pixels_first else np.ascontiguousarray(data.T)
                handle["mzArray"] = np.arange(bins, dtype=float)
                handle["Class_Label"] = (x > width // 2).astype(int)
                handle["xLocation"], handle["yLocation"] = x, y
            _, labels, xx, yy, raw, stored = timing.load_section(path)
            tic_chunks = timing.tic_normalise(raw, stored, chunk)
            sources, targets = moore_edges(xx, yy)
            stats, pcc, _ = evaluator.tic_statistics(path, stored, bins, chunk,
                                                     {"soft": posterior}, sources, targets)
            mine_pcc = np.zeros((bins, 2))
            mine_mean, mine_moran = np.zeros(bins), np.zeros(bins)
            for start, stop, values in tic_chunks:
                mine_pcc[start:stop] = timing.pearson_features_vs_maps(values, posterior)
                mine_mean[start:stop] = values.mean(axis=0)
                mine_moran[start:stop] = timing.morans_i_per_feature(values, sources, targets)
            np.testing.assert_array_equal(mine_pcc, pcc["soft"], err_msg=f"pcc {pixels_first}")
            np.testing.assert_array_equal(mine_mean, stats["mean_intensity"],
                                          err_msg=f"mean {pixels_first}")
            np.testing.assert_array_equal(mine_moran, stats["morans_i"],
                                          err_msg=f"moran {pixels_first}")
            correlations = attributed.load_correlations(path, labels, bins, stored, chunk)
            np.testing.assert_array_equal(timing.stage_oracle(raw, stored, labels, chunk),
                                          supervised_oracle_ranking(correlations))

    def test_the_oracle_stage_leaves_the_in_memory_spectra_unchanged(self):
        for pixels_first in (True, False):
            folder = Path(tempfile.mkdtemp())
            path, _ = write_section(folder, pixels_first)
            _, labels, _, _, raw, stored = timing.load_section(path)
            before = raw.copy()
            timing.stage_oracle(raw, stored, labels, CHUNK)
            np.testing.assert_array_equal(raw, before)

    def test_tic_normalisation_matches_the_evaluator_values(self):
        for pixels_first in (True, False):
            folder = Path(tempfile.mkdtemp())
            path, _ = write_section(folder, pixels_first)
            _, _, _, _, raw, stored = timing.load_section(path)
            tic_chunks = timing.tic_normalise(raw, stored, CHUNK)
            self.assertEqual(timing.n_bins_of(tic_chunks), BINS)
            matrix = np.concatenate([values for _, _, values in tic_chunks], axis=1)
            self.assertEqual(matrix.shape, (WIDTH * HEIGHT, BINS))
            self.assertTrue(np.all(matrix[3] == 0.0))
            np.testing.assert_allclose(np.delete(matrix.sum(axis=1), 3), 1.0, rtol=1e-12)


@unittest.skipIf(h5py is None, "h5py is not installed")
class MainOutput(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.path, self.attribution = write_section(self.folder)
        self.rankings = evaluator_rankings(self.path, self.attribution)

    def arguments(self, fair, output="out"):
        arguments = ["--input", str(self.path), "--attribution-dir", str(self.attribution),
                     "--output", str(self.folder / output), "--chunk-size", str(CHUNK)]
        return arguments + (["--fair-summary", str(fair)] if fair else [])

    def test_complete_summary_with_three_repeats_and_ig_label(self):
        fair = write_fair_summary(self.folder, self.path, self.rankings)
        run_main(self.arguments(fair))
        summary = json.loads((self.folder / "out" / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(summary["repeats"], 3)
        self.assertEqual(len(summary["stage_seconds_repeats"]), 3)
        for stage in timing.STAGES:
            values = sorted(r[stage] for r in summary["stage_seconds_repeats"])
            self.assertEqual(summary["stage_seconds_median"][stage], values[1])
        self.assertEqual(set(summary["reproduction"]["rankings"]), set(timing.SAVED_NAME.values()))
        self.assertEqual(summary["integrated_gradients"]["seconds"], 12.5)
        self.assertTrue(summary["integrated_gradients"]["label"].startswith(
            "IG incl. GMM + faithfulness"))
        self.assertIn("cpu_model", summary["environment"])
        self.assertEqual((summary["pixels"], summary["spectral_bins"]), (WIDTH * HEIGHT, BINS))

    def test_existing_output_is_never_overwritten(self):
        fair = write_fair_summary(self.folder, self.path, self.rankings)
        run_main(self.arguments(fair))
        with self.assertRaises(SystemExit) as raised:
            run_main(self.arguments(fair))
        self.assertEqual(raised.exception.code, 3)

    def test_a_ranking_that_does_not_reproduce_reports_nothing(self):
        for name in timing.SAVED_NAME.values():
            fair = write_fair_summary(self.folder, self.path, self.rankings, tamper=name)
            with self.assertRaises(SystemExit) as raised:
                run_main(self.arguments(fair, output=f"out_{name}"))
            self.assertEqual(raised.exception.code, 4, name)
            self.assertFalse((self.folder / f"out_{name}" / "summary.json").exists())

    def test_wrong_input_or_incomplete_fair_summary_is_refused(self):
        fair = write_fair_summary(self.folder, self.folder / "other.h5", self.rankings)
        with self.assertRaises(SystemExit):
            run_main(self.arguments(fair, output="a"))
        summary = json.loads(fair.read_text(encoding="utf-8"))
        summary["status"] = "running"
        summary["provenance"]["input"]["path"] = str(self.path)
        fair.write_text(json.dumps(summary), encoding="utf-8")
        with self.assertRaises(SystemExit):
            run_main(self.arguments(fair, output="b"))

    def test_without_a_fair_summary_the_ranking_check_is_labelled_unavailable(self):
        run_main(self.arguments(None))
        summary = json.loads((self.folder / "out" / "summary.json").read_text(encoding="utf-8"))
        self.assertTrue(summary["reproduction"]["rankings"].startswith("not available"))

    def test_refuses_outside_slurm_without_the_flag(self):
        # The cluster test job itself runs inside Slurm, so hide its job ID here.
        environment = {k: v for k, v in os.environ.items() if k != "SLURM_JOB_ID"}
        with mock.patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(SystemExit):
                timing.main(self.arguments(None, output="outside_slurm"))
        self.assertFalse((self.folder / "outside_slurm").exists())


@unittest.skipIf(h5py is None, "h5py is not installed")
class Summariser(unittest.TestCase):
    def write(self, root, section, cpu, check="identical (full-ranking SHA-256)"):
        folder = root / f"{section}_seed1" / "uniform_mean"
        folder.mkdir(parents=True)
        rankings = ({name: check for name in timing.SAVED_NAME.values()}
                    if check.startswith("identical") else check)
        summary = {"status": "complete", "dataset": section, "pixels": 10, "spectral_bins": 20,
                   "data_load_seconds": 1.0, "tic_normalisation_seconds": 0.5,
                   "stage_seconds_median": {s: 0.1 for s in timing.STAGES},
                   "posterior_abs_pcc_including_gmm_posterior_median": 0.2,
                   "integrated_gradients": {"seconds": 9.0, "label": timing.IG_LABEL,
                                            "attribution_status": "valid"},
                   "reproduction": {"rankings": rankings},
                   "environment": {"cpu_model": cpu, "node": "n1"}}
        (folder / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    def test_table_allows_one_cpu_per_collection_and_refuses_mixed_within_one(self):
        root = Path(tempfile.mkdtemp())
        self.write(root, "40TopL", "Xeon A")
        self.write(root, "RCC_UH0505_12", "Xeon B", check="not available (no seed-1 ...)")
        rows, cpus = summariser.collect(root, expected=("40TopL", "RCC_UH0505_12"))
        self.assertEqual(cpus, {"CAC": "Xeon A", "RCC": "Xeon B"})
        self.assertEqual([r["section"] for r in rows], ["40TopL", "RCC_UH0505_12"])
        self.assertEqual(rows[0]["collection"], "CAC")
        self.assertEqual(rows[1]["ranking_reproduction"], "not available (no seed-1 ...)")
        self.assertEqual(rows[0]["posterior_abs_pcc_seconds"], 0.1)
        self.assertEqual(rows[0]["ig_label"], timing.IG_LABEL)
        self.write(root, "160TopL", "Xeon C")
        with self.assertRaises(SystemExit):
            summariser.collect(root, expected=("40TopL", "160TopL"))

    def test_collection_specific_root_keeps_existing_summaries_untouched(self):
        root = Path(tempfile.mkdtemp())
        rcc_root = Path(tempfile.mkdtemp())
        self.write(root, "40TopL", "Xeon A")
        self.write(rcc_root, "RCC_MH0204_33", "Xeon B")
        rows, cpus = summariser.collect(
            root, expected=("RCC_MH0204_33", "40TopL"),
            collection_roots={"RCC": rcc_root})
        self.assertEqual([r["status"] for r in rows], ["complete", "complete"])
        self.assertEqual(cpus, {"CAC": "Xeon A", "RCC": "Xeon B"})
        self.assertIn(rcc_root.as_posix(), rows[0]["source"])

    def test_missing_section_is_listed_not_invented(self):
        root = Path(tempfile.mkdtemp())
        self.write(root, "40TopL", "Xeon A")
        rows, _ = summariser.collect(root, expected=("40TopL", "160TopL"))
        self.assertEqual(rows[1]["status"], "missing")
        self.assertIsNone(rows[1]["posterior_abs_pcc_seconds"])


class JobScript(unittest.TestCase):
    def test_job_uses_seed1_uniform_artifacts_and_the_test_r_order(self):
        script = (ROOT / "slurm_jobs" / "run_ranking_stage_timing.sh").read_text(encoding="utf-8")
        self.assertIn("test_r_sections.sh", script)
        self.assertIn("uniform_mean", script)
        self.assertIn("_seed1", script)
        self.assertIn("ranking_stage_runtime", script)
        self.assertNotIn("--allow-outside-slurm", script)
        self.assertIn("#SBATCH --exclusive", script)

    def test_rcc_submit_option_uses_sbatch_nodelist_and_a_new_root(self):
        script = (ROOT / "slurm_jobs" / "submit_rcc_ranking_stage_timing.sh").read_text(
            encoding="utf-8")
        self.assertIn('squeue -r -u zsuliman -h -t RUNNING -p bigbatch', script)
        self.assertIn('--partition=bigbatch --nodelist="$nodes" --array=0-7%2', script)
        self.assertIn("mscluster55,mscluster71,mscluster74,mscluster76,mscluster77", script)
        self.assertIn("ranking_stage_runtime_rcc_bigbatch", script)
        self.assertNotIn("SBATCH_NODELIST", script)

    def test_paths_for_each_collection(self):
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("bash not available")
        script = ('source "slurm_jobs/run_ranking_stage_timing.sh" '
                  '--paths-only; '
                  'for s in RCC_UH0505_12 40TopL GBM22_2; do ranking_timing_paths "$s"; done')
        result = subprocess.run([bash, "-c", script], capture_output=True, text=True,
                                env=dict(os.environ, HOME="/h"), cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        lines = result.stdout.split()
        self.assertEqual(lines, [
            "/datasets/zsuliman/msi_data/rcc_cardinal/RCC_UH0505_12.h5",
            "/h/msi/results/experiments/rcc_spatial_msipl/RCC_UH0505_12_seed1/uniform_mean/attribution",
            "/h/msi/results/diagnostics/fair_scoring_baselines/rcc/bin_level_only/RCC_UH0505_12_seed1/uniform_mean/summary.json",
            "/datasets/zsuliman/msi_data/cac_msipl/40TopL.h5",
            "/h/msi/results/experiments/spatial_msipl_cac_gmm_integrated_gradients/40TopL_seed1/uniform_mean",
            "/h/msi/results/diagnostics/fair_scoring_baselines/bin_level_only/40TopL_seed1/uniform_mean/summary.json",
            "/datasets/zsuliman/msi_data/gbm_massnet/GBM22_2.h5",
            "/h/msi/results/experiments/spatial_msipl_gmm_integrated_gradients/GBM22_2_seed1/uniform_mean",
            "/h/msi/results/diagnostics/fair_scoring_baselines/bin_level_only/GBM22_2_seed1/uniform_mean/summary.json",
        ])


if __name__ == "__main__":
    unittest.main()
