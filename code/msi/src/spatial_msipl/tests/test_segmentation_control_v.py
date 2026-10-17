"""Test V: VAE segmentation vs a PCA segmentation (protocol 18 Section 6.4).

Synthetic sections only. The section scripts run as subprocesses against the real
fair-scoring evaluator's outputs, as in test_spatial_segmentation.py.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

try:
    import h5py  # noqa: F401
    import sklearn  # noqa: F401
    import matplotlib  # noqa: F401
    HAVE_STACK = True
except ImportError:  # pragma: no cover - the cluster test job has all three
    HAVE_STACK = False

if HAVE_STACK:
    from spatial_msipl import segmentation_control as sc


@unittest.skipUnless(HAVE_STACK, "h5py, sklearn and matplotlib are required")
class PreprocessingTests(unittest.TestCase):
    """PCA must see exactly the centre input the VAE's encoder receives."""

    def test_inputs_equal_the_training_dataset_target_in_both_layouts(self):
        from spatial_msipl.preprocessing import (
            CachedH5SpatialContextDataset, H5SpatialContextDataset)
        rng = np.random.default_rng(3)
        xs, ys = np.meshgrid(np.arange(1, 7), np.arange(1, 6))
        x, y = xs.ravel(), ys.ravel()
        data = rng.gamma(2.0, 1.0, (len(x), 37)).astype(np.float32)
        data[4] = 0.0                                   # a zero-TIC pixel stays zero
        for pixels_first in (True, False):
            folder = Path(tempfile.mkdtemp())
            path = folder / "section.h5"
            with h5py.File(path, "w") as handle:
                handle["Data"] = data if pixels_first else data.T
                handle["mzArray"] = np.linspace(100, 200, data.shape[1])
                handle["Class_Label"] = (x > 2).astype(np.int64)
                handle["xLocation"] = x
                handle["yLocation"] = y
            inputs = sc.vae_centre_inputs(path)
            self.assertEqual(inputs.dtype, np.float32)
            for dataset_class in (CachedH5SpatialContextDataset, H5SpatialContextDataset):
                dataset = dataset_class(path, include_neighbourhood=True)
                for index in range(len(x)):
                    np.testing.assert_array_equal(inputs[index], dataset[index]["target"],
                                                  err_msg=f"{dataset_class.__name__} {index}")
                dataset.close()
            self.assertTrue(np.all(inputs[4] == 0))

    def test_function_names_are_recorded(self):
        record = sc.PREPROCESSING_RECORD
        self.assertIn("spatial_msipl.preprocessing.tic_normalize", record["function"])
        self.assertIn("H5SpatialContextDataset.__getitem__", record["matches"])


@unittest.skipUnless(HAVE_STACK, "h5py, sklearn and matplotlib are required")
class PcaSegmentationTests(unittest.TestCase):
    def test_predeclared_pca_and_gmm_settings(self):
        from sklearn.decomposition import PCA
        from sklearn.mixture import GaussianMixture
        from sklearn.preprocessing import StandardScaler
        rng = np.random.default_rng(0)
        features = np.vstack([rng.normal(0, 1, (60, 30)), rng.normal(3, 1, (60, 30))])
        features = features.astype(np.float32)
        posterior, component, record = sc.pca_segmentation(features, 5, k=2)
        scores = PCA(n_components=5, svd_solver="randomized", random_state=1).fit_transform(
            features).astype(np.float64)   # scores are clustered in float64, as Test S
        expected = GaussianMixture(2, covariance_type="full", reg_covar=1e-6, n_init=20,
                                   random_state=1).fit(StandardScaler().fit_transform(scores))
        np.testing.assert_allclose(
            posterior, expected.predict_proba(StandardScaler().fit_transform(scores)))
        np.testing.assert_array_equal(component, np.argmax(posterior, axis=1))
        self.assertEqual(record["n_components"], 5)
        self.assertEqual(len(record["explained_variance_ratio"]), 5)
        self.assertAlmostEqual(record["explained_variance_ratio_sum"],
                               float(np.sum(record["explained_variance_ratio"])))
        self.assertEqual(record["gmm"], {"components": 2, "covariance_type": "full",
                                         "reg_covar": 1e-6, "n_init": 20, "seed": 1,
                                         "scaler": "StandardScaler"})
        self.assertEqual(record["pca"], {"svd_solver": "randomized", "random_state": 1})
        self.assertEqual(sum(record["component_counts"]), 120)

    def test_fixed_constants(self):
        self.assertEqual(sc.PRIMARY_COMPONENTS, 5)
        self.assertEqual(sc.SENSITIVITY_COMPONENTS, 20)
        self.assertEqual((sc.GMM_N_INIT, sc.GMM_SEED, sc.REG_COVAR, sc.PCA_SEED),
                         (20, 1, 1e-6, 1))


def paired_record(differences):
    differences = np.asarray(differences, dtype=float)
    return {"sections": len(differences), "mean_difference": float(differences.mean()),
            "positive_sections": int(np.sum(differences > 0))}


@unittest.skipUnless(HAVE_STACK, "h5py, sklearn and matplotlib are required")
class DecisionRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import summarise_segmentation_control_v as summary
        cls.s = summary

    def decide(self, *scales, n=8):
        return self.s.decide({f"s{i}": paired_record(d) for i, d in enumerate(scales)}, n)

    def test_helps_needs_mean_and_six_of_eight_at_every_scale(self):
        helps = [0.05] * 6 + [-0.01] * 2
        self.assertEqual(self.decide(helps, helps), self.s.HELPS)
        self.assertEqual(self.decide(helps, [0.05] * 5 + [-0.01] * 3), self.s.MIXED)
        self.assertEqual(self.decide(helps, [0.019] * 8), self.s.MIXED)

    def test_pca_better_needs_mean_and_at_most_two_positive_at_every_scale(self):
        worse = [-0.05] * 6 + [0.01] * 2
        self.assertEqual(self.decide(worse, worse), self.s.PCA_BETTER)
        self.assertEqual(self.decide(worse, [-0.05] * 5 + [0.01] * 3), self.s.MIXED)
        self.assertEqual(self.decide(worse, [-0.019] * 8), self.s.MIXED)

    def test_equivalent_and_boundaries(self):
        self.assertEqual(self.decide([0.019] * 8, [-0.019] * 8), self.s.EQUIVALENT)
        self.assertEqual(self.decide([0.02] * 8), self.s.HELPS)
        self.assertEqual(self.decide([-0.02] * 8), self.s.PCA_BETTER)
        self.assertEqual(self.decide([0.02] * 8, n=7), "incomplete; no verdict (7/8 sections)")


@unittest.skipUnless(HAVE_STACK, "h5py, sklearn and matplotlib are required")
class SectionScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from spatial_msipl.tests.test_rcc_pipeline import build_section, run
        cls.run_script = staticmethod(run)
        cls.tmp = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.tmp.name)
        cls.input, cls.attribution, _, _, _ = build_section(root, "SYN", 2, seed=5)
        (cls.attribution / "summary.json").write_text(json.dumps(
            {"status": "valid", "gmm": {"components": 2, "n_init": 1, "seed": 1}}))
        cls.partitions = root / "partitions"
        run("audit_peak_partitions.py", "--input", cls.input, "--output", cls.partitions,
            "--chunk-size", 64, "--allow-outside-slurm")
        audit = json.loads((cls.partitions / "summary.json").read_text())
        approval = root / "approval.json"
        approval.write_text(json.dumps({"status": "approved", "partitions": {"P1": {
            "parameters": audit["partitions"]["P1"]["parameters"],
            "sections": {"SYN": audit["partitions"]["P1"]["structure"]["sha256"]}}}}))
        budget = root / "budget" / "reference_budget.json"
        run("compute_reference_budget.py", "--input", cls.input, "--output", budget,
            "--chunk-size", 64, "--allow-outside-slurm")
        k = json.loads(budget.read_text())["K_bin"]
        saved = root / "saved"
        run("evaluate_spatial_msipl_attributed_peaks.py", "--input", cls.input,
            "--attribution-dir", cls.attribution, "--no-legacy", "--output", saved,
            "--matched-count", k, "--chunk-size", 64, "--ion-images", 2,
            "--consolidated-candidates", 5)
        common = ["--input", cls.input, "--attribution-dir", cls.attribution,
                  "--saved-evaluation-dir", saved, "--no-legacy", "--reference-budget", budget,
                  "--random-draws", 5, "--chunk-size", 64, "--allow-outside-slurm"]
        cls.fair_p1 = root / "fair_p1"
        run("evaluate_fair_scoring_baselines.py", *common, "--output", cls.fair_p1,
            "--partition-dir", cls.partitions, "--partition-approval", approval)
        cls.fair_bin = root / "fair_bin"
        run("evaluate_fair_scoring_baselines.py", *common, "--output", cls.fair_bin)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def score_v(self, output, fair, *extra, attribution=None, check=True, partitions=True):
        arguments = ["--input", self.input, "--attribution-dir", attribution or self.attribution,
                     "--fair-scoring-summary", fair / "summary.json", "--output", output,
                     "--chunk-size", 64, "--allow-outside-slurm", *extra]
        if partitions:
            arguments += ["--partition-dir", self.partitions]
        return self.run_script("evaluate_segmentation_control_v.py", *arguments, check=check)

    def assert_refused(self, result, text):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(text, result.stderr)

    def test_scores_both_pca_segmentations_and_records_checks(self):
        output = self.root / "v"
        self.score_v(output, self.fair_p1, "--uniform-fair-scoring-summary",
                     self.fair_p1 / "summary.json")
        summary = json.loads((output / "summary.json").read_text())
        self.assertEqual(summary["checks"]["production_refit_ari_to_saved"], 1.0)
        self.assertEqual(set(summary["checks"]["reproduced_mSCF1"]),
                         {"bin:posterior_abs_pcc_balanced", "bin:morans_i",
                          "P1:posterior_abs_pcc_balanced", "P1:morans_i"})
        for scale in ("bin", "P1"):
            self.assertEqual(set(summary["mSCF1"][scale]),
                             {"posterior_abs_pcc_balanced", "morans_i",
                              "pca5_posterior_abs_pcc_balanced",
                              "pca20_posterior_abs_pcc_balanced"})
            self.assertAlmostEqual(
                summary["vae_minus_pca5"][scale],
                summary["mSCF1"][scale]["posterior_abs_pcc_balanced"]
                - summary["mSCF1"][scale]["pca5_posterior_abs_pcc_balanced"])
            self.assertIn("integrated_gradients", summary["saved_descriptive"][scale])
            self.assertIn("vae_uniform_mean_posterior_abs_pcc_balanced",
                          summary["saved_descriptive"][scale])
        self.assertEqual(summary["pca"]["pca5"]["n_components"], 5)
        self.assertEqual(summary["pca"]["pca20"]["n_components"], 20)
        self.assertIn("balanced_accuracy", summary["segmentation_vs_expert"]["pca5"])
        self.assertIn("balanced_accuracy", summary["segmentation_vs_expert"]["vae_central_only"])
        self.assertEqual(summary["provenance"]["parameters"]["preprocessing"],
                         sc.PREPROCESSING_RECORD)
        # A second run with the same inputs is skipped, not recomputed.
        self.assertIn("skipped", self.score_v(output, self.fair_p1, "--uniform-fair-scoring-summary",
                                              self.fair_p1 / "summary.json").stdout)

    def test_pca_ranking_is_the_posterior_pcc_ranking_of_the_pca_posterior(self):
        from evaluate_fair_scoring_baselines import tic_statistics
        from evaluate_spatial_msipl_attributed_peaks import read_h5_metadata
        from spatial_msipl.simple_baselines import moore_edges, one_hot_maps, posterior_pcc_rankings
        output = self.root / "v_rank"
        self.score_v(output, self.fair_bin, partitions=False)
        mz, labels, x, y, pixels_first = read_h5_metadata(self.input)
        posterior, component, _ = sc.pca_segmentation(sc.vae_centre_inputs(self.input), 5, k=2)
        sources, targets = moore_edges(x, y)
        _, pcc, _ = tic_statistics(self.input, pixels_first, len(mz), 64,
                                   {"soft": posterior, "hard": one_hot_maps(component, 2)},
                                   sources, targets)
        expected = posterior_pcc_rankings(pcc["soft"], pcc["hard"])["posterior_abs_pcc_balanced"]
        saved = np.load(output / "rankings_prefix.npz")["pca5_posterior_abs_pcc_balanced"]
        np.testing.assert_array_equal(saved, expected[:len(saved)])

    def test_bin_only_and_missing_uniform_summary(self):
        output = self.root / "v_bin"
        self.score_v(output, self.fair_bin, partitions=False)
        summary = json.loads((output / "summary.json").read_text())
        self.assertEqual(set(summary["mSCF1"]), {"bin"})
        self.assertIsNone(summary["saved_descriptive"]["bin"][
            "vae_uniform_mean_posterior_abs_pcc_balanced"])

    def test_partition_arguments_must_match_the_fair_summary(self):
        self.assert_refused(self.score_v(self.root / "r1", self.fair_p1, partitions=False,
                                        check=False), "--partition-dir is required")
        self.assert_refused(self.score_v(self.root / "r2", self.fair_bin, check=False),
                            "has no approved P1")

    def fair_copy(self, name, edit, source=None):
        target = self.root / name
        shutil.copytree(source or self.fair_p1, target)
        summary = json.loads((target / "summary.json").read_text())
        edit(summary)
        (target / "summary.json").write_text(json.dumps(summary))
        return target

    def test_saved_scores_that_do_not_reproduce_are_refused(self):
        def edit(summary):
            summary["bin_level"]["posterior_abs_pcc_balanced"]["1.0"]["mSCF1"] += 1e-6
        self.assert_refused(self.score_v(self.root / "r3", self.fair_copy("f3", edit),
                                        check=False),
                            "posterior_abs_pcc_balanced: bin-level rescore")

    def test_refit_that_does_not_reproduce_the_saved_labels_is_refused(self):
        from spatial_msipl.provenance import file_record
        attribution = self.root / "attr_labels"
        shutil.copytree(self.attribution, attribution)
        saved = dict(np.load(attribution / "coordinates_and_gmm.npz"))
        saved["component"] = np.roll(saved["component"], 7)
        np.savez(attribution / "coordinates_and_gmm.npz", **saved)
        record = file_record(attribution / "coordinates_and_gmm.npz")

        def edit(summary):
            summary["provenance"]["source_artifacts"]["coordinates_and_gmm"] = record
        self.assert_refused(self.score_v(self.root / "r4", self.fair_copy("f4", edit),
                                        check=False, attribution=attribution), "ARI")

    def test_class_subset_or_other_section_is_refused(self):
        fair = self.fair_copy("f5", lambda s: s.update(class_subset={"classes": [0]}))
        self.assert_refused(self.score_v(self.root / "r5", fair, check=False), "class-subset")
        fair = self.fair_copy("f6", lambda s: s.update(dataset="OTHER"))
        self.assert_refused(self.score_v(self.root / "r6", fair, check=False), "another section")


def minimal_summary(section, vae, pca5, scales=("bin", "P1"), code="h"):
    return {
        "status": "complete", "dataset": section, "K_bin": 100,
        "provenance": {"test_v_version": 1, "code": code,
                       "parameters": {"scales": list(scales), "pca_components": [5, 20],
                                      "gmm_n_init": 20, "gmm_seed": 1, "reg_covar": 1e-6}},
        "mSCF1": {s: {"posterior_abs_pcc_balanced": vae, "pca5_posterior_abs_pcc_balanced": pca5,
                      "pca20_posterior_abs_pcc_balanced": pca5, "morans_i": 0.1}
                  for s in scales},
        "saved_descriptive": {s: {"integrated_gradients": 0.05,
                                  "vae_uniform_mean_posterior_abs_pcc_balanced": vae}
                              for s in scales},
        "segmentation_vs_expert": {"pca5": {"balanced_accuracy": 0.7},
                                   "pca20": {"balanced_accuracy": 0.7},
                                   "vae_central_only": {"balanced_accuracy": 0.8}},
        "pca": {"pca5": {"explained_variance_ratio_sum": 0.5},
                "pca20": {"explained_variance_ratio_sum": 0.8}},
    }


@unittest.skipUnless(HAVE_STACK, "h5py, sklearn and matplotlib are required")
class SummariserTests(unittest.TestCase):
    def write(self, root, collection, section, *args, **kwargs):
        folder = root / collection / f"{section}_seed1"
        folder.mkdir(parents=True)
        (folder / "summary.json").write_text(json.dumps(minimal_summary(section, *args, **kwargs)))

    def build(self, scales_for):
        from summarise_segmentation_control_v import SECTIONS
        root = Path(tempfile.mkdtemp())
        for collection, sections in SECTIONS.items():
            for section in sections:
                vae = 0.5 if collection == "GBM" else 0.3
                pca = 0.45 if collection == "GBM" else (0.3 if collection == "CAC" else 0.36)
                self.write(root, collection, section, vae, pca, scales=scales_for[collection])
        return root

    def test_verdicts_per_collection(self):
        from spatial_msipl.tests.test_rcc_pipeline import run
        root = self.build({"GBM": ("bin", "P1"), "CAC": ("bin", "P1"), "RCC": ("bin",)})
        output = root / "out"
        result = run("summarise_segmentation_control_v.py", "--root", root, "--output", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        decisions = json.loads((output / "decisions.json").read_text())
        self.assertEqual(decisions["GBM"]["verdict"], "VAE segmentation helps")
        self.assertEqual(decisions["CAC"]["verdict"], "equivalent")
        self.assertEqual(decisions["RCC"]["verdict"], "PCA better")
        self.assertEqual(set(decisions["RCC"]["vae_minus_pca5"]), {"bin"})
        self.assertIn("descriptive", decisions["GBM"]["descriptive"]["status"])
        self.assertIsNone(decisions["GBM"]["descriptive"]["d_vae_seed_mean_minus_pca5"])

    def test_wrong_scales_or_mixed_code_are_refused(self):
        from spatial_msipl.tests.test_rcc_pipeline import run
        root = self.build({"GBM": ("bin", "P1"), "CAC": ("bin", "P1"), "RCC": ("bin", "P1")})
        result = run("summarise_segmentation_control_v.py", "--root", root, "--output",
                     root / "o", check=False)
        self.assertNotEqual(result.returncode, 0)
        root = self.build({"GBM": ("bin", "P1"), "CAC": ("bin", "P1"), "RCC": ("bin",)})
        summary = json.loads((root / "GBM" / "GBM12_1_seed1" / "summary.json").read_text())
        summary["provenance"]["code"] = "other"
        (root / "GBM" / "GBM12_1_seed1" / "summary.json").write_text(json.dumps(summary))
        result = run("summarise_segmentation_control_v.py", "--root", root, "--output",
                     root / "o", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("different code", result.stderr)

    def test_seed_mean_uses_test_r_fair_scoring_when_complete(self):
        import summarise_segmentation_control_v as s
        fair = Path(tempfile.mkdtemp())
        for seed, value in ((2, 0.4), (3, 0.6)):
            folder = fair / "bin_level_only" / f"GBM12_1_seed{seed}" / "central_only"
            folder.mkdir(parents=True)
            (folder / "summary.json").write_text(json.dumps({
                "status": "complete", "class_subset": None,
                "bin_level": {"posterior_abs_pcc_balanced": {"1.0": {"mSCF1": value}}}}))
        values = s.test_r_values(fair, "GBM12_1", "bin")
        self.assertEqual(values, {2: 0.4, 3: 0.6})
        self.assertEqual(s.test_r_values(fair, "GBM12_2", "bin"), {})


class JobScriptTests(unittest.TestCase):
    def test_job_uses_the_central_only_fair_summary_and_a_new_root(self):
        script = (ROOT / "slurm_jobs" / "run_segmentation_control_v.sh").read_text(encoding="utf-8")
        self.assertIn("segmentation_control_V", script)
        self.assertIn("/central_only/summary.json", script)
        self.assertIn("/uniform_mean/summary.json", script)
        self.assertIn("with_approved_partitions", script)
        self.assertIn("rcc/bin_level_only", script)
        self.assertNotIn("--allow-outside-slurm", script)
        submit = (ROOT / "slurm_jobs" / "submit_segmentation_control_v.sh").read_text(
            encoding="utf-8")
        self.assertIn('concurrency="${concurrency:-2}"', submit)


if __name__ == "__main__":
    unittest.main()
