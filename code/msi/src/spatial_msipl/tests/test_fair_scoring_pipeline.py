"""End-to-end synthetic test of the partition audit and fair-scoring scripts.

Builds a tiny synthetic section, produces a 'saved' evaluation with the
existing production evaluator, then checks that the new script reproduces it,
refuses unapproved or altered partitions, and writes peak-level results only
for approved ones. Requires h5py, sklearn and matplotlib (cluster env).
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

try:
    import h5py
    import sklearn  # noqa: F401
    import matplotlib  # noqa: F401
    DEPENDENCIES = True
except ImportError:  # pragma: no cover - data_tools_env without these
    DEPENDENCIES = False

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"


def run(script, *arguments, check=True):
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src"), str(SCRIPTS), environment.get("PYTHONPATH", "")])
    environment["MPLBACKEND"] = "Agg"
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, arguments)],
        env=environment, capture_output=True, text=True, check=check)


@unittest.skipUnless(DEPENDENCIES, "h5py/sklearn/matplotlib not installed")
class FairScoringPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sklearn.mixture import GaussianMixture
        from sklearn.preprocessing import StandardScaler

        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        rng = np.random.default_rng(0)
        xs, ys = np.meshgrid(np.arange(1, 13), np.arange(1, 11))
        x, y = xs.reshape(-1), ys.reshape(-1)
        labels = (x > 6).astype(np.int64)
        n_bins = 240
        mz = 300.0 * (1 + 15e-6) ** np.arange(n_bins)
        mz[120:] += 0.5  # a hard gap
        peak_centres = np.arange(5, n_bins, 12)
        profile = np.zeros(n_bins)
        for centre in peak_centres:
            profile += np.exp(-0.5 * ((np.arange(n_bins) - centre) / 1.5) ** 2)
        data = rng.gamma(2.0, 1.0, (len(x), n_bins)) * 0.05 + profile
        marker = peak_centres[::2]
        data[:, marker] *= (1 + 2.0 * labels)[:, None]
        cls.input = root / "SYN1.h5"
        with h5py.File(cls.input, "w") as handle:
            handle["Data"] = data.astype(np.float32)
            handle["mzArray"] = mz
            handle["Class_Label"] = labels + 1
            handle["xLocation"] = x
            handle["yLocation"] = y

        latent = np.column_stack((labels + rng.normal(0, 0.2, len(x)),
                                  rng.normal(size=(len(x), 4))))
        scaler = StandardScaler().fit(latent)
        gmm = GaussianMixture(2, covariance_type="full", random_state=1).fit(
            scaler.transform(latent))
        posterior = gmm.predict_proba(scaler.transform(latent))
        component = np.argmax(posterior, axis=1)
        cls.attribution = root / "attribution"
        cls.attribution.mkdir()
        np.save(cls.attribution / "latent_mean.npy", latent.astype(np.float32))
        np.savez(cls.attribution / "gmm_parameters.npz",
                 scaler_mean=scaler.mean_, scaler_scale=scaler.scale_,
                 mixture_weights=gmm.weights_.astype(np.float32),
                 component_means=gmm.means_.astype(np.float32),
                 covariances=gmm.covariances_.astype(np.float32),
                 precision_cholesky=gmm.precisions_cholesky_.astype(np.float32))
        np.savez(cls.attribution / "coordinates_and_gmm.npz", x=x, y=y,
                 component=component,
                 assigned_posterior=posterior[np.arange(len(x)), component].astype(np.float32))
        (cls.attribution / "summary.json").write_text(json.dumps({"status": "valid"}))
        ig = np.abs(rng.normal(size=n_bins)) * 0.1
        ig[marker] += 1.0
        ig[marker + 1] += 0.8  # shoulder duplicates
        np.savez(cls.attribution / "attributions.npz", mz=mz.astype(np.float32),
                 first_layer_combined_l2=rng.random(n_bins).astype(np.float32),
                 component_0_combined_absolute_mean=ig.astype(np.float32),
                 component_1_combined_absolute_mean=(ig * rng.uniform(0.8, 1.2, n_bins)
                                                     ).astype(np.float32))

        sys.path[:0] = [str(ROOT / "src"), str(SCRIPTS)]
        from evaluate_spatial_msipl_attributed_peaks import load_correlations, score_indices
        cls.k_bin = 20
        legacy = peak_centres[:cls.k_bin]
        correlations = load_correlations(cls.input, labels + 1, n_bins, True, 64)
        legacy_score = score_indices(legacy, correlations, n_bins)
        cls.legacy_peaks = root / "learned_peaks.csv"
        np.savetxt(cls.legacy_peaks, mz[legacy], delimiter=",", header="mz_peak", comments="")
        cls.legacy_metrics = root / "peak_metrics.json"
        cls.legacy_metrics.write_text(json.dumps({
            "unique_nearest_bins": cls.k_bin, "mSCF1": legacy_score["mSCF1"],
            "mixed_f1": legacy_score["mixed_f1"],
            "threshold_results": legacy_score["threshold_results"]}))
        cls.saved = root / "saved_evaluation"
        run("evaluate_spatial_msipl_attributed_peaks.py", "--input", cls.input,
            "--attribution-dir", cls.attribution, "--legacy-peaks", cls.legacy_peaks,
            "--legacy-metrics", cls.legacy_metrics, "--output", cls.saved,
            "--matched-count", cls.k_bin, "--chunk-size", 64, "--ion-images", 2,
            "--consolidated-candidates", 5)
        cls.partitions = root / "partitions"
        run("audit_peak_partitions.py", "--input", cls.input, "--output", cls.partitions,
            "--chunk-size", 64, "--allow-outside-slurm")
        cls.audit = json.loads((cls.partitions / "summary.json").read_text())
        cls.root = root

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def common(self, output):
        return ["--input", self.input, "--attribution-dir", self.attribution,
                "--saved-evaluation-dir", self.saved, "--legacy-peaks", self.legacy_peaks,
                "--legacy-metrics", self.legacy_metrics, "--output", output,
                "--random-draws", 5, "--chunk-size", 64, "--allow-outside-slurm"]

    def approval(self, name, sha=None):
        path = self.root / name
        path.write_text(json.dumps({"partitions": {"P1": {
            "parameters": self.audit["partitions"]["P1"]["parameters"],
            "sections": {"SYN1": sha or self.audit["partitions"]["P1"]["structure"]["sha256"]},
        }}}))
        return path

    def test_audit_reads_no_labels_and_reports_both_partitions(self):
        self.assertFalse(self.audit["labels_or_scores_read"])
        self.assertEqual(set(self.audit["partitions"]), {"P1", "P3"})
        for record in self.audit["partitions"].values():
            self.assertIn("passed", record["sanity"])
            self.assertEqual(len(record["structure"]["sha256"]), 64)

    def test_without_approval_reproduces_saved_scores_and_skips_peak_level(self):
        output = self.root / "no_approval"
        run("evaluate_fair_scoring_baselines.py", *self.common(output))
        summary = json.loads((output / "summary.json").read_text())
        saved = json.loads((self.saved / "summary.json").read_text())
        self.assertAlmostEqual(
            summary["bin_level"]["integrated_gradients"]["1.0"]["mSCF1"],
            saved["matched_peak_evaluation"]["methods"]["integrated_gradients"]["mSCF1"],
            places=12)
        self.assertEqual(summary["peak_level"], {})
        self.assertIn("not requested", summary["peak_level_status"])
        self.assertAlmostEqual(summary["provenance_checks"]["legacy_rescore_minus_saved"], 0.0)
        for name in ("posterior_abs_pcc_balanced", "morans_i", "oracle", "random"):
            self.assertIn(name, summary["bin_level"])
        self.assertIn("not deployable", summary["oracle_label"])

    def test_approved_partition_adds_reconstructible_peak_level_results(self):
        approval = self.approval("partition_approval.json")
        output = self.root / "approved"
        run("evaluate_fair_scoring_baselines.py", *self.common(output),
            "--partition-dir", self.partitions, "--partition-approval", approval)
        summary = json.loads((output / "summary.json").read_text())
        record = summary["peak_level"]["P1"]
        self.assertGreater(record["K_peak"], 0)
        ig = record["methods"]["integrated_gradients"]
        self.assertEqual(ig["matched_K_peak"]["selected_groups"], record["K_peak"])
        self.assertLessEqual(ig["collapse_K_bin"]["distinct_groups"], self.k_bin)
        self.assertIn("not a matched", record["methods"]["legacy_msipl"]["matched_K_peak"])
        self.assertEqual(summary["provenance"]["partition_approval"]["sha256"],
                         __import__("hashlib").sha256(approval.read_bytes()).hexdigest())
        self.assertEqual(summary["provenance"]["approved_partition_hashes"]["P1"],
                         self.audit["partitions"]["P1"]["structure"]["sha256"])

        # Reconstruct the IG peak-level score from saved selections and partition arrays.
        selections = np.load(output / "peak_level_selections.npz")
        partitions = np.load(self.partitions / "partitions.npz")
        matched = selections["P1__integrated_gradients__matched_groups"]
        np.testing.assert_array_equal(
            selections["P1__integrated_gradients__matched_apex_bins"],
            partitions["P1_apex"][matched])
        prefix = np.load(output / "rankings_prefix.npz")["integrated_gradients"]
        consumed = ig["matched_K_peak"]["bins_consumed"]
        self.assertGreaterEqual(len(prefix), consumed)
        groups = partitions["P1_group_of_bin"]
        rebuilt = list(dict.fromkeys(groups[prefix[:consumed]].tolist()))
        np.testing.assert_array_equal(rebuilt, matched)
        reference = selections["P1__reference_groups_0.4"]
        self.assertEqual(len(reference), record["K_peak"])

    def test_tampered_partition_hash_is_refused_before_scoring(self):
        approval = self.approval("bad_approval.json", sha="0" * 64)
        output = self.root / "bad"
        result = run("evaluate_fair_scoring_baselines.py", *self.common(output),
                     "--partition-dir", self.partitions, "--partition-approval", approval,
                     check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("hash differs", result.stderr)
        self.assertFalse((output / "summary.json").exists())

    def test_restart_reuses_only_identical_provenance(self):
        output = self.root / "restart"
        run("evaluate_fair_scoring_baselines.py", *self.common(output))
        again = run("evaluate_fair_scoring_baselines.py", *self.common(output))
        self.assertIn("skipped", again.stdout)
        # Different parameters: refuse, never reuse or overwrite.
        args = self.common(output)
        args[args.index("--random-draws") + 1] = 6
        stale = run("evaluate_fair_scoring_baselines.py", *args, check=False)
        self.assertEqual(stale.returncode, 3)
        self.assertIn("STALE", stale.stderr)
        # A bare "complete" summary from older code is not reusable.
        bare = self.root / "bare"
        bare.mkdir()
        (bare / "summary.json").write_text(json.dumps({"status": "complete"}))
        result = run("evaluate_fair_scoring_baselines.py", *self.common(bare), check=False)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads((bare / "summary.json").read_text()), {"status": "complete"})

    def test_legacy_rescore_mismatch_stops(self):
        metrics = json.loads(self.legacy_metrics.read_text())
        metrics["threshold_results"]["0.4"]["mixed_classes"]["true_positive"] += 1
        tampered = self.root / "tampered_legacy.json"
        tampered.write_text(json.dumps(metrics))
        args = self.common(self.root / "legacy_bad")
        args[args.index("--legacy-metrics") + 1] = tampered
        result = run("evaluate_fair_scoring_baselines.py", *args, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("legacy rescore differs", result.stderr)

    def test_refuses_to_run_outside_slurm_without_test_flag(self):
        args = [a for a in self.common(self.root / "guard") if a != "--allow-outside-slurm"]
        environment_job = os.environ.pop("SLURM_JOB_ID", None)
        try:
            result = run("evaluate_fair_scoring_baselines.py", *args, check=False)
            audit = run("audit_peak_partitions.py", "--input", self.input,
                        "--output", self.root / "guard_audit", check=False)
        finally:
            if environment_job is not None:
                os.environ["SLURM_JOB_ID"] = environment_job
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing", result.stderr)
        self.assertIn("Refusing", audit.stderr)

    def test_summariser_writes_decision_table(self):
        output = self.root / "fair" / "SYN1_seed1" / "uniform_mean"
        run("evaluate_fair_scoring_baselines.py", *self.common(output))
        run("summarise_fair_scoring_baselines.py", "--root", self.root / "fair",
            "--output", self.root / "fair_summary")
        decisions = json.loads((self.root / "fair_summary" / "decisions.json").read_text())
        record = decisions["CAC/uniform_mean"]
        self.assertEqual(record["ig_minus_posterior_bin"]["sections"], 1)
        # One section can never produce a collection verdict.
        self.assertTrue(record["ig_vs_posterior_verdict"].startswith("incomplete collection"))
        self.assertIn("not a matched", record["legacy_note"])


if __name__ == "__main__":
    unittest.main()
