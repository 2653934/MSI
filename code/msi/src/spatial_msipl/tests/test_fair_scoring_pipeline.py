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

    def approval(self, name, sha=None, status="approved"):
        path = self.root / name
        path.write_text(json.dumps({"status": status, "partitions": {"P1": {
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

    def test_draft_partition_approval_is_refused_before_scoring(self):
        approval = self.approval("draft_approval.json", status="draft")
        output = self.root / "draft"
        result = run("evaluate_fair_scoring_baselines.py", *self.common(output),
                     "--partition-dir", self.partitions, "--partition-approval", approval,
                     check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("status must be 'approved'", result.stderr)
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

    # --- Gate (d) pixel-count evaluator on the same synthetic section. ---
    def gate_d_ranking(self, arrays):
        from spatial_msipl.simple_baselines import (
            balanced_ranking_from_component_scores, production_ig_scores)
        return balanced_ranking_from_component_scores(production_ig_scores(arrays))

    def swapped_n12(self, same_set):
        """Swap two component-0 IG scores so the K_bin set stays (or does not stay) the same."""
        production = dict(np.load(self.attribution / "attributions.npz"))
        key = "component_0_combined_absolute_mean"
        reference = self.gate_d_ranking(production)[:self.k_bin]
        order = np.argsort(-production[key], kind="stable")
        candidates = ([(order[i], order[i + 1]) for i in range(self.k_bin - 1)] if same_set
                      else [(order[0], b) for b in order[self.k_bin * 3:]])
        for a, b in candidates:
            arrays = dict(production)
            arrays[key] = production[key].copy()
            arrays[key][[a, b]] = arrays[key][[b, a]]
            prefix = self.gate_d_ranking(arrays)[:self.k_bin]
            if (set(prefix.tolist()) == set(reference.tolist())) == same_set and \
                    not np.array_equal(prefix, reference):
                return arrays
        self.fail("no swap gives the required precondition")

    def gate_d_runs(self, name, n12_arrays=None, n48_component=None):
        """Fake n=12/48/192 IG runs: n=12 copies production unless n12_arrays is given."""
        import shutil
        fair = self.root / f"{name}_fair"
        if not (fair / "summary.json").exists():
            run("evaluate_fair_scoring_baselines.py", *self.common(fair))
        run_root = self.root / name / "uniform_mean"
        production = dict(np.load(self.attribution / "attributions.npz"))
        rng = np.random.default_rng(5)
        for n in (12, 48, 192):
            directory = run_root / f"n{n}"
            directory.mkdir(parents=True)
            shutil.copy(self.attribution / "coordinates_and_gmm.npz", directory)
            arrays = dict(production)
            key = "component_0_combined_absolute_mean"
            if n == 12:
                arrays = n12_arrays if n12_arrays is not None else arrays
            else:
                arrays[key] = arrays[key] * rng.uniform(0.5, 1.5, len(arrays[key])
                                                        ).astype(np.float32)
            np.savez(directory / "attributions.npz", **arrays)
            if n == 48 and n48_component is not None:
                gmm = dict(np.load(directory / "coordinates_and_gmm.npz"))
                gmm["component"] = n48_component
                np.savez(directory / "coordinates_and_gmm.npz", **gmm)
            samples = {str(c): {"requested_attribution": n, "actual_attribution": n,
                                "capped": False} for c in (0, 1)}
            (directory / "summary.json").write_text(json.dumps({
                "attribution_version": 2, "status": "valid", "runtime_seconds": 1.0,
                "variant": "uniform_mean", "dataset": str(self.input),
                "model_state_sha256": "synthetic", "model_configuration": {},
                "input_specification": {}, "pixels": 24, "spectral_bins": 48,
                "gmm": {"components": 2, "covariance_type": "full", "n_init": 20,
                        "seed": 1, "component_counts": {"0": 60, "1": 60},
                        # GPU diagnostic: differs per run, must not block scoring.
                        "differentiable_posterior_max_absolute_difference": 1e-7 * n},
                "integrated_gradients": {
                    "baseline": "synthetic", "target": "synthetic", "steps": 64,
                    "integration": "trapezoidal", "attribution_pixels_per_component": 12,
                    "central_context_combination": "synthetic", "sampling_seed": 1,
                    "selection_seed": 701, "nested_attribution_samples": samples},
                "gmm_label_alignment": {
                    "enabled": True, "permutation": {"0": 0, "1": 1}, "identity": True,
                    "max_posterior_diff": 0.0,
                    "production_reference": {"sha256": __import__("hashlib").sha256(
                        (self.attribution / "coordinates_and_gmm.npz").read_bytes()
                    ).hexdigest()}}}))
        args = ["--input", self.input, "--run-root", run_root,
                "--production-attribution-dir", self.attribution,
                "--saved-evaluation-dir", self.saved,
                "--fair-scoring-summary", fair / "summary.json",
                "--output", run_root / "evaluation", "--chunk-size", 64,
                "--allow-outside-slurm"]
        return run_root, args

    def test_gate_d_reproduces_n12_and_scores_larger_counts(self):
        run_root, args = self.gate_d_runs("gate_d_ok")
        run("evaluate_gate_d_pixel_counts.py", *args)
        summary = json.loads((run_root / "evaluation" / "summary.json").read_text())
        self.assertEqual(summary["status"], "complete")
        self.assertTrue(summary["n12_reproduction"]["passed"])
        self.assertEqual(summary["n12_reproduction"]["order_differing_positions"], 0)
        self.assertEqual(
            summary["n12_reproduction"]["max_relative_attribution_difference"]["maximum"], 0.0)
        self.assertAlmostEqual(summary["change_vs_saved_n12_at_K_bin"]["12"], 0.0, places=12)
        self.assertEqual(summary["jaccard_vs_n12_at_K_bin"]["12"], 1.0)
        self.assertEqual(set(summary["mSCF1"]), {"12", "48", "192"})
        self.assertTrue(summary["gmm_label_alignment"]["192"]["identity"])
        self.assertTrue(all(summary["distinct_from_next_smaller"].values()))
        self.assertIn("1.0", summary["descriptive_ig_minus_posterior_abs_pcc"]["48"])
        again = run("evaluate_gate_d_pixel_counts.py", *args)
        self.assertIn("skipped", again.stdout)

    def test_gate_d_order_change_with_identical_set_passes(self):
        run_root, args = self.gate_d_runs("gate_d_order", n12_arrays=self.swapped_n12(True))
        run("evaluate_gate_d_pixel_counts.py", *args)
        summary = json.loads((run_root / "evaluation" / "summary.json").read_text())
        reproduction = summary["n12_reproduction"]
        self.assertEqual(summary["status"], "complete")
        self.assertTrue(reproduction["passed"])
        self.assertTrue(reproduction["identical_bin_set"])
        self.assertGreater(reproduction["order_differing_positions"], 0)
        self.assertGreater(reproduction["max_relative_attribution_difference"]["maximum"], 0.0)

    def test_gate_d_stops_when_n12_bin_set_differs(self):
        run_root, args = self.gate_d_runs("gate_d_bad", n12_arrays=self.swapped_n12(False))
        result = run("evaluate_gate_d_pixel_counts.py", *args, check=False)
        self.assertEqual(result.returncode, 4)
        summary = json.loads((run_root / "evaluation" / "summary.json").read_text())
        self.assertEqual(summary["status"], "reproduction_failed")
        self.assertFalse(summary["n12_reproduction"]["identical_bin_set"])
        self.assertNotIn("mSCF1", summary)
        # A failed result is never reused or overwritten.
        self.assertEqual(run("evaluate_gate_d_pixel_counts.py", *args,
                             check=False).returncode, 3)

    def test_gate_d_refuses_a_different_gmm_assignment(self):
        component = np.load(self.attribution / "coordinates_and_gmm.npz")["component"]
        run_root, args = self.gate_d_runs("gate_d_gmm", n48_component=1 - component)
        result = run("evaluate_gate_d_pixel_counts.py", *args, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GMM assignment differs", result.stderr)
        self.assertFalse((run_root / "evaluation" / "summary.json").exists())

    def test_gate_d_records_but_does_not_compare_gpu_posterior_diagnostic(self):
        # gate_d_runs gives each run a different posterior diagnostic (1e-7 * n).
        run_root, args = self.gate_d_runs("gate_d_diagnostic")
        run("evaluate_gate_d_pixel_counts.py", *args)
        summary = json.loads((run_root / "evaluation" / "summary.json").read_text())
        self.assertEqual(summary["status"], "complete")
        recorded = summary["run_diagnostics_not_in_signature"]
        self.assertAlmostEqual(
            recorded["192"]["differentiable_posterior_max_absolute_difference"], 1.92e-5)
        self.assertNotEqual(recorded["12"], recorded["48"])

    def test_gate_d_refuses_a_changed_run_configuration(self):
        run_root, args = self.gate_d_runs("gate_d_config")
        path = run_root / "n192" / "summary.json"
        summary = json.loads(path.read_text())
        summary["gmm"]["component_counts"] = {"0": 59, "1": 61}
        path.write_text(json.dumps(summary))
        result = run("evaluate_gate_d_pixel_counts.py", *args, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("run configuration differs from n=12", result.stderr)
        self.assertFalse((run_root / "evaluation" / "summary.json").exists())

    def test_gate_d_refuses_a_run_without_label_alignment(self):
        run_root, args = self.gate_d_runs("gate_d_unaligned")
        path = run_root / "n48" / "summary.json"
        summary = json.loads(path.read_text())
        del summary["gmm_label_alignment"]
        path.write_text(json.dumps(summary))
        result = run("evaluate_gate_d_pixel_counts.py", *args, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--align-gmm-labels-to-production", result.stderr)
        self.assertFalse((run_root / "evaluation" / "summary.json").exists())

    def test_gate_d_refuses_a_different_alignment_reference(self):
        run_root, args = self.gate_d_runs("gate_d_reference")
        path = run_root / "n12" / "summary.json"
        summary = json.loads(path.read_text())
        summary["gmm_label_alignment"]["production_reference"]["sha256"] = "0" * 64
        path.write_text(json.dumps(summary))
        result = run("evaluate_gate_d_pixel_counts.py", *args, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("different production reference", result.stderr)
        self.assertFalse((run_root / "evaluation" / "summary.json").exists())

    def test_gate_d_refuses_incomplete_ig(self):
        run_root, args = self.gate_d_runs("gate_d_incomplete")
        path = run_root / "n48" / "summary.json"
        summary = json.loads(path.read_text())
        summary["status"] = "needs_more_ig_steps"
        path.write_text(json.dumps(summary))
        result = run("evaluate_gate_d_pixel_counts.py", *args, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to score incomplete attributions", result.stderr)
        self.assertFalse((run_root / "evaluation" / "summary.json").exists())

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
