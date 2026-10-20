"""Tests for protocol 18 Section 6.6 statistics (hand-checked toy cases)."""

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

try:
    import scipy  # noqa: F401
except ImportError:  # pragma: no cover - the uv environment and the cluster have scipy
    scipy = None
try:
    import statsmodels  # noqa: F401
except ImportError:  # pragma: no cover
    statsmodels = None

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

if scipy is not None:
    from spatial_msipl import paired_statistics as ps
    import compute_statistics_6_6 as stats66


@unittest.skipIf(scipy is None, "scipy is not installed")
class PairedStatistics(unittest.TestCase):
    def test_null_counts_for_three_ranks(self):
        # Subsets of {1,2,3}: sums 0,1,2,3,3,4,5,6.
        self.assertEqual(list(ps.signed_rank_null_counts(3)), [1, 1, 1, 2, 1, 1, 1])

    def test_all_positive_n8(self):
        result = ps.paired_summary(np.arange(1.0, 9.0))
        self.assertEqual(result["statistic"], 0.0)
        self.assertAlmostEqual(result["p_exact"], 2 / 256, places=12)
        self.assertAlmostEqual(result["min_attainable_p"], 2 / 256, places=12)
        # 36 Walsh averages; the 4th smallest is 2 and the 4th largest is 7
        # (P(T+ <= 3) = 5/256 <= 0.025 < P(T+ <= 4) = 7/256).
        self.assertEqual(result["hl_estimate"], 4.5)
        self.assertEqual((result["hl_ci_low"], result["hl_ci_high"]), (2.0, 7.0))
        self.assertAlmostEqual(result["hl_ci_coverage"], 1 - 10 / 256, places=12)
        self.assertTrue(result["ci_95_attainable"])
        self.assertEqual(result["rank_biserial"], 1.0)
        self.assertEqual((result["n_positive"], result["n_negative"], result["n_zero"]),
                         (8, 0, 0))

    def test_one_negative_n8(self):
        result = ps.paired_summary([-1.0, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(result["statistic"], 1.0)
        self.assertAlmostEqual(result["p_exact"], 4 / 256, places=12)
        self.assertAlmostEqual(result["rank_biserial"], (35 - 1) / 36, places=12)

    def test_zero_is_dropped_from_the_exact_test_but_counted(self):
        result = ps.paired_summary([0.0, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual((result["n_zero"], result["n_nonzero"]), (1, 7))
        self.assertAlmostEqual(result["p_exact"], 2 / 128, places=12)
        self.assertEqual(result["n"], 8)

    def test_all_zero_gives_no_test(self):
        result = ps.wilcoxon_exact([0.0, 0.0, 0.0])
        self.assertIsNone(result["p_exact"])

    def test_ci_n7_and_not_attainable_at_n4(self):
        n7 = ps.hodges_lehmann(np.arange(1.0, 8.0))
        # P(T+ <= 2) = 3/128 <= 0.025 < P(T+ <= 3) = 5/128: 3rd smallest / largest
        # Walsh averages (1, 1.5, 2, 2, ... and ..., 6, 6, 6.5, 7).
        self.assertEqual((n7["hl_ci_low"], n7["hl_ci_high"]), (2.0, 6.0))
        self.assertAlmostEqual(n7["hl_ci_coverage"], 1 - 6 / 128, places=12)
        n4 = ps.hodges_lehmann([1.0, 2.0, 3.0, 4.0])
        self.assertFalse(n4["ci_95_attainable"])
        self.assertEqual((n4["hl_ci_low"], n4["hl_ci_high"]), (1.0, 4.0))
        self.assertAlmostEqual(n4["hl_ci_coverage"], 0.875, places=12)

    def test_rank_biserial_uses_mid_ranks(self):
        # |d| ranks 1.5, 1.5, 3: T+ = 4.5, T- = 1.5.
        self.assertAlmostEqual(ps.rank_biserial([1.0, -1.0, 2.0]), 0.5, places=12)

    def test_holm_hand_checked(self):
        adjusted = ps.holm([0.01, 0.04, 0.03, 0.005])
        np.testing.assert_allclose(adjusted, [0.03, 0.06, 0.06, 0.02], rtol=0, atol=1e-12)
        self.assertEqual(ps.holm([None, 0.02, 0.5])[0], None)
        np.testing.assert_allclose(ps.holm([None, 0.02, 0.5])[1:], [0.04, 0.5], atol=1e-12)


@unittest.skipIf(scipy is None, "scipy is not installed")
class FamilyAndGuards(unittest.TestCase):
    def test_family_is_the_predeclared_38_rows(self):
        rows = stats66.family_rows()
        self.assertEqual([r["row"] for r in rows], list(range(1, 39)))
        sizes = {name: sum(stats66.family_of(r["row"]) == name for r in rows)
                 for name in stats66.FAMILIES}
        self.assertEqual(list(sizes.values()), [6, 4, 17, 9, 2])
        self.assertEqual(rows[0]["unit"], "seed mean 1-3")
        self.assertEqual(rows[33]["unit"], "seed 1")  # Test V: unit of its label (Q4)
        self.assertTrue(all(r["scales"] == ("bin",) for r in rows
                            if r["collection"] == "RCC" or r["row"] in range(7, 11)))

    def test_check_saved_refuses_a_mismatch_and_accepts_reordering(self):
        stats66.check_saved([0.1, -0.2], [-0.2, 0.1], "ok")
        with self.assertRaises(ValueError):
            stats66.check_saved([0.1, -0.2], [0.1, -0.2 + 1e-9], "bad")
        with self.assertRaises(ValueError):
            stats66.check_saved([0.1], [0.1, 0.2], "bad length")

    def test_pdx_line_averages_available_sections(self):
        names, values, counts = stats66.pdx_line(
            ["GBM108_negative", "GBM108_positive", "GBM12_1", "GBM22_2", "GBM39_1"],
            [0.1, 0.3, 0.5, 0.2, 0.4])
        self.assertEqual(names, ["GBM12", "GBM22", "GBM39", "GBM108"])
        np.testing.assert_allclose(values, [0.5, 0.2, 0.4, 0.2])
        self.assertEqual(counts, [1, 1, 1, 2])

    def test_existing_output_is_refused_with_exit_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "statistics_6_6"
            out.mkdir()
            self.assertEqual(stats66.run(Path(tmp), out, mixed=False), 3)


@unittest.skipIf(scipy is None or statsmodels is None, "statsmodels is not installed")
class MixedModel(unittest.TestCase):
    def test_crossed_model_recovers_a_known_method_effect(self):
        rng = np.random.default_rng(0)
        section_effect = rng.normal(0, 0.1, 8)
        seed_effect = rng.normal(0, 0.02, 3)
        rows = []
        for s in range(8):
            for seed in range(3):
                for first in (0, 1):
                    rows.append({"section": f"s{s}", "seed": seed, "is_first": first,
                                 "score": 0.5 + section_effect[s] + seed_effect[seed]
                                 - 0.2 * first + rng.normal(0, 0.01)})
        result = stats66.fit_mixed(rows, crossed=True)
        # Balanced design: the method effect equals the mean paired difference.
        paired = np.mean([b["score"] - a["score"] for a, b in zip(rows[::2], rows[1::2])])
        self.assertAlmostEqual(result["estimate"], paired, places=6)
        self.assertAlmostEqual(result["estimate"], -0.2, delta=0.02)
        self.assertLess(result["ci_low"], result["estimate"])
        self.assertGreater(result["ci_high"], result["estimate"])
        self.assertEqual(result["n_sections"], 8)
        self.assertEqual(result["status"], "converged")

    def test_not_converged_fit_reports_no_estimate(self):
        from unittest import mock
        import statsmodels.regression.mixed_linear_model as mlm

        rows = [{"section": f"s{s}", "seed": seed, "is_first": first,
                 "score": 0.5 + 0.01 * s - 0.1 * first + 0.001 * seed}
                for s in range(4) for seed in range(3) for first in (0, 1)]
        original = mlm.MixedLM.fit

        def unconverged(self, *args, **kwargs):
            result = original(self, *args, **kwargs)
            result.converged = False
            return result

        with mock.patch.object(mlm.MixedLM, "fit", unconverged):
            result = stats66.fit_mixed(rows, crossed=False)
        self.assertEqual(result["status"], "not converged")
        self.assertNotIn("estimate", result)
        self.assertNotIn("ci_low", result)


if __name__ == "__main__":
    unittest.main()
