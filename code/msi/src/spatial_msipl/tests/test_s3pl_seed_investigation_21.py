"""Investigation 21 Part A summariser (protocol 18 Section 6.7) on toy data."""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

import summarise_s3pl_seed_investigation_21 as inv

try:
    import statsmodels  # noqa: F401
    HAVE_STATSMODELS = True
except ImportError:
    HAVE_STATSMODELS = False


def write_run(root, collection, section, seed, score, loss, peaks):
    log, results = inv.preliminary_locations(collection, section, seed)
    (root / log).parent.mkdir(parents=True, exist_ok=True)
    (root / results).mkdir(parents=True, exist_ok=True)
    (root / log).write_text(json.dumps({"n_epochs": 2, "train_history": [0.5, loss],
                                        "random_seed": seed}))
    mixed = {"0.3": score + 0.03, "0.4": score + 0.01, "0.5": score - 0.01, "0.6": score - 0.03}
    (root / results / "metrics.json").write_text(json.dumps({
        "dataset": section, "mixed_f1": mixed, "mSCF1": round(score, 3),
        "number_picked_peaks": len(peaks), "normalization": "reference_spatial_max"}))
    (root / results / f"picked_peaks_{section}.csv").write_text("0\n" + "\n".join(peaks) + "\n")


def build_tree(root, scores=None):
    rng = np.random.default_rng(0)
    for collection, names in inv.SECTIONS.items():
        for i, section in enumerate(names):
            for seed in (1, 2, 3):
                score = scores[(collection, section, seed)] if scores else 0.1 * (i % 4) + 0.01 * seed
                peaks = [f"{100 + j}.{seed if j < 2 else 0}" for j in range(6)]
                write_run(root, collection, section, seed, score, 0.02 + 0.001 * rng.random(), peaks)


class PrimitiveTests(unittest.TestCase):
    def test_jaccard(self):
        self.assertEqual(inv.jaccard({"a", "b"}, {"b", "c"}), 1 / 3)
        self.assertEqual(inv.jaccard({"a"}, {"a"}), 1.0)

    def test_largest_gap(self):
        gap, split = inv.largest_gap([0.44, 0.03, 0.08])
        self.assertAlmostEqual(gap, 0.36)
        self.assertEqual(split, "2 below / 1 above")

    def test_anova_known_components(self):
        # Additive section + seed effects with no residual: residual 0, and the
        # moment estimates equal the sample variances of the effects.
        rows = np.array([0.0, 1.0, 3.0])[:, None]
        cols = np.array([0.0, 0.5])[None, :]
        out = inv.anova_components(rows + cols)
        self.assertAlmostEqual(out["residual"], 0.0)
        self.assertAlmostEqual(out["section"], np.var([0, 1, 3], ddof=1))
        self.assertAlmostEqual(out["seed"], np.var([0, 0.5], ddof=1))

    def test_shares_truncate_negative_moments(self):
        self.assertEqual(inv.shares({"a": -1.0, "b": 1.0, "c": 3.0}),
                         {"a": 0.0, "b": 0.25, "c": 0.75})

    def test_peaks_header_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.csv"
            path.write_text("1\n2\n")
            with self.assertRaises(ValueError):
                inv.read_peaks(path)
            path.write_text("0\n2\n2\n")
            with self.assertRaises(ValueError):
                inv.read_peaks(path)


class TreeTests(unittest.TestCase):
    def test_summary_on_toy_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_tree(root)
            runs, sections, pairs, variance, collections, files = inv.summarise(root, "preliminary", mixed=False)
            self.assertEqual(len(runs), 48)
            self.assertEqual(len(sections), 16)
            self.assertEqual(len(pairs), 48)
            # Peaks 100.s and 101.s differ between seeds, 102.0-105.0 are shared: 4 of 8.
            self.assertTrue(all(p["jaccard"] == 0.5 for p in pairs))
            first = sections[0]
            self.assertAlmostEqual(first["mean"], 0.02)
            self.assertAlmostEqual(first["sd"], 0.01)
            self.assertEqual(first["highest_mscf1_seed"], 3)
            # Unrounded mSCF1 is the mixed_f1 mean, not the rounded saved value.
            self.assertAlmostEqual(runs[0]["mscf1"], 0.01)
            self.assertEqual(collections["GBM"]["seeds"], [1, 2, 3])
            self.assertIn("controlled", collections["GBM"]["seed_mode"])
            self.assertIn("released", collections["CAC"]["seed_mode"])
            self.assertAlmostEqual(variance[0]["anova_var_residual"], 0.0)

    def test_rounding_mismatch_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_tree(root)
            _, results = inv.preliminary_locations("CAC", "40TopL", 2)
            metrics = json.loads((root / results / "metrics.json").read_text())
            metrics["mSCF1"] = 0.999
            (root / results / "metrics.json").write_text(json.dumps(metrics))
            with self.assertRaises(ValueError):
                inv.summarise(root, "preliminary", mixed=False)

    def test_existing_output_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_tree(root)
            out = root / "out"
            out.mkdir()
            self.assertEqual(inv.run(root, out, "preliminary", mixed=False, figure=False), 3)
            self.assertEqual(list(out.iterdir()), [])

    def test_run_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_tree(root)
            out = root / "out"
            self.assertEqual(inv.run(root, out, "preliminary", mixed=False, figure=False), 0)
            summary = json.loads((out / "summary.json").read_text())
            self.assertEqual(summary["status"], "preliminary")
            self.assertEqual(len(summary["provenance"]["inputs"]), 48 * 3)
            for name in ("runs.csv", "sections.csv", "jaccard_pairs.csv", "variance.csv"):
                self.assertTrue((out / name).exists())


@unittest.skipUnless(HAVE_STATSMODELS, "statsmodels not installed")
class MixedModelTests(unittest.TestCase):
    @staticmethod
    def rows(seed):
        rng = np.random.default_rng(seed)
        section_effects = rng.normal(0, 0.2, 8)
        return [{"section": f"s{i}", "seed": k,
                 "score": section_effects[i] + rng.normal(0, 0.02) + 0.01 * k}
                for i in range(8) for k in (1, 2, 3)]

    def test_crossed_fit_recovers_section_variance(self):
        fit = inv.fit_crossed(self.rows(5))
        self.assertEqual(fit["status"], "converged")
        self.assertGreater(fit["shares"]["section"], 0.9)
        self.assertAlmostEqual(sum(fit["shares"].values()), 1.0)

    def test_non_converged_fit_reports_no_components(self):
        fit = inv.fit_crossed(self.rows(3))
        self.assertEqual(fit["status"], "not converged")
        self.assertNotIn("components", fit)


if __name__ == "__main__":
    unittest.main()
