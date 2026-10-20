"""Investigation 21 Parts B and D summariser (protocol 18 Section 6.7) on toy data."""

import json
import math
import tempfile
import unittest
from itertools import combinations
from pathlib import Path

import numpy as np

import summarise_s3pl_investigation_21_bd as bd
import summarise_s3pl_seed_investigation_21 as inv
from spatial_msipl.tests.test_s3pl_seed_investigation_21 import write_run

COUNTS = bd.native_counts()


def peaks_for(section, seed):
    return [f"{100 + j}.{seed % 2}" for j in range(COUNTS[section])]


def build(root, collection, seeds, score, locate=inv.released_locations, normalization=None):
    for section in inv.SECTIONS[collection]:
        for seed in seeds:
            write_run(root, collection, section, seed, score(section, seed), 0.02,
                      peaks_for(section, seed), locate=locate, controlled=False,
                      normalization=normalization)


class PrimitiveTests(unittest.TestCase):
    def test_expected_max_matches_enumeration(self):
        values = [0.03, 0.44, 0.08, 0.45, 0.02, 0.46, 0.11, 0.09, 0.29, 0.06]
        for k in range(1, 11):
            brute = np.mean([max(c) for c in combinations(values, k)])
            self.assertAlmostEqual(bd.expected_max(values, k), brute)
        self.assertAlmostEqual(bd.expected_max(values, 1), np.mean(values))
        self.assertEqual(bd.expected_max(values, 10), max(values))

    def test_percentile_counts_ties_half(self):
        self.assertEqual(bd.percentile_of(0.5, [0.1, 0.5, 0.6, 0.7]), 37.5)
        self.assertEqual(bd.percentile_of(0.9, [0.1, 0.5]), 100.0)

    def test_published_means_match_table_3(self):
        for collection, values in bd.PUBLISHED.items():
            self.assertEqual(round(float(np.mean(list(values.values()))), 3), bd.PUBLISHED_MEAN[collection])

    def test_native_counts_read_from_data_configs(self):
        self.assertEqual(COUNTS["GBM12_2"], 981)
        self.assertEqual(COUNTS["520TopL"], 257)

    def test_released_locations(self):
        log, res = inv.released_locations("GBM", "GBM12_2", 1)
        self.assertEqual(str(log).replace("\\", "/"),
                         "logs/s3pl/GBM12_2_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_3.json")
        log, _ = inv.released_locations("GBM", "GBM108_positive", 3)
        self.assertIn("s3pl_massnet/GBM108_positive_p3_reference_spatial_max_seed3", str(log).replace("\\", "/"))
        log, _ = inv.released_locations("GBM", "GBM12_2", 3)
        self.assertIn("s3pl_investigation_21/released/GBM/seed3", str(log).replace("\\", "/"))
        log, _ = inv.released_locations("CAC", "40TopL", 2)
        self.assertIn("s3pl_cac_seeds/seed2_released", str(log).replace("\\", "/"))
        log, _ = inv.paper_tic_locations("GBM", "GBM12_2", 1)
        self.assertIn("GBM12_2_p3_paper_tic_seed1", str(log).replace("\\", "/"))
        self.assertTrue(str(log).endswith("_paper_tic.json"))


class PartBTests(unittest.TestCase):
    def test_labels_and_curve(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Every section: 9 seeds at 0.30 and one seed at 0.70. Seed-level collection
            # means are 0.30 (seeds 1-9) and 0.70 (seed 10); E[max over k] = 0.30 + 0.4 k/10.
            build(root, "GBM", bd.B_SEEDS, lambda s, seed: 0.70 if seed == 10 else 0.30)
            summary, sections, _ = bd.part_b(root, "GBM")
            self.assertEqual(summary["consistency_label"], "inside our seed distribution")
            curve = summary["best_of_k_expected_mean"]
            self.assertAlmostEqual(curve["1"], 0.34)
            self.assertAlmostEqual(curve["5"], 0.50)
            # 0.30 + 0.04 k >= 0.496 first at k = 5.
            self.assertEqual(summary["best_of_k_smallest_k"], 5)
            self.assertEqual(summary["best_of_k_label"],
                             "consistent with per-section best-of-k selection (k = 5)")
            row = next(r for r in sections if r["section"] == "GBM12_2")  # published 0.55
            self.assertEqual(row["published_percentile_within_our_seeds"], 90.0)

    def test_outside_and_not_explained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build(root, "CAC", bd.B_SEEDS, lambda s, seed: 0.40 + 0.001 * seed)
            summary, _, _ = bd.part_b(root, "CAC")
            self.assertEqual(summary["consistency_label"], "outside our seed distribution")
            self.assertIsNone(summary["best_of_k_smallest_k"])
            self.assertEqual(summary["best_of_k_label"], "not explained by seed selection alone")

    def test_wrong_seed_or_peak_count_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build(root, "GBM", bd.B_SEEDS, lambda s, seed: 0.3)
            log, _ = inv.released_locations("GBM", "GBM22_1", 7)
            config = json.loads((root / log).read_text())
            config["initialization_seed"] = 7
            (root / log).write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                bd.part_b(root, "GBM")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build(root, "GBM", bd.B_SEEDS, lambda s, seed: 0.3)
            _, res = inv.released_locations("GBM", "GBM22_1", 4)
            (peaks,) = (root / res).glob("picked_peaks_*.csv")
            peaks.write_text("0\n1.0\n")
            metrics = json.loads((root / res / "metrics.json").read_text())
            metrics["number_picked_peaks"] = 1
            (root / res / "metrics.json").write_text(json.dumps(metrics))
            with self.assertRaises(ValueError):
                bd.part_b(root, "GBM")


def set_peak_count(root, collection, section, seed, n):
    """Rewrite one released run to hold n picked peaks (dropping or adding at the end)."""
    _, res = inv.released_locations(collection, section, seed)
    (peaks,) = (root / res).glob("picked_peaks_*.csv")
    values = peaks_for(section, seed)[:n] + [f"9{j}.5" for j in range(max(0, n - COUNTS[section]))]
    peaks.write_text("0\n" + "\n".join(values) + "\n")
    metrics = json.loads((root / res / "metrics.json").read_text())
    metrics["number_picked_peaks"] = n
    (root / res / "metrics.json").write_text(json.dumps(metrics))


def write_selection_counts(root, rows):
    path = root / inv.SELECTION_COUNTS
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["idx\tcollection\tsection\tseed\tnormalization\troot\tlogged_distinct_selection\tslurm_out\tslurm_out_sha256"]
    lines += [f"{i}\t{c}\t{s}\t{seed}\treference_spatial_max\tx\t{n}\tx.out\t0"
              for i, (c, s, seed, n) in enumerate(rows)]
    path.write_text("\n".join(lines) + "\n")


class ShortPeakListTests(unittest.TestCase):
    """Released S3PL keeps all distinct selections when there are fewer than num_GT_peaks
    (CAC 240TopL seed 7: 256 of 257; supervisor chat 2026-10-20 20:39)."""

    def tree(self, root):
        for collection in ("GBM", "CAC"):
            build(root, collection, bd.B_SEEDS, lambda s, seed: 0.3 + 0.001 * seed)

    def test_short_run_with_matching_log_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.tree(root)
            set_peak_count(root, "CAC", "240TopL", 7, 256)
            write_selection_counts(root, [("CAC", "240TopL", 7, 256), ("CAC", "40TopL", 7, COUNTS["40TopL"] + 50)])
            summary, sections, _ = bd.part_b(root, "CAC")
            self.assertEqual([(s["section"], s["seed"], s["n_peaks"], s["native"])
                              for s in summary["short_peak_lists"]], [("240TopL", 7, 256, 257)])
            self.assertEqual(sum(r["n_seeds"] for r in sections), 80)  # balanced 8 x 10 kept
            out = root / "out"
            self.assertEqual(bd.run(root, out, "B"), 0)
            result = json.loads((out / "summary.json").read_text())
            self.assertEqual(result["short_peak_lists"],
                             "1/160 released runs returned 256 of 257 peaks (released "
                             "distinct-m/z cut-off; CAC 240TopL seed 7)")
            self.assertIn(str(inv.SELECTION_COUNTS).replace("\\", "/"),
                          [r["path"] for r in result["provenance"]["inputs"]])

    def test_short_run_without_matching_log_is_refused(self):
        for logged in (None, 255, 257):
            with self.subTest(logged=logged), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.tree(root)
                set_peak_count(root, "CAC", "240TopL", 7, 256)
                if logged is not None:
                    write_selection_counts(root, [("CAC", "240TopL", 7, logged)])
                with self.assertRaises(ValueError):
                    bd.part_b(root, "CAC")

    def test_above_native_or_inconsistent_log_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.tree(root)
            set_peak_count(root, "CAC", "240TopL", 7, 258)
            write_selection_counts(root, [("CAC", "240TopL", 7, 258)])
            with self.assertRaises(ValueError):
                bd.part_b(root, "CAC")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.tree(root)
            write_selection_counts(root, [("CAC", "240TopL", 7, 200)])  # full list, log says fewer
            with self.assertRaises(ValueError):
                bd.part_b(root, "CAC")

    def test_no_short_runs_sentence(self):
        self.assertEqual(inv.short_list_sentence([], 160),
                         "0/160 released runs returned fewer than num_GT_peaks peaks")

    def test_part_a_released_applies_the_same_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.tree(root)
            set_peak_count(root, "CAC", "240TopL", 7, 256)
            with self.assertRaises(ValueError):
                inv.summarise(root, "released", mixed=False)
            write_selection_counts(root, [("CAC", "240TopL", 7, 256)])
            runs, _, pairs, _, collections, _ = inv.summarise(root, "released", mixed=False)
            self.assertEqual(len(runs), 160)
            self.assertEqual(len(collections["CAC"]["short_peak_lists"]), 1)
            self.assertEqual(collections["GBM"]["short_peak_lists"], [])
            out = root / "out"
            self.assertEqual(inv.run(root, out, "released", mixed=False, figure=False), 0)
            self.assertEqual(json.loads((out / "summary.json").read_text())["short_peak_lists"],
                             "1/160 released runs returned 256 of 257 peaks (released "
                             "distinct-m/z cut-off; CAC 240TopL seed 7)")


class PartDTests(unittest.TestCase):
    def build_d(self, root, tic_score, released_score=lambda s, seed: 0.30):
        build(root, "GBM", bd.D_SEEDS, released_score)
        build(root, "GBM", bd.D_SEEDS, tic_score, locate=inv.paper_tic_locations,
              normalization="paper_tic")

    def label(self, tic):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_d(root, lambda s, seed: tic)
            return bd.part_d(root)[0]

    def test_label_cut_offs(self):
        self.assertEqual(self.label(0.4461)["label"], "explains the gap")
        self.assertEqual(self.label(0.4459)["label"], "partly")
        self.assertEqual(self.label(0.36)["label"], "partly")
        self.assertEqual(self.label(0.34)["label"], "does not explain")
        self.assertEqual(self.label(0.20)["label"], "does not explain")

    def test_disclosure_and_statistics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_d(root, lambda s, seed: 0.30 + 0.01 * inv.SECTIONS["GBM"].index(s) + 0.001)
            summary, rows, _ = bd.part_d(root)
            self.assertIn("seeds 2-3 are blind", summary["label_with_disclosure"])
            stats = summary["paired_statistics_tic_minus_released"]
            self.assertEqual(stats["n"], 8)
            self.assertAlmostEqual(stats["p_exact"] if "p_exact" in stats else stats["p"], 2 / 256)
            self.assertEqual(len(rows), 8)

    def test_released_normalisation_is_not_accepted_as_tic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build(root, "GBM", bd.D_SEEDS, lambda s, seed: 0.3)
            build(root, "GBM", bd.D_SEEDS, lambda s, seed: 0.3, locate=inv.paper_tic_locations,
                  normalization=None)
            with self.assertRaises(ValueError):
                bd.part_d(root)

    def test_existing_output_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            out.mkdir()
            self.assertEqual(bd.run(Path(tmp), out, "D"), 3)


if __name__ == "__main__":
    unittest.main()
