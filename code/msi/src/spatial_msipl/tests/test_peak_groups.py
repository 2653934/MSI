"""Tests for method-independent peak partitions and peak-level scoring."""

import unittest

import numpy as np

from spatial_msipl.peak_groups import (
    check_partition_sanity,
    contiguous_runs,
    first_k_distinct_groups,
    group_apexes,
    group_reference_sets,
    max_attainable_f1,
    partition_hash,
    partition_p1_basins,
    partition_p3_ppm,
    partition_structure,
    score_groups,
)


def uniform_axis(start, n, ppm):
    return start * (1 + ppm * 1e-6) ** np.arange(n)


class PartitionP1Tests(unittest.TestCase):
    def test_two_separated_peaks_form_two_groups_with_correct_apexes(self):
        mz = uniform_axis(500.0, 21, 5.0)
        spectrum = np.zeros(21)
        spectrum[3:8] = [1, 3, 9, 3, 1]
        spectrum[13:18] = [1, 4, 10, 4, 1]
        groups, apex = partition_p1_basins(spectrum, mz)
        self.assertEqual(len(apex), int(groups.max()) + 1)
        self.assertNotEqual(groups[5], groups[15])
        self.assertIn(5, apex.tolist())
        self.assertIn(15, apex.tolist())

    def test_hard_gap_break_splits_even_without_minimum(self):
        mz = np.concatenate((uniform_axis(500.0, 5, 5.0), uniform_axis(500.2, 5, 5.0)))
        spectrum = np.linspace(1.0, 2.0, 10)  # monotone: no local minima
        groups, _ = partition_p1_basins(spectrum, mz, gap_break_ppm=50.0)
        self.assertEqual(groups[4] + 1, groups[5])
        self.assertTrue(np.all(groups[:5] == groups[0]))

    def test_shallow_dip_is_merged_but_deep_dip_is_not(self):
        mz = uniform_axis(500.0, 9, 2.0)
        shallow = np.array([1, 5, 10, 9.9, 9.95, 10, 5, 1, 0.5])
        groups, _ = partition_p1_basins(shallow, mz, smoothing_bins=1)
        self.assertEqual(groups[2], groups[5])
        deep = np.array([1, 5, 10, 2, 1, 10, 5, 1, 0.5])
        groups, _ = partition_p1_basins(deep, mz, smoothing_bins=1)
        self.assertNotEqual(groups[2], groups[5])

    def test_merge_respects_width_cap(self):
        mz = uniform_axis(500.0, 9, 30.0)  # 8 gaps x 30 ppm > 100 ppm cap
        shallow = np.array([1, 5, 10, 9.9, 9.95, 10, 5, 1, 0.5])
        groups, _ = partition_p1_basins(shallow, mz, smoothing_bins=1,
                                        max_merge_width_ppm=100.0)
        self.assertNotEqual(groups[2], groups[5])

    def test_plateau_minimum_boundary_is_first_plateau_bin(self):
        mz = uniform_axis(500.0, 9, 2.0)
        spectrum = np.array([1, 10, 2, 2, 2, 10, 1, 0.5, 0.4])
        groups, _ = partition_p1_basins(spectrum, mz, smoothing_bins=1,
                                        min_relative_depth=0.0)
        self.assertEqual(groups[1], 0)
        self.assertEqual(groups[2], 1)  # first plateau bin starts the next group
        self.assertEqual(groups[4], 1)

    def test_groups_are_contiguous_and_cover_axis(self):
        rng = np.random.default_rng(0)
        mz = uniform_axis(100.0, 500, 12.0)
        spectrum = rng.random(500)
        groups, apex = partition_p1_basins(spectrum, mz)
        self.assertEqual(groups[0], 0)
        self.assertTrue(np.all(np.isin(np.diff(groups), [0, 1])))
        for g, a in enumerate(apex):
            members = np.flatnonzero(groups == g)
            self.assertEqual(a, members[np.argmax(spectrum[members])])


class PartitionP3Tests(unittest.TestCase):
    def test_dense_axis_chains_into_one_group(self):
        mz = uniform_axis(500.0, 2000, 10.0)  # every gap 10 ppm <= 20 ppm
        groups, _ = partition_p3_ppm(np.ones(2000), mz, tolerance_ppm=20.0)
        self.assertEqual(int(groups.max()), 0)
        structure = partition_structure(groups, mz)
        verdict = check_partition_sanity(structure)
        self.assertFalse(verdict["passed"])
        self.assertTrue(any(f.startswith("S1") for f in verdict["failures"]))
        # S2 is descriptive: reported, never a failure.
        self.assertFalse(any(f.startswith("S2") for f in verdict["failures"]))
        self.assertEqual(verdict["diagnostics"]["S2_largest_group_bins"], 2000)
        self.assertEqual(verdict["diagnostics"]["S2_largest_group_fraction_of_bins"], 1.0)

    def test_many_bin_group_within_width_limit_passes(self):
        # A dense axis: 40 bins inside 0.02 Da would breach the old 0.5% bin rule
        # (40/1000 = 4%) but is physically narrow, so it must pass S1.
        mz = np.concatenate((500.0 + 0.0005 * np.arange(40),
                             600.0 + 0.1 * np.arange(960)))
        groups = np.concatenate((np.zeros(40, dtype=np.int64), np.arange(1, 961)))
        verdict = check_partition_sanity(partition_structure(groups, mz))
        self.assertTrue(verdict["passed"])
        self.assertAlmostEqual(verdict["diagnostics"]["S2_largest_group_fraction_of_bins"], 0.04)

    def test_gaps_above_tolerance_split(self):
        mz = np.array([500.0, 500.005, 500.1, 500.105])
        groups, _ = partition_p3_ppm(np.ones(4), mz, tolerance_ppm=20.0)
        np.testing.assert_array_equal(groups, [0, 0, 1, 1])


class StructureAndScoringTests(unittest.TestCase):
    def test_structure_widths_and_hash(self):
        mz = np.array([100.0, 100.001, 200.0, 300.0, 300.002])
        groups = np.array([0, 0, 1, 2, 2])
        structure = partition_structure(groups, mz)
        self.assertEqual(structure["groups"], 3)
        self.assertAlmostEqual(structure["width_da"]["max"], 0.002)
        self.assertAlmostEqual(structure["singleton_fraction"], 1 / 3)
        self.assertEqual(structure["sha256"], partition_hash(groups))
        self.assertNotEqual(partition_hash(groups), partition_hash(np.array([0, 1, 2, 3, 4])))

    def test_apex_ties_go_to_lowest_index(self):
        apex = group_apexes(np.array([0, 0, 0, 1]), np.array([2.0, 5.0, 5.0, 1.0]))
        np.testing.assert_array_equal(apex, [1, 3])

    def test_rule_a_runs_match_reviewed_example(self):
        _, run_id = contiguous_runs(np.array([10, 11, 12, 20, 22, 23]))
        self.assertEqual(int(run_id[-1]) + 1, 3)

    def test_first_k_distinct_groups_skips_duplicates_and_counts_bins(self):
        group_of_bin = np.array([0, 0, 0, 1, 1, 2, 3])
        ranking = np.array([0, 1, 3, 2, 5, 6, 4])
        order, consumed = first_k_distinct_groups(ranking, group_of_bin, 3)
        np.testing.assert_array_equal(order, [0, 1, 2])
        self.assertEqual(consumed, 5)
        with self.assertRaises(ValueError):
            first_k_distinct_groups(ranking[:2], group_of_bin, 2)

    def test_group_reference_uses_apex_only(self):
        apex = np.array([1, 3, 5])
        reference = group_reference_sets({0.4: {0, 3}}, apex)
        # Group 0 has a positive shoulder bin (0) but a negative apex (1).
        self.assertEqual(reference[0.4], {1})

    def test_duplicate_bins_count_once_at_group_level(self):
        references = {t: {0, 1} for t in (0.3, 0.4, 0.5, 0.6)}
        result = score_groups({0, 0, 2}, references, n_groups=4)
        metrics = result["threshold_results"]["0.4"]
        self.assertEqual(metrics["true_positive"], 1)
        self.assertEqual(metrics["false_positive"], 1)
        self.assertEqual(metrics["false_negative"], 1)
        self.assertAlmostEqual(result["mSCF1"], 0.5)

    def test_max_attainable_f1(self):
        self.assertEqual(max_attainable_f1(581, 581), 1.0)
        self.assertAlmostEqual(max_attainable_f1(584, 940), 2 * 584 / (584 + 940))


if __name__ == "__main__":
    unittest.main()
