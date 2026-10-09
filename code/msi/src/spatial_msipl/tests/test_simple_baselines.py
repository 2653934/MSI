"""Tests for label-free saved-artifact baselines."""

import unittest

import numpy as np

from spatial_msipl.evaluation import morans_i
from spatial_msipl.peak_selection import balanced_round_robin_rankings
from spatial_msipl.preprocessing import build_moore_neighbour_slots
from spatial_msipl.simple_baselines import (
    budgets,
    check_posterior_against_saved,
    gmm_posterior_numpy,
    moore_edges,
    morans_i_per_feature,
    nan_to_lowest,
    one_hot_maps,
    pearson_features_vs_maps,
    posterior_pcc_rankings,
    production_ig_ranking,
    random_rankings,
    rank_descending,
    supervised_oracle_ranking,
    tie_permuted_positions,
)


class PosteriorTests(unittest.TestCase):
    def test_numpy_posterior_matches_sklearn(self):
        from sklearn.mixture import GaussianMixture
        from sklearn.preprocessing import StandardScaler

        rng = np.random.default_rng(3)
        latent = np.vstack((rng.normal(0, 1, (80, 5)), rng.normal(3, 0.5, (60, 5))))
        scaler = StandardScaler().fit(latent)
        gmm = GaussianMixture(2, covariance_type="full", random_state=1).fit(
            scaler.transform(latent))
        expected = gmm.predict_proba(scaler.transform(latent))
        parameters = {
            "scaler_mean": scaler.mean_, "scaler_scale": scaler.scale_,
            "mixture_weights": gmm.weights_, "component_means": gmm.means_,
            "precision_cholesky": gmm.precisions_cholesky_,
        }
        posterior = gmm_posterior_numpy(latent, **parameters)
        np.testing.assert_allclose(posterior, expected, atol=1e-10)
        labels = np.argmax(expected, axis=1)
        check_posterior_against_saved(posterior, labels, expected[np.arange(140), labels])
        with self.assertRaises(ValueError):
            check_posterior_against_saved(posterior, 1 - labels, expected.max(axis=1))


class CorrelationAndMoranTests(unittest.TestCase):
    def test_pearson_matches_numpy_corrcoef_and_constant_gives_zero(self):
        rng = np.random.default_rng(1)
        features = rng.random((50, 4))
        features[:, 3] = 2.0
        maps = rng.random((50, 2))
        result = pearson_features_vs_maps(features, maps)
        for i in range(3):
            for j in range(2):
                self.assertAlmostEqual(
                    result[i, j], np.corrcoef(features[:, i], maps[:, j])[0, 1])
        np.testing.assert_array_equal(result[3], [0.0, 0.0])

    def test_morans_i_matches_existing_definition(self):
        x, y = np.meshgrid(np.arange(1, 7), np.arange(1, 6))
        x, y = x.reshape(-1), y.reshape(-1)
        keep = np.ones(len(x), dtype=bool)
        keep[[3, 17]] = False  # holes, as in partial coverage
        x, y = x[keep], y[keep]
        rng = np.random.default_rng(2)
        features = np.column_stack((x + 0.1 * rng.random(len(x)), rng.random(len(x)),
                                    np.ones(len(x))))
        sources, targets = moore_edges(x, y)
        values = morans_i_per_feature(features, sources, targets)
        slots = build_moore_neighbour_slots(x, y)
        for column in range(2):
            self.assertAlmostEqual(values[column], morans_i(features[:, column], slots))
        self.assertTrue(np.isnan(values[2]))
        self.assertEqual(rank_descending(nan_to_lowest(values))[-1], 2)


class TieHandlingTests(unittest.TestCase):
    def test_rank_descending_breaks_exact_ties_by_index_on_any_platform(self):
        scores = np.array([0.5, 0.9, 0.9, 0.1, 0.9, -np.inf])
        np.testing.assert_array_equal(rank_descending(scores), [1, 2, 4, 0, 3, 5])
        float32_tie = np.array([0.77442014, 0.1, 0.77442014], dtype=np.float32)
        np.testing.assert_array_equal(rank_descending(float32_tie), [0, 2, 1])

    def test_reproduction_accepts_only_exact_tie_permutations(self):
        # Mirrors the GBM22_2 centre-only L2 case: two bins with identical
        # float32 scores in swapped order in the historical list.
        scores = np.array([0.9, 0.7744, 0.7744, 0.5, 0.2])
        score_at = lambda position, b: scores[b]
        saved = np.array([0, 2, 1, 3])
        self.assertEqual(tie_permuted_positions(rank_descending(scores)[:4], saved,
                                                score_at), 2)
        self.assertEqual(tie_permuted_positions(saved, saved, score_at), 0)
        with self.assertRaises(ValueError):  # non-tied swap
            tie_permuted_positions(np.array([0, 3, 1, 2]), saved, score_at)
        with self.assertRaises(ValueError):  # different bins selected
            tie_permuted_positions(np.array([0, 1, 2, 4]), saved, score_at)
        with self.assertRaises(ValueError):
            tie_permuted_positions(np.array([0, 1, 2]), saved, score_at)


class OracleTests(unittest.TestCase):
    def test_three_class_oracle_uses_signed_pcc_like_the_reference(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
        from evaluate_msipl_massnet_peaks import true_indices_at_threshold

        # Bin 0: strongly NEGATIVE with class 2 only -> not reference-positive.
        # Bin 1: moderately positive with class 1 -> reference-positive at 0.4.
        correlations = {
            0: np.array([0.05, 0.10, 0.70, 0.20, -0.30, 0.01]),
            1: np.array([0.10, 0.55, -0.20, 0.15, 0.48, 0.38]),
            2: np.array([-0.95, -0.30, -0.40, 0.18, -0.10, 0.03]),
        }
        ranking = supervised_oracle_ranking(correlations)
        reference = set().union(*(true_indices_at_threshold(correlations[c], 0.4)
                                  for c in correlations))
        self.assertEqual(reference, {1, 2, 4})
        self.assertEqual(set(ranking[:len(reference)].tolist()), reference)
        absolute = np.argsort(np.max(np.abs(np.stack(list(correlations.values()))), 0))[::-1]
        self.assertEqual(absolute[0], 0)  # an |PCC| oracle would wrongly rank bin 0 first
        self.assertNotIn(0, ranking[:len(reference)].tolist())

    def test_two_class_signed_and_absolute_oracles_coincide(self):
        r = np.array([0.6, -0.7, 0.1, -0.2])
        signed = supervised_oracle_ranking({0: r, 1: -r})
        np.testing.assert_array_equal(signed, rank_descending(np.abs(r)))


class RankingTests(unittest.TestCase):
    def test_production_ig_ranking_matches_round_robin(self):
        rng = np.random.default_rng(4)
        scores = {0: rng.random(30), 1: rng.random(30)}
        attributions = {f"component_{c}_combined_absolute_mean": s for c, s in scores.items()}
        attributions["first_layer_combined_l2"] = rng.random(30)
        expected, _ = balanced_round_robin_rankings(
            {c: np.argsort(s)[::-1].copy() for c, s in scores.items()}, 30)
        np.testing.assert_array_equal(production_ig_ranking(attributions), expected)

    def test_posterior_rankings_are_permutations_and_balanced_for_two_components(self):
        rng = np.random.default_rng(5)
        pcc = rng.uniform(-1, 1, (40, 2))
        pcc[:, 1] = -pcc[:, 0]  # K=2: p1 = 1 - p0
        hard = rng.uniform(-1, 1, (40, 2))
        rankings = posterior_pcc_rankings(pcc, hard)
        for ranking in rankings.values():
            np.testing.assert_array_equal(np.sort(ranking), np.arange(40))
        # With identical |PCC| per component the balanced ranking is the |PCC| order.
        np.testing.assert_array_equal(
            rankings["posterior_abs_pcc_balanced"], rank_descending(np.abs(pcc[:, 0])))
        # Signed: component 0 contributes its most positive markers first.
        self.assertEqual(rankings["posterior_signed_pcc_balanced"][0], np.argmax(pcc[:, 0]))

    def test_one_hot_random_and_budgets(self):
        np.testing.assert_array_equal(one_hot_maps([1, 0], 2), [[0, 1], [1, 0]])
        draws = random_rankings(10, draws=3, seed=7)
        self.assertEqual(len(draws), 3)
        np.testing.assert_array_equal(draws[0], random_rankings(10, 1, 7)[0])
        self.assertEqual(budgets(584, 85062),
                         {"0.5": 292, "0.75": 438, "1.0": 584, "1.5": 876, "2.0": 1168})
        self.assertNotIn("2.0", budgets(600, 1000))


if __name__ == "__main__":
    unittest.main()
