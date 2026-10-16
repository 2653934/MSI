"""Synthetic tests of the RCC options (protocol 18 Section 6.1, item D step 2).

1. Default paths are bit-identical: the fair-scoring and matched evaluators
   without the new flags give the same outputs as the frozen pre-change copies
   in fixtures/pre_rcc/ (commit 6d889c1), with legacy and with an approved
   partition. Only runtimes and code hashes may differ.
2. --class-subset keeps the rankings, K_bin and reproduction checks, and scores
   with the subset's PCCs only; a subset listing every class is refused.
3. --no-legacy needs a reference budget whose K_bin and input match.
4. compute_reference_budget.py gives K_bin = |R@0.4| over all classes.
5. summarise_rcc_fair_scoring.py: a verdict only with all 8 runs, none for the
   sensitivity analysis, and no mixing of primary and subset results.
Requires h5py, sklearn and matplotlib (cluster env).
"""

import hashlib
import json
import os
import shutil
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
except ImportError:  # pragma: no cover - environments without these
    DEPENDENCIES = False

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pre_rcc"
# sha256 of the two scripts at commit 6d889c1, before the RCC options were added.
FIXTURE_SHA256 = {
    "evaluate_fair_scoring_baselines.py":
        "cd88bd02a1aaf642bc2c9976390770a429d5549388f16bc6f4fc44e0372ccb6f",
    "evaluate_spatial_msipl_attributed_peaks.py":
        "2c33904f917cf394e45249e73cd290a7b89f5c5da17a622c94628199342c6dc4",
}
RCC_SECTIONS = ("RCC_MH0204_33", "RCC_UH0505_12", "RCC_UH0710_33", "RCC_UH9610_15",
                "RCC_UH9812_03", "RCC_UH9905_18", "RCC_UH9911_05", "RCC_UH9912_01")


def run(script, *arguments, check=True, directory=SCRIPTS):
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src"), str(SCRIPTS), environment.get("PYTHONPATH", "")])
    environment["MPLBACKEND"] = "Agg"
    return subprocess.run(
        [sys.executable, str(directory / script), *map(str, arguments)],
        env=environment, capture_output=True, text=True, check=check)


def build_section(root, name, n_classes, seed):
    """A small synthetic section, its GMM/IG artifacts and a legacy list."""
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler

    rng = np.random.default_rng(seed)
    xs, ys = np.meshgrid(np.arange(1, 16), np.arange(1, 11))
    x, y = xs.reshape(-1), ys.reshape(-1)
    labels = np.minimum((x - 1) * n_classes // 15, n_classes - 1).astype(np.int64)
    n_bins = 240
    mz = 300.0 * (1 + 15e-6) ** np.arange(n_bins)
    mz[120:] += 0.5
    centres = np.arange(5, n_bins, 12)
    profile = np.zeros(n_bins)
    for centre in centres:
        profile += np.exp(-0.5 * ((np.arange(n_bins) - centre) / 1.5) ** 2)
    data = rng.gamma(2.0, 1.0, (len(x), n_bins)) * 0.05 + profile
    for c in range(n_classes):
        data[:, centres[c::n_classes]] *= (1 + 2.0 * (labels == c))[:, None]
    path = root / f"{name}.h5"
    with h5py.File(path, "w") as handle:
        handle["Data"] = data.astype(np.float32)
        handle["mzArray"] = mz
        handle["Class_Label"] = labels  # raw labels 0..K-1, as in the RCC export
        handle["xLocation"] = x
        handle["yLocation"] = y

    latent = np.column_stack((labels + rng.normal(0, 0.2, len(x)),
                              rng.normal(size=(len(x), 4))))
    scaler = StandardScaler().fit(latent)
    gmm = GaussianMixture(n_classes, covariance_type="full", random_state=1).fit(
        scaler.transform(latent))
    posterior = gmm.predict_proba(scaler.transform(latent))
    component = np.argmax(posterior, axis=1)
    attribution = root / f"{name}_attribution"
    attribution.mkdir()
    np.save(attribution / "latent_mean.npy", latent.astype(np.float32))
    np.savez(attribution / "gmm_parameters.npz",
             scaler_mean=scaler.mean_, scaler_scale=scaler.scale_,
             mixture_weights=gmm.weights_.astype(np.float32),
             component_means=gmm.means_.astype(np.float32),
             covariances=gmm.covariances_.astype(np.float32),
             precision_cholesky=gmm.precisions_cholesky_.astype(np.float32))
    np.savez(attribution / "coordinates_and_gmm.npz", x=x, y=y, component=component,
             assigned_posterior=posterior[np.arange(len(x)), component].astype(np.float32))
    (attribution / "summary.json").write_text(json.dumps({"status": "valid"}))
    arrays = {"mz": mz.astype(np.float32),
              "first_layer_combined_l2": rng.random(n_bins).astype(np.float32)}
    for c in range(n_classes):
        ig = np.abs(rng.normal(size=n_bins)) * 0.1
        ig[centres[c::n_classes]] += 1.0
        arrays[f"component_{c}_combined_absolute_mean"] = ig.astype(np.float32)
    np.savez(attribution / "attributions.npz", **arrays)
    return path, attribution, labels, mz, centres


@unittest.skipUnless(DEPENDENCIES, "h5py/sklearn/matplotlib not installed")
class RccPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path[:0] = [str(ROOT / "src"), str(SCRIPTS)]
        from evaluate_spatial_msipl_attributed_peaks import load_correlations, score_indices
        from evaluate_msipl_massnet_peaks import true_indices_at_threshold

        cls.tmp = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.tmp.name)

        # Two-class section with a legacy list: the GBM/CAC default path.
        cls.input2, cls.attribution2, labels2, mz2, centres2 = build_section(
            root, "SYN2", 2, seed=0)
        cls.k2 = 20
        legacy = centres2[:cls.k2]
        correlations2 = load_correlations(cls.input2, labels2, len(mz2), True, 64)
        legacy_score = score_indices(legacy, correlations2, len(mz2))
        cls.legacy_peaks = root / "learned_peaks.csv"
        np.savetxt(cls.legacy_peaks, mz2[legacy], delimiter=",", header="mz_peak",
                   comments="")
        cls.legacy_metrics = root / "peak_metrics.json"
        cls.legacy_metrics.write_text(json.dumps({
            "unique_nearest_bins": cls.k2, "mSCF1": legacy_score["mSCF1"],
            "mixed_f1": legacy_score["mixed_f1"],
            "threshold_results": legacy_score["threshold_results"]}))
        cls.partitions2 = root / "partitions2"
        run("audit_peak_partitions.py", "--input", cls.input2, "--output", cls.partitions2,
            "--chunk-size", 64, "--allow-outside-slurm")
        audit = json.loads((cls.partitions2 / "summary.json").read_text())
        cls.approval2 = root / "approval2.json"
        cls.approval2.write_text(json.dumps({"status": "approved", "partitions": {"P1": {
            "parameters": audit["partitions"]["P1"]["parameters"],
            "sections": {"SYN2": audit["partitions"]["P1"]["structure"]["sha256"]}}}}))

        # Three-class RCC-like section without legacy.
        cls.input3, cls.attribution3, labels3, mz3, _ = build_section(
            root, "RCC_SYN", 3, seed=3)
        correlations3 = load_correlations(cls.input3, labels3, len(mz3), True, 64)
        cls.expected_k3 = len(set().union(*(true_indices_at_threshold(correlations3[c], 0.4)
                                            for c in range(3))))
        cls.budget3 = root / "RCC_SYN_budget" / "reference_budget.json"
        run("compute_reference_budget.py", "--input", cls.input3, "--output", cls.budget3,
            "--descriptive-class-subset", 0, 1, "--chunk-size", 64, "--allow-outside-slurm")
        cls.k3 = json.loads(cls.budget3.read_text())["K_bin"]
        cls.saved3 = root / "RCC_SYN_saved"
        run("evaluate_spatial_msipl_attributed_peaks.py", "--input", cls.input3,
            "--attribution-dir", cls.attribution3, "--no-legacy", "--output", cls.saved3,
            "--matched-count", cls.k3, "--chunk-size", 64, "--ion-images", 2,
            "--consolidated-candidates", 5)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    # ----- helpers -----
    def matched2(self, output, directory=SCRIPTS):
        run("evaluate_spatial_msipl_attributed_peaks.py", "--input", self.input2,
            "--attribution-dir", self.attribution2, "--legacy-peaks", self.legacy_peaks,
            "--legacy-metrics", self.legacy_metrics, "--output", output,
            "--matched-count", self.k2, "--chunk-size", 64, "--ion-images", 2,
            "--consolidated-candidates", 5, directory=directory)
        return output

    def fair2(self, output, saved, *extra, directory=SCRIPTS, check=True):
        return run("evaluate_fair_scoring_baselines.py", "--input", self.input2,
                   "--attribution-dir", self.attribution2, "--saved-evaluation-dir", saved,
                   "--legacy-peaks", self.legacy_peaks, "--legacy-metrics",
                   self.legacy_metrics, "--output", output, "--random-draws", 5,
                   "--chunk-size", 64, "--allow-outside-slurm", *extra,
                   directory=directory, check=check)

    def fair3(self, output, *extra, budget=None, check=True):
        return run("evaluate_fair_scoring_baselines.py", "--input", self.input3,
                   "--attribution-dir", self.attribution3, "--saved-evaluation-dir",
                   self.saved3, "--no-legacy", "--reference-budget", budget or self.budget3,
                   "--output", output, "--random-draws", 5, "--chunk-size", 64,
                   "--allow-outside-slurm", *extra, check=check)

    @staticmethod
    def comparable(path):
        """A summary without runtimes and code hashes, the only fields allowed to differ."""
        summary = json.loads(Path(path).read_text())
        summary.pop("runtime_seconds", None)
        summary.get("provenance", {}).pop("code", None)
        return summary

    def assert_npz_equal(self, left, right):
        a, b = np.load(left), np.load(right)
        self.assertEqual(sorted(a.files), sorted(b.files))
        for key in a.files:
            np.testing.assert_array_equal(a[key], b[key], err_msg=key)

    # ----- 1. default paths are bit-identical to the pre-change code -----
    def test_fixtures_are_the_pre_change_scripts(self):
        for name, expected in FIXTURE_SHA256.items():
            digest = hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
            self.assertEqual(digest, expected, name)

    def test_matched_evaluator_default_path_is_unchanged(self):
        new = self.matched2(self.root / "matched_new")
        old = self.matched2(self.root / "matched_old", directory=FIXTURES)
        self.assertEqual(self.comparable(new / "summary.json"),
                         self.comparable(old / "summary.json"))
        for csv_name in sorted(p.name for p in old.glob("*.csv")):
            self.assertEqual((new / csv_name).read_bytes(), (old / csv_name).read_bytes(),
                             csv_name)

    def test_fair_scoring_default_path_is_unchanged(self):
        saved = self.matched2(self.root / "saved2")
        cases = {"bin": (), "p1": ("--partition-dir", self.partitions2,
                                   "--partition-approval", self.approval2)}
        for case, extra in cases.items():
            new, old = self.root / f"fair2_new_{case}", self.root / f"fair2_old_{case}"
            self.fair2(new, saved, *extra)
            self.fair2(old, saved, *extra, directory=FIXTURES)
            self.assertEqual(self.comparable(new / "summary.json"),
                             self.comparable(old / "summary.json"), case)
            self.assert_npz_equal(new / "rankings_prefix.npz", old / "rankings_prefix.npz")
            if case == "p1":
                self.assert_npz_equal(new / "peak_level_selections.npz",
                                      old / "peak_level_selections.npz")
            self.assertNotIn("class_subset", json.loads((new / "summary.json").read_text()))

    # ----- 2. class subset -----
    def test_class_subset_keeps_rankings_and_scores_with_subset_only(self):
        from evaluate_spatial_msipl_attributed_peaks import (
            load_correlations, read_h5_metadata, score_indices)
        primary, subset = self.root / "rcc_primary", self.root / "rcc_subset"
        self.fair3(primary)
        self.fair3(subset, "--class-subset", 1, 0)
        a = json.loads((primary / "summary.json").read_text())
        b = json.loads((subset / "summary.json").read_text())
        self.assertEqual(b["class_subset"]["classes"], [0, 1])
        self.assertEqual(b["provenance"]["parameters"]["class_subset"], [0, 1])
        self.assertEqual(a["K_bin"], b["K_bin"])
        self.assertEqual(a["provenance_checks"], b["provenance_checks"])
        ra, rb = np.load(primary / "rankings_prefix.npz"), np.load(subset / "rankings_prefix.npz")
        for name in ra.files:
            if name != "oracle":  # the oracle is label-based, so it follows the subset
                np.testing.assert_array_equal(ra[name], rb[name], err_msg=name)
        mz, labels, _, _, first = read_h5_metadata(self.input3)
        correlations = load_correlations(self.input3, labels, len(mz), first, 64)
        two = {c: correlations[c] for c in (0, 1)}
        ig = ra["integrated_gradients"][:a["K_bin"]]
        self.assertAlmostEqual(b["bin_level"]["integrated_gradients"]["1.0"]["mSCF1"],
                               score_indices(ig, two, len(mz))["mSCF1"], places=12)
        self.assertAlmostEqual(a["bin_level"]["integrated_gradients"]["1.0"]["mSCF1"],
                               score_indices(ig, correlations, len(mz))["mSCF1"], places=12)
        threshold = b["bin_level"]["integrated_gradients"]["1.0"]["threshold_results"]["0.4"]
        self.assertEqual(sorted(threshold["class_metrics"]), ["0", "1"])

    def test_class_subset_listing_every_class_or_an_unknown_class_is_refused(self):
        for values in ((0, 1, 2), (0, 5)):
            output = self.root / f"bad_subset_{len(values)}"
            result = self.fair3(output, "--class-subset", *values, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((output / "summary.json").exists())

    # ----- 3. no legacy -----
    def test_no_legacy_records_the_note_and_omits_legacy_rows(self):
        output = self.root / "rcc_no_legacy"
        self.fair3(output)
        summary = json.loads((output / "summary.json").read_text())
        self.assertEqual(summary["legacy_msipl"],
                         "legacy msiPL not run on RCC (requires count tuning)")
        self.assertNotIn("legacy_msipl", summary["bin_level"])
        self.assertNotIn("legacy_msipl", summary["collapse_rule_a_first_K_bin"])
        self.assertNotIn("legacy_peaks", summary["provenance"]["source_artifacts"])
        self.assertIn("reference_budget", summary["provenance"]["source_artifacts"])
        self.assertNotIn("legacy_msipl", np.load(output / "rankings_prefix.npz").files)
        saved = json.loads((self.saved3 / "summary.json").read_text())
        self.assertNotIn("legacy_msipl", saved["matched_peak_evaluation"]["methods"])

    def test_no_legacy_refuses_a_budget_that_differs(self):
        budget = json.loads(self.budget3.read_text())
        budget["K_bin"] += 1
        wrong = self.root / "wrong_budget.json"
        wrong.write_text(json.dumps(budget))
        output = self.root / "rcc_wrong_budget"
        result = self.fair3(output, budget=wrong, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("differs from the reference budget", result.stderr)
        self.assertFalse((output / "summary.json").exists())

    def test_no_legacy_and_legacy_files_are_exclusive(self):
        result = run("evaluate_fair_scoring_baselines.py", "--input", self.input3,
                     "--attribution-dir", self.attribution3, "--saved-evaluation-dir",
                     self.saved3, "--no-legacy", "--legacy-peaks", self.legacy_peaks,
                     "--reference-budget", self.budget3, "--output", self.root / "x",
                     "--allow-outside-slurm", check=False)
        self.assertNotEqual(result.returncode, 0)
        result = run("evaluate_fair_scoring_baselines.py", "--input", self.input3,
                     "--attribution-dir", self.attribution3, "--saved-evaluation-dir",
                     self.saved3, "--no-legacy", "--output", self.root / "y",
                     "--allow-outside-slurm", check=False)
        self.assertIn("requires --reference-budget", result.stderr)

    # ----- 4. reference budget -----
    def test_reference_budget_is_r04_over_all_classes(self):
        budget = json.loads(self.budget3.read_text())
        self.assertEqual(budget["K_bin"], self.expected_k3)
        self.assertEqual(budget["K_bin"], budget["reference_set_sizes_all_classes"]["0.4"])
        self.assertEqual(budget["classes"], [0, 1, 2])
        self.assertIn("never a budget", budget["reference_set_sizes_descriptive_subset"]["use"])
        again = run("compute_reference_budget.py", "--input", self.input3, "--output",
                    self.budget3, "--descriptive-class-subset", 0, 1, "--chunk-size", 64,
                    "--allow-outside-slurm")
        self.assertIn("skipped", again.stdout)
        stale = run("compute_reference_budget.py", "--input", self.input3, "--output",
                    self.budget3, "--chunk-size", 64, "--allow-outside-slurm", check=False)
        self.assertEqual(stale.returncode, 3)

    # ----- 5. RCC summariser -----
    def summary_tree(self, name, source, sections=RCC_SECTIONS):
        root = self.root / name
        for section in sections:
            for arm in ("central_only", "uniform_mean"):
                target = root / f"{section}_seed1" / arm
                target.mkdir(parents=True)
                shutil.copy(source / "summary.json", target / "summary.json")
        return root

    def test_rcc_summariser_verdicts_and_sensitivity(self):
        primary, subset = self.root / "sum_primary", self.root / "sum_subset"
        self.fair3(primary)
        self.fair3(subset, "--class-subset", 0, 1)
        tree = self.summary_tree("tree_full", primary)
        run("summarise_rcc_fair_scoring.py", "--root", tree, "--output", self.root / "d_full")
        decisions = json.loads((self.root / "d_full" / "decisions.json").read_text())
        record = decisions["RCC/central_only"]
        self.assertEqual(record["ig_minus_posterior_bin"]["sections"], 8)
        self.assertFalse(record["ig_vs_posterior_verdict"].startswith("incomplete"))
        self.assertTrue(any("may include tissue" in d for d in record["disclosures"]))
        self.assertEqual(len(decisions["_patients"]["mapping"]), 8)

        partial = self.summary_tree("tree_partial", primary, RCC_SECTIONS[:7])
        run("summarise_rcc_fair_scoring.py", "--root", partial, "--output", self.root / "d_7")
        record = json.loads((self.root / "d_7" / "decisions.json").read_text())["RCC/uniform_mean"]
        self.assertTrue(record["ig_vs_posterior_verdict"].startswith("incomplete"))

        sens = self.summary_tree("tree_sens", subset)
        run("summarise_rcc_fair_scoring.py", "--root", sens, "--output", self.root / "d_s",
            "--sensitivity")
        record = json.loads((self.root / "d_s" / "decisions.json").read_text())["RCC/central_only"]
        self.assertIsNone(record["ig_vs_posterior_verdict"])
        self.assertEqual(record["label"], "sensitivity, cancer/normal classes only")

        refused = run("summarise_rcc_fair_scoring.py", "--root", sens, "--output",
                      self.root / "d_bad", check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("class-subset result in the primary table", refused.stderr)

        other = self.summary_tree("tree_other", primary, ("40TopL",))
        refused = run("summarise_rcc_fair_scoring.py", "--root", other, "--output",
                      self.root / "d_other", check=False)
        self.assertIn("is not an RCC run", refused.stderr)


if __name__ == "__main__":
    unittest.main()
