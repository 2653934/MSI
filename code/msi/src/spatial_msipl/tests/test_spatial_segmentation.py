"""Test S (protocol 18 Section 6.2; supervisor chat 2026-10-17 08:04).

1. Neighbourhoods: the smoothing neighbourhoods give exactly the measured Moore
   edges that ``evaluation.morans_i`` and the fair-scoring Moran's I use.
2. Weights: Cardinal 3.12.1 sigma = (2r+1)/4, Euclidean spatial distance, and
   the per-pixel adaptive scale s_i = max_j ||z_i - z_j|| / 2 + sqrt(eps),
   against a direct loop; missing neighbours carry no weight.
3. Identity: sigma -> 0 (with or without the adaptive weight) gives z~ = z, and
   the full pipeline then reproduces plain posterior-|PCC| exactly.
4. The decision rule and the summariser's refuse paths.
5. The per-section script's refuse paths (hashes, refit ARI, partitions,
   reproduction of the saved scores).
Parts 3 (pipeline) and 5 need h5py, sklearn and matplotlib.
"""

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
sys.path[:0] = [str(ROOT / "src"), str(SCRIPTS)]

from spatial_msipl import spatial_segmentation as ss  # noqa: E402
from spatial_msipl.evaluation import morans_i  # noqa: E402
from spatial_msipl.preprocessing import build_moore_neighbour_slots  # noqa: E402
from spatial_msipl.simple_baselines import moore_edges, morans_i_per_feature  # noqa: E402

try:
    import h5py  # noqa: F401
    import sklearn  # noqa: F401
    import matplotlib  # noqa: F401
    DEPENDENCIES = True
except ImportError:  # pragma: no cover
    DEPENDENCIES = False


def irregular_grid():
    """A 7 x 6 grid with holes and a ragged edge (measured pixels only)."""
    xs, ys = np.meshgrid(np.arange(1, 8), np.arange(1, 7))
    keep = ~(((xs == 3) & (ys == 3)) | ((xs == 6) & (ys <= 2)) | ((xs == 1) & (ys == 6)))
    return xs[keep].astype(np.int64), ys[keep].astype(np.int64)


class NeighbourhoodTests(unittest.TestCase):
    def test_edges_equal_the_morans_i_moore_edges(self):
        x, y = irregular_grid()
        neighbourhoods = ss.measured_neighbourhoods(x, y)
        self.assertTrue(np.array_equal(neighbourhoods[:, 0], np.arange(len(x))))
        sources, targets = ss.neighbourhood_edges(neighbourhoods)
        expected = moore_edges(x, y)
        self.assertEqual(sorted(zip(sources.tolist(), targets.tolist())),
                         sorted(zip(expected[0].tolist(), expected[1].tolist())))
        # evaluation.morans_i on its own slots equals Moran's I on these edges.
        values = np.random.default_rng(0).normal(size=len(x))
        slots = build_moore_neighbour_slots(x, y)
        self.assertAlmostEqual(morans_i(values, slots),
                               morans_i_per_feature(values[:, None], sources, targets)[0],
                               places=12)

    def test_offsets_match_the_slot_order(self):
        x, y = irregular_grid()
        neighbourhoods = ss.measured_neighbourhoods(x, y)
        lookup = {(a, b): i for i, (a, b) in enumerate(zip(x.tolist(), y.tolist()))}
        for i, (a, b) in enumerate(zip(x.tolist(), y.tolist())):
            for slot, (dx, dy) in enumerate(ss.OFFSETS):
                self.assertEqual(neighbourhoods[i, slot], lookup.get((a + dx, b + dy), -1))


class WeightTests(unittest.TestCase):
    def test_sigma_and_spatial_weights_follow_cardinal(self):
        self.assertEqual(ss.SIGMA, 0.75)
        x, y = irregular_grid()
        alpha = ss.spatial_weights(ss.measured_neighbourhoods(x, y))
        centre = len(x) // 2
        self.assertEqual(alpha[centre, 0], 1.0)
        for slot, (dx, dy) in enumerate(ss.OFFSETS):
            if ss.measured_neighbourhoods(x, y)[centre, slot] >= 0:
                self.assertAlmostEqual(alpha[centre, slot],
                                       np.exp(-(dx * dx + dy * dy) / (2 * 0.75 ** 2)), places=15)
        self.assertAlmostEqual(np.exp(-1 / 1.125), 0.4111, places=4)

    def test_adaptive_weights_match_a_direct_loop_of_cardinals_formula(self):
        x, y = irregular_grid()
        z = np.random.default_rng(1).normal(size=(len(x), 5))
        neighbourhoods = ss.measured_neighbourhoods(x, y)
        beta, scale = ss.adaptive_weights(z, neighbourhoods)
        eps = np.sqrt(np.finfo(float).eps)
        for i in range(len(x)):
            members = [j for j in neighbourhoods[i] if j >= 0]
            d = np.array([np.linalg.norm(z[i] - z[j]) for j in members])
            s = d.max() / 2 + eps
            self.assertAlmostEqual(scale[i], s, places=12)
            expected = dict(zip(members, np.exp(-d ** 2 / (2 * s ** 2))))
            for slot, j in enumerate(neighbourhoods[i]):
                self.assertAlmostEqual(beta[i, slot], expected.get(j, 0.0) if j >= 0 else 0.0,
                                       places=12)

    def test_missing_neighbours_carry_no_weight_and_smoothing_is_a_weighted_mean(self):
        x, y = irregular_grid()
        z = np.random.default_rng(2).normal(size=(len(x), 3))
        smoothed, record = ss.structure_adaptive_smoothing(z, x, y)
        neighbourhoods = ss.measured_neighbourhoods(x, y)
        beta, _ = ss.adaptive_weights(z, neighbourhoods)
        weights = ss.spatial_weights(neighbourhoods) * beta
        self.assertTrue(np.all(weights[neighbourhoods < 0] == 0))
        i = 0  # a corner pixel with missing neighbours
        members = [(s, j) for s, j in enumerate(neighbourhoods[i]) if j >= 0]
        expected = (sum(weights[i, s] * z[j] for s, j in members)
                    / sum(weights[i, s] for s, _ in members))
        np.testing.assert_allclose(smoothed[i], expected, rtol=0, atol=1e-12)
        constant = np.ones((len(x), 2)) * 3.5
        np.testing.assert_allclose(ss.structure_adaptive_smoothing(constant, x, y)[0], constant)
        self.assertEqual(record["sigma"], 0.75)
        self.assertIn("median_neighbour_distance_lambda_0804", record)

    def test_identity_limit_leaves_the_latents_unchanged(self):
        x, y = irregular_grid()
        z = np.random.default_rng(3).normal(size=(len(x), 5))
        for adaptive in (True, False):
            smoothed, _ = ss.structure_adaptive_smoothing(z, x, y, sigma=1e-6, adaptive=adaptive)
            self.assertTrue(np.array_equal(smoothed, z))


class FusionTests(unittest.TestCase):
    def test_mean_rank_with_ties_broken_by_the_primary(self):
        primary = np.array([0, 1, 2, 3])     # ranks 0 1 2 3
        secondary = np.array([3, 2, 1, 0])   # ranks 3 2 1 0 -> all means 1.5
        self.assertEqual(ss.rank_fusion(primary, secondary).tolist(), [0, 1, 2, 3])
        primary = np.array([2, 0, 1, 3])     # bin ranks: 0->1, 1->2, 2->0, 3->3
        secondary = np.array([0, 1, 3, 2])   # bin ranks: 0->0, 1->1, 2->3, 3->2
        # means: bin0 0.5, bin1 1.5, bin2 1.5, bin3 2.5; tie 1/2 broken by primary (2 first)
        self.assertEqual(ss.rank_fusion(primary, secondary).tolist(), [0, 2, 1, 3])

    def test_a_ranking_that_is_not_a_permutation_is_refused(self):
        with self.assertRaises(ValueError):
            ss.rank_fusion(np.array([0, 0, 1]), np.array([0, 1, 2]))


def paired_record(differences):
    differences = np.asarray(differences, dtype=float)
    return {"sections": len(differences), "mean_difference": float(differences.mean()),
            "positive_sections": int(np.sum(differences > 0))}


class DecisionRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from summarise_spatial_segmentation_s import EQUIVALENT, HELPS, MIXED, decide
        cls.decide = staticmethod(decide)
        cls.HELPS, cls.EQUIVALENT, cls.MIXED = HELPS, EQUIVALENT, MIXED

    def test_helps_needs_mean_and_six_of_eight_at_every_scale(self):
        helps = paired_record([0.05] * 6 + [-0.01] * 2)
        self.assertGreaterEqual(helps["mean_difference"], 0.02)
        self.assertEqual(self.decide({"bin": helps, "P1": helps}, 8), self.HELPS)
        five = paired_record([0.08] * 5 + [-0.01] * 3)
        self.assertEqual(self.decide({"bin": five}, 8), self.MIXED)
        # bin level meets the rule, P1 does not: GBM/CAC need both.
        self.assertEqual(self.decide({"bin": helps, "P1": paired_record([0.01] * 8)}, 8),
                         self.MIXED)
        self.assertEqual(self.decide({"bin": helps}, 8), self.HELPS)

    def test_equivalent_needs_every_scale_inside_the_margin(self):
        small = paired_record([0.019, -0.01] * 4)
        self.assertEqual(self.decide({"bin": small, "P1": small}, 8), self.EQUIVALENT)
        self.assertEqual(self.decide({"bin": small, "P1": paired_record([-0.03] * 8)}, 8),
                         self.MIXED)

    def test_boundaries_and_incomplete(self):
        exact = {"sections": 8, "mean_difference": 0.02, "positive_sections": 6}
        self.assertEqual(self.decide({"bin": exact}, 8), self.HELPS)
        self.assertEqual(self.decide({"bin": dict(exact, mean_difference=-0.02)}, 8), self.MIXED)
        self.assertEqual(self.decide({"bin": paired_record([0.05] * 7)}, 7),
                         "incomplete; no verdict (7/8 sections)")


def minimal_summary(section, difference, scales=("bin", "P1"), sigma=0.75, code="h"):
    """A Test S summary.json with only the fields the summariser reads."""
    values = {"posterior_abs_pcc_balanced": 0.5, "sa_posterior_abs_pcc_balanced": 0.5 + difference,
              "morans_i": 0.45, "rank_fusion_posterior_morans_i": 0.52}
    return {"status": "complete", "dataset": section, "K_bin": 100,
            "provenance": {"test_s_version": 1, "code": {"x": code},
                           "parameters": {"gmm_components": 2, "gmm_n_init": 20, "gmm_seed": 1,
                                          "radius": 1, "sigma": sigma, "adaptive": sigma == 0.75,
                                          "scales": list(scales), "chunk_size": 1024}},
            "mSCF1": {scale: dict(values) for scale in scales},
            "smoothed_gmm": {"empty_components": 0},
            "S2": {"c_segmentation": {"ari_smoothed_vs_production": 0.9,
                                      "production_vs_expert": {"balanced_accuracy": 0.8},
                                      "smoothed_vs_expert": {"balanced_accuracy": 0.85}}}}


class SummariserTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "S"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, collection, section, arm, summary):
        target = self.root / collection / f"{section}_seed1" / arm
        target.mkdir(parents=True, exist_ok=True)
        (target / "summary.json").write_text(json.dumps(summary))

    def summarise(self, check=True):
        from spatial_msipl.tests.test_rcc_pipeline import run
        return run("summarise_spatial_segmentation_s.py", "--root", self.root, "--output",
                   Path(self.tmp.name) / "out", check=check)

    def decisions(self):
        return json.loads((Path(self.tmp.name) / "out" / "decisions.json").read_text())

    def test_verdicts_per_collection_and_arm(self):
        from summarise_spatial_segmentation_s import SECTIONS
        for section in SECTIONS["GBM"]:
            self.write("GBM", section, "central_only", minimal_summary(section, 0.05))
            self.write("GBM", section, "uniform_mean", minimal_summary(section, 0.001))
        for section in SECTIONS["RCC"]:
            self.write("RCC", section, "central_only",
                       minimal_summary(section, -0.05, scales=("bin",)))
            if section != "RCC_UH0505_12":
                self.write("RCC", section, "uniform_mean",
                           minimal_summary(section, 0.05, scales=("bin",)))
        self.summarise()
        decisions = self.decisions()
        self.assertEqual(decisions["GBM/central_only"]["verdict"], "spatial segmentation helps")
        self.assertEqual(decisions["GBM/uniform_mean"]["verdict"], "equivalent")
        self.assertEqual(decisions["RCC/central_only"]["verdict"],
                         "mixed (does not meet the 'helps' rule)")
        self.assertEqual(decisions["RCC/uniform_mean"]["verdict"],
                         "incomplete; no verdict (7/8 sections)")
        self.assertEqual(decisions["RCC/central_only"]["scales"], ["bin"])
        self.assertAlmostEqual(
            decisions["GBM/central_only"]["S2b_fusion_minus_plain"]["P1"]["mean_difference"], 0.02)
        self.assertEqual(decisions["GBM/central_only"]["S2_status"], "descriptive; no verdict")

    def assert_refused(self, text):
        result = self.summarise(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(text, result.stderr)

    def test_rcc_with_p1_is_refused(self):
        self.write("RCC", "RCC_MH0204_33", "central_only", minimal_summary("RCC_MH0204_33", 0))
        self.assert_refused("needs ['bin']")

    def test_cac_without_p1_is_refused(self):
        self.write("CAC", "40TopL", "central_only", minimal_summary("40TopL", 0, scales=("bin",)))
        self.assert_refused("needs ['bin', 'P1']")

    def test_identity_or_other_smoothing_is_refused(self):
        self.write("GBM", "GBM12_1", "central_only", minimal_summary("GBM12_1", 0, sigma=1e-6))
        self.assert_refused("not the predeclared smoothing")

    def test_mixed_code_is_refused(self):
        self.write("GBM", "GBM12_1", "central_only", minimal_summary("GBM12_1", 0))
        self.write("GBM", "GBM12_2", "central_only", minimal_summary("GBM12_2", 0, code="other"))
        self.assert_refused("different code or settings")

    def test_unknown_section_and_folder_mismatch_are_refused(self):
        self.write("GBM", "40TopL", "central_only", minimal_summary("40TopL", 0))
        self.assert_refused("is not a GBM section")
        shutil.rmtree(self.root)
        self.write("GBM", "GBM12_1", "central_only", minimal_summary("GBM12_2", 0))
        self.assert_refused("not a complete Test S result")


@unittest.skipUnless(DEPENDENCIES, "h5py/sklearn/matplotlib not installed")
class SectionScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from spatial_msipl.tests.test_rcc_pipeline import build_section, run
        cls.run_script = staticmethod(run)
        cls.tmp = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.tmp.name)
        cls.input, cls.attribution, _, _, _ = build_section(root, "SYN", 2, seed=5)
        attribution_summary = cls.attribution / "summary.json"
        attribution_summary.write_text(json.dumps(
            {"status": "valid", "gmm": {"components": 2, "n_init": 1, "seed": 1}}))
        cls.partitions = root / "partitions"
        run("audit_peak_partitions.py", "--input", cls.input, "--output", cls.partitions,
            "--chunk-size", 64, "--allow-outside-slurm")
        audit = json.loads((cls.partitions / "summary.json").read_text())
        approval = root / "approval.json"
        approval.write_text(json.dumps({"status": "approved", "partitions": {"P1": {
            "parameters": audit["partitions"]["P1"]["parameters"],
            "sections": {"SYN": audit["partitions"]["P1"]["structure"]["sha256"]}}}}))
        k = 20
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

    def score_s(self, output, fair, *extra, attribution=None, check=True, partitions=True):
        arguments = ["--input", self.input, "--attribution-dir", attribution or self.attribution,
                     "--fair-scoring-summary", fair / "summary.json", "--output", output,
                     "--chunk-size", 64, "--allow-outside-slurm", *extra]
        if partitions:
            arguments += ["--partition-dir", self.partitions]
        return self.run_script("evaluate_spatial_segmentation_s.py", *arguments, check=check)


    def assert_refused(self, result, text):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(text, result.stderr)

    def test_identity_smoothing_reproduces_plain_posterior_exactly(self):
        output = self.root / "identity"
        self.score_s(output, self.fair_p1, "--identity-smoothing")
        summary = json.loads((output / "summary.json").read_text())
        for scale in ("bin", "P1"):
            values = summary["mSCF1"][scale]
            self.assertEqual(values["sa_posterior_abs_pcc_balanced"],
                             values["posterior_abs_pcc_balanced"])
        self.assertEqual(summary["S2"]["c_segmentation"]["ari_smoothed_vs_production"], 1.0)
        prefixes = np.load(output / "rankings_prefix.npz")
        self.assertTrue(np.array_equal(prefixes["sa_posterior_abs_pcc_balanced"],
                                       prefixes["posterior_abs_pcc_balanced"]))

    def test_production_smoothing_runs_reproduces_saved_scores_and_records_checks(self):
        output = self.root / "production"
        self.score_s(output, self.fair_p1)
        summary = json.loads((output / "summary.json").read_text())
        checks = summary["checks"]
        self.assertEqual(checks["production_refit_ari_to_saved"], 1.0)
        self.assertTrue(checks["neighbourhood_edges_equal_morans_i_edges"])
        self.assertEqual(set(checks["reproduced_mSCF1"]),
                         {"bin:posterior_abs_pcc_balanced", "bin:morans_i",
                          "P1:posterior_abs_pcc_balanced", "P1:morans_i"})
        self.assertEqual(summary["provenance"]["parameters"]["sigma"], 0.75)
        self.assertTrue(summary["provenance"]["parameters"]["adaptive"])
        self.assertEqual(set(summary["mSCF1"]), {"bin", "P1"})
        self.assertIn("balanced_accuracy", summary["S2"]["c_segmentation"]["smoothed_vs_expert"])
        # A second run with the same inputs is skipped, not recomputed.
        rerun = self.score_s(output, self.fair_p1)
        self.assertIn("skipped", rerun.stdout)

    def test_bin_only_summary_scores_bin_level_only(self):
        output = self.root / "bin_only"
        self.score_s(output, self.fair_bin, partitions=False)
        summary = json.loads((output / "summary.json").read_text())
        self.assertEqual(set(summary["mSCF1"]), {"bin"})
        self.assertIsNone(summary["peak_level_P1"])

    def test_partition_arguments_must_match_the_fair_summary(self):
        self.assert_refused(self.score_s(self.root / "r1", self.fair_p1, partitions=False,
                                        check=False), "--partition-dir is required")
        self.assert_refused(self.score_s(self.root / "r2", self.fair_bin, check=False),
                            "has no approved P1")

    def copy_attribution(self, name):
        target = self.root / name
        shutil.copytree(self.attribution, target)
        return target

    def test_changed_latent_is_refused_by_hash(self):
        attribution = self.copy_attribution("attr_latent")
        latent = np.load(attribution / "latent_mean.npy")
        np.save(attribution / "latent_mean.npy", latent + np.float32(1e-3))
        self.assert_refused(self.score_s(self.root / "r3", self.fair_p1, check=False,
                                        attribution=attribution), "latent_mean differs")

    def fair_copy(self, name, edit):
        target = self.root / name
        shutil.copytree(self.fair_p1, target)
        summary = json.loads((target / "summary.json").read_text())
        edit(summary)
        (target / "summary.json").write_text(json.dumps(summary))
        return target

    def test_refit_that_does_not_reproduce_the_saved_labels_is_refused(self):
        from spatial_msipl.provenance import file_record
        attribution = self.copy_attribution("attr_labels")
        saved = dict(np.load(attribution / "coordinates_and_gmm.npz"))
        saved["component"] = np.roll(saved["component"], 7)
        np.savez(attribution / "coordinates_and_gmm.npz", **saved)
        record = file_record(attribution / "coordinates_and_gmm.npz")

        def edit(summary):
            summary["provenance"]["source_artifacts"]["coordinates_and_gmm"] = record
        fair = self.fair_copy("fair_labels", edit)
        self.assert_refused(self.score_s(self.root / "r4", fair, check=False,
                                        attribution=attribution), "ARI")

    def test_saved_scores_that_do_not_reproduce_are_refused(self):
        def edit_bin(summary):
            summary["bin_level"]["morans_i"]["1.0"]["mSCF1"] += 1e-6
        self.assert_refused(self.score_s(self.root / "r5", self.fair_copy("fair_bin_edit", edit_bin),
                                        check=False), "morans_i: bin-level rescore")

        def edit_p1(summary):
            methods = summary["peak_level"]["P1"]["methods"]
            methods["posterior_abs_pcc_balanced"]["matched_K_peak"]["mSCF1"] += 1e-6
        self.assert_refused(self.score_s(self.root / "r6", self.fair_copy("fair_p1_edit", edit_p1),
                                        check=False), "posterior_abs_pcc_balanced: P1 rescore")

    def test_class_subset_summary_is_refused(self):
        fair = self.fair_copy("fair_subset", lambda s: s.update(class_subset={"classes": [0]}))
        self.assert_refused(self.score_s(self.root / "r7", fair, check=False), "class-subset")


if __name__ == "__main__":
    unittest.main()
