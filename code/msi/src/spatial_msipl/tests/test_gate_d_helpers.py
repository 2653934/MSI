"""Tests for gate-(d) sampling and BIC helpers."""

import unittest

import numpy as np

from spatial_msipl.gate_d_helpers import (
    mark_distinct_arms,
    nested_attribution_samples,
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
