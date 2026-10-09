"""Tests for gate-(d) sampling and BIC helpers."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from spatial_msipl.gate_d_helpers import (
    GMM_ALIGNMENT_EXIT_CODE,
    SKLEARN_COMPONENT_ATTRIBUTES,
    GmmLabelAlignmentError,
    component_order,
    production_label_permutation,
    reorder_gmm_components,
    mark_distinct_arms,
    nested_attribution_samples,
    pixel_count_decision,
    production_disjoint_samples,
    select_gmm_k_by_bic,
)


class NestedSamplingTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(0)
        self.labels = rng.integers(0, 2, 600)
        self.seed = 1 + 700  # production sampling_seed + 700

    def test_n12_reproduces_production_exactly(self):
        production = production_disjoint_samples(self.labels, 12, 32, self.seed)
        nested = nested_attribution_samples(self.labels, 12, self.seed)
        for component in production:
            np.testing.assert_array_equal(
                nested[component]["attribution"], production[component]["attribution"])
            np.testing.assert_array_equal(
                nested[component]["faithfulness"], production[component]["faithfulness"])

    def test_larger_arms_are_nested_and_keep_faithfulness_fixed(self):
        production = production_disjoint_samples(self.labels, 12, 32, self.seed)
        arms = {n: nested_attribution_samples(self.labels, n, self.seed) for n in (12, 48, 192)}
        for component in production:
            a12 = set(arms[12][component]["attribution"].tolist())
            a48 = set(arms[48][component]["attribution"].tolist())
            a192 = set(arms[192][component]["attribution"].tolist())
            self.assertTrue(a12 < a48 < a192)
            self.assertEqual(len(a48), 48)
            self.assertEqual(len(a192), 192)
            faith = set(production[component]["faithfulness"].tolist())
            for n in (48, 192):
                self.assertEqual(set(arms[n][component]["faithfulness"].tolist()), faith)
                self.assertFalse(faith & set(arms[n][component]["attribution"].tolist()))

    def test_capping_records_actual_count_and_flags_non_distinct_arms(self):
        labels = np.array([0] * 100 + [1] * 300)
        arms = {n: nested_attribution_samples(labels, n, self.seed) for n in (12, 48, 192)}
        self.assertEqual(arms[192][0]["actual_attribution"], 12 + 100 - 44)
        self.assertTrue(arms[192][0]["capped"])
        self.assertEqual(arms[192][1]["actual_attribution"], 192)
        counts = {n: {c: arms[n][c]["actual_attribution"] for c in arms[n]} for n in arms}
        self.assertEqual(mark_distinct_arms(counts), {12: True, 48: True, 192: True})
        tiny = np.array([0] * 60 + [1] * 60)
        arms = {n: nested_attribution_samples(tiny, n, self.seed) for n in (12, 48, 192)}
        counts = {n: {c: arms[n][c]["actual_attribution"] for c in arms[n]} for n in arms}
        self.assertEqual(mark_distinct_arms(counts), {12: True, 48: True, 192: False})

    def test_too_few_pixels_is_an_error_as_in_production(self):
        with self.assertRaises(ValueError):
            nested_attribution_samples(np.array([0] * 43 + [1] * 100), 12, self.seed)


def three_blob_gmm(seed=0):
    from sklearn.mixture import GaussianMixture

    rng = np.random.default_rng(seed)
    data = np.vstack([rng.normal(centre, 0.3, (120 + 40 * i, 4))
                      for i, centre in enumerate((0.0, 4.0, 8.0))])
    return data, GaussianMixture(3, covariance_type="full", n_init=2,
                                 random_state=1).fit(data)


class GmmLabelAlignmentTests(unittest.TestCase):
    """Protocol 18 Section 6 amendment: relabel the refit onto production."""

    def test_swapped_labels_are_aligned_and_sampling_draws_production_pixels(self):
        rng = np.random.default_rng(3)
        production = rng.integers(0, 3, 900)
        swap = np.array([0, 2, 1])
        refit = swap[production]  # identical segmentation, components 1 and 2 renumbered
        permutation = production_label_permutation(refit, production, 3)
        self.assertEqual(permutation, (0, 2, 1))
        aligned = np.asarray(permutation)[refit]
        np.testing.assert_array_equal(aligned, production)
        seed = 1 + 700
        expected = production_disjoint_samples(production, 12, 32, seed)
        unaligned = nested_attribution_samples(refit, 12, seed)
        realigned = nested_attribution_samples(aligned, 12, seed)
        for component in expected:
            np.testing.assert_array_equal(realigned[component]["attribution"],
                                          expected[component]["attribution"])
            np.testing.assert_array_equal(realigned[component]["faithfulness"],
                                          expected[component]["faithfulness"])
        # Without alignment the renumbered components draw each other's permutations.
        self.assertFalse(np.array_equal(unaligned[1]["attribution"],
                                        expected[1]["attribution"]))

    def test_non_identical_assignment_has_no_permutation(self):
        production = np.repeat([0, 1, 2], 50)
        refit = np.array([0, 2, 1])[production]
        refit[0] = 1  # one pixel genuinely moved
        with self.assertRaises(GmmLabelAlignmentError):
            production_label_permutation(refit, production, 3)

    def test_component_count_mismatch_is_an_alignment_error(self):
        production = np.repeat([0, 1], 60)  # production K = 2
        refit_three = np.repeat([0, 1, 2], 40)
        with self.assertRaises(GmmLabelAlignmentError):
            production_label_permutation(refit_three, production, 3)
        with self.assertRaises(GmmLabelAlignmentError):
            production_label_permutation(production, np.repeat([0, 1, 2], 40), 2)
        # A K=3 refit that leaves one component empty must not "match" a K=2 production.
        with self.assertRaises(GmmLabelAlignmentError):
            production_label_permutation(production.copy(), production, 3)

    def test_identity_is_a_no_op(self):
        data, gmm = three_blob_gmm()
        labels = gmm.predict(data)
        before = {a: np.array(getattr(gmm, a)) for a in SKLEARN_COMPONENT_ATTRIBUTES}
        permutation = production_label_permutation(labels, labels, 3)
        self.assertEqual(permutation, (0, 1, 2))
        reorder_gmm_components(gmm, component_order(permutation))
        for attribute, value in before.items():
            np.testing.assert_array_equal(getattr(gmm, attribute), value)

    def test_permuted_parameters_reorder_posterior_columns_exactly(self):
        data, gmm = three_blob_gmm()
        posterior = gmm.predict_proba(data)
        order = np.array([2, 0, 1])
        reorder_gmm_components(gmm, order)
        reordered = gmm.predict_proba(data)
        self.assertLessEqual(float(np.max(np.abs(reordered - posterior[:, order]))), 1e-12)
        np.testing.assert_array_equal(gmm.predict(data), np.argmax(posterior[:, order], axis=1))


class IgScriptLabelAlignmentTests(unittest.TestCase):
    """align_gmm_to_production in the IG script: relabel, verify, or exit 5."""

    @classmethod
    def setUpClass(cls):
        try:
            import run_spatial_msipl_gmm_integrated_gradients as ig
        except ImportError as error:  # pragma: no cover - needs torch and scripts/
            raise unittest.SkipTest(f"IG script not importable: {error}")
        cls.ig = ig

    def production_dir(self, tmp, labels, assigned):
        path = Path(tmp)
        np.savez(path / "coordinates_and_gmm.npz", x=np.arange(len(labels)),
                 y=np.zeros(len(labels)), component=labels, assigned_posterior=assigned)
        return path

    def test_swapped_production_labels_are_aligned_with_matching_posterior(self):
        data, gmm = three_blob_gmm()
        posterior = gmm.predict_proba(data)
        swap = np.array([0, 2, 1])
        production = swap[gmm.predict(data)]
        assigned = posterior[np.arange(len(data)), gmm.predict(data)]
        with tempfile.TemporaryDirectory() as tmp:
            labels, aligned_posterior, record = self.ig.align_gmm_to_production(
                gmm, data, self.production_dir(tmp, production, assigned))
        np.testing.assert_array_equal(labels, production)
        self.assertFalse(record["identity"])
        self.assertEqual(record["permutation"], {"0": 0, "1": 2, "2": 1})
        self.assertLessEqual(record["max_posterior_diff"], 1e-12)
        self.assertIn("sklearn", record["refit_environment"])
        self.assertLessEqual(float(np.max(np.abs(aligned_posterior - posterior[:, swap]))),
                             1e-12)

    def test_identity_alignment_is_recorded_as_a_no_op(self):
        data, gmm = three_blob_gmm()
        labels = gmm.predict(data)
        assigned = gmm.predict_proba(data)[np.arange(len(data)), labels]
        means = np.array(gmm.means_)
        with tempfile.TemporaryDirectory() as tmp:
            aligned, _, record = self.ig.align_gmm_to_production(
                gmm, data, self.production_dir(tmp, labels, assigned))
        self.assertTrue(record["identity"])
        np.testing.assert_array_equal(aligned, labels)
        np.testing.assert_array_equal(gmm.means_, means)

    def test_component_count_mismatch_exits_with_alignment_code(self):
        data, gmm = three_blob_gmm()  # refit K = 3
        production = (gmm.predict(data) > 0).astype(np.int64)  # production K = 2
        assigned = np.ones(len(data))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as stop:
                self.ig.align_gmm_to_production(
                    gmm, data, self.production_dir(tmp, production, assigned))
        self.assertEqual(stop.exception.code, GMM_ALIGNMENT_EXIT_CODE)

    def test_alignment_records_the_production_reference_hash(self):
        import hashlib
        data, gmm = three_blob_gmm()
        labels = gmm.predict(data)
        assigned = gmm.predict_proba(data)[np.arange(len(data)), labels]
        with tempfile.TemporaryDirectory() as tmp:
            folder = self.production_dir(tmp, labels, assigned)
            expected = hashlib.sha256((folder / "coordinates_and_gmm.npz").read_bytes()).hexdigest()
            _, _, record = self.ig.align_gmm_to_production(gmm, data, folder)
        self.assertEqual(record["production_reference"]["sha256"], expected)

    def test_non_identical_assignment_exits_with_alignment_code(self):
        data, gmm = three_blob_gmm()
        labels = gmm.predict(data)
        production = labels.copy()
        production[0] = (production[0] + 1) % 3
        assigned = gmm.predict_proba(data)[np.arange(len(data)), labels]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as stop:
                self.ig.align_gmm_to_production(
                    gmm, data, self.production_dir(tmp, production, assigned))
        self.assertEqual(stop.exception.code, GMM_ALIGNMENT_EXIT_CODE)


class PixelCountDecisionTests(unittest.TestCase):
    """The predeclared rule: >= +0.02 on both development sections, per arm."""

    def decide(self, gbm, cac, distinct=(True, True), arm="uniform_mean"):
        changes = {arm: {"GBM108_positive": {48: gbm, 192: gbm},
                         "40TopL": {48: cac, 192: cac}}}
        flags = {arm: {"GBM108_positive": {48: distinct[0], 192: distinct[0]},
                       "40TopL": {48: distinct[1], 192: distinct[1]}}}
        return pixel_count_decision(changes, flags)[arm]["48"]["verdict"]

    def test_gain_on_both_sections_triggers_rerun(self):
        self.assertIn("triggers", self.decide(0.03, 0.02))

    def test_gain_on_one_section_only_keeps_production(self):
        self.assertEqual(self.decide(0.05, 0.019), "production n=12 stands")

    def test_large_decrease_keeps_production(self):
        self.assertEqual(self.decide(-0.10, -0.08), "production n=12 stands")

    def test_non_distinct_arm_gives_no_verdict(self):
        self.assertIn("not distinct", self.decide(0.05, 0.05, distinct=(True, False)))

    def test_missing_section_or_arm_gives_no_verdict(self):
        changes = {"uniform_mean": {"GBM108_positive": {48: 0.05, 192: 0.05}}}
        flags = {"uniform_mean": {"GBM108_positive": {48: True, 192: True}}}
        decisions = pixel_count_decision(changes, flags)
        self.assertEqual(decisions["uniform_mean"]["48"]["verdict"], "incomplete; no verdict")
        self.assertEqual(decisions["central_only"]["192"]["verdict"], "incomplete; no verdict")

    def test_rule_is_applied_per_arm(self):
        changes = {"central_only": {"GBM108_positive": {48: 0.05, 192: 0.0},
                                    "40TopL": {48: 0.05, 192: 0.0}},
                   "uniform_mean": {"GBM108_positive": {48: 0.0, 192: 0.0},
                                    "40TopL": {48: 0.0, 192: 0.0}}}
        flags = {arm: {s: {48: True, 192: True} for s in ("GBM108_positive", "40TopL")}
                 for arm in changes}
        decisions = pixel_count_decision(changes, flags)
        self.assertIn("triggers", decisions["central_only"]["48"]["verdict"])
        self.assertEqual(decisions["central_only"]["192"]["verdict"], "production n=12 stands")
        self.assertEqual(decisions["uniform_mean"]["48"]["verdict"], "production n=12 stands")


class PixelCountSummaryScriptTests(unittest.TestCase):
    def run_summary(self, root, output):
        scripts = Path(__file__).resolve().parents[3] / "scripts"
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join(
            [str(scripts.parent / "src"), environment.get("PYTHONPATH", "")])
        return subprocess.run(
            [sys.executable, str(scripts / "summarise_gate_d_pixel_counts.py"),
             "--root", str(root), "--output", str(output)],
            env=environment, capture_output=True, text=True)

    def write(self, root, section, arm, status="complete", change=0.0, code="c0de"):
        path = root / f"{section}_seed1" / arm / "evaluation" / "summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"status": status,
                  "provenance": {"evaluation_version": 1, "protocol": "p",
                                 "parameters": {"pixel_counts": [12, 48, 192]},
                                 "code": {"evaluate_gate_d_pixel_counts.py": code}}}
        if status == "complete":
            record["change_vs_saved_n12_at_K_bin"] = {"12": 0.0, "48": change, "192": change}
            record["distinct_from_next_smaller"] = {"12": True, "48": True, "192": True}
        path.write_text(json.dumps(record))

    def test_failed_reproduction_gives_no_verdict_for_that_arm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for section in ("GBM108_positive", "40TopL"):
                self.write(root, section, "central_only", change=0.05)
            self.write(root, "GBM108_positive", "uniform_mean", change=0.05)
            self.write(root, "40TopL", "uniform_mean", status="reproduction_failed")
            result = self.run_summary(root, root / "out")
            self.assertEqual(result.returncode, 0, result.stderr)
            decisions = json.loads((root / "out" / "decisions.json").read_text())
            self.assertIn("triggers", decisions["central_only"]["48"]["verdict"])
            self.assertEqual(decisions["uniform_mean"]["48"]["verdict"],
                             "incomplete; no verdict")
            self.assertEqual(decisions["_evaluation_status"]["uniform_mean"]["40TopL"],
                             "reproduction_failed")

    def test_mixed_code_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root, "GBM108_positive", "central_only")
            self.write(root, "40TopL", "central_only", code="other")
            result = self.run_summary(root, root / "out")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to mix", result.stderr)


class BicTests(unittest.TestCase):
    def test_single_blob_selects_k1_as_primary_result(self):
        latent = np.random.default_rng(1).normal(size=(400, 5))
        result = select_gmm_k_by_bic(latent, seed=1, n_init=2, candidates=(1, 2, 3))
        self.assertEqual(result["selected_k"], 1)
        self.assertIn("no supported multi-cluster", result["primary_result"])
        self.assertIn("not BIC-selected", result["sensitivity_label"])

    def test_two_separated_blobs_select_k2(self):
        rng = np.random.default_rng(2)
        latent = np.vstack((rng.normal(0, 1, (200, 5)), rng.normal(6, 1, (200, 5))))
        result = select_gmm_k_by_bic(latent, seed=1, n_init=2, candidates=(1, 2, 3))
        self.assertEqual(result["selected_k"], 2)
        self.assertNotIn("sensitivity_k_ge_2", result)


if __name__ == "__main__":
    unittest.main()
