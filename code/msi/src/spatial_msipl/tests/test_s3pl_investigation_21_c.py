"""Investigation 21 Part C summariser (protocol 18 Section 6.7) on toy data."""

import json
import tempfile
import unittest
from pathlib import Path

import summarise_s3pl_investigation_21_c as c
import summarise_s3pl_seed_investigation_21 as inv

COUNTS = inv.native_counts()
TASKS = (Path(c.ROOT) / c.PART_C / "provenance" / "tasks.tsv")


def write(root, arm, section, init, order, repeat, score, history=(0.5, 0.02), peaks_tag=0,
          seeds=None):
    if arm == "repeat":
        log, res = c.repeat_locations(section, repeat)
        init_seed, order_seed = None, None
    else:
        log, res = c.controlled_locations(section, init, order)
        init_seed, order_seed = init, order
    if seeds is not None:
        init_seed, order_seed = seeds
    (root / log).parent.mkdir(parents=True, exist_ok=True)
    (root / res).mkdir(parents=True, exist_ok=True)
    (root / log).write_text(json.dumps({"n_epochs": len(history), "train_history": list(history),
                                        "random_seed": 1, "initialization_seed": init_seed,
                                        "sample_order_seed": order_seed}))
    mixed = {"0.3": score + 0.03, "0.4": score + 0.01, "0.5": score - 0.01, "0.6": score - 0.03}
    peaks = [f"{100 + j}.{peaks_tag}" for j in range(COUNTS[section])]
    (root / res / "metrics.json").write_text(json.dumps({
        "dataset": section, "mixed_f1": mixed, "mSCF1": round(score, 3),
        "number_picked_peaks": len(peaks), "normalization": "reference_spatial_max"}))
    (root / res / f"picked_peaks_{section}.csv").write_text("0\n" + "\n".join(peaks) + "\n")


def build(root, init_score, order_score, repeat_score, repeat_tag=lambda s, r: 0):
    for arm, section, init, order, repeat in c.arm_runs():
        if arm == "init":
            score = init_score(section, init)
        elif arm == "order":
            score = order_score(section, order)
        else:
            score = repeat_score(section, repeat)
        tag = repeat_tag(section, repeat) if arm == "repeat" else 0
        write(root, arm, section, init, order, repeat, score, peaks_tag=tag)


def label(init_score, order_score, repeat_score, **kw):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build(root, init_score, order_score, repeat_score, **kw)
        return c.summarise(root)


class LocationTests(unittest.TestCase):
    def test_new_runs_are_exactly_the_part_c_task_table(self):
        new = set()
        for arm, section, init, order, repeat in c.arm_runs():
            log, _ = (c.repeat_locations(section, repeat) if arm == "repeat"
                      else c.controlled_locations(section, init, order))
            parts = Path(log).parts
            if Path(*parts[:3]) == c.PART_C:
                new.add("/".join(parts[:4]))
        table = {line.split()[5] for line in TASKS.read_text().splitlines()}
        self.assertEqual(new, table)
        self.assertEqual(len(table), 19)

    def test_saved_runs_are_reused(self):
        log, _ = c.controlled_locations("GBM108_positive", 5, 1)
        self.assertIn("s3pl_massnet/GBM108_positive_p3_rng_init5_order1", str(log).replace("\\", "/"))
        log, _ = c.controlled_locations("GBM12_2", 3, 1)
        self.assertIn("s3pl_massnet/GBM12_2_p3_rng_init3_order1", str(log).replace("\\", "/"))
        log, _ = c.controlled_locations("GBM108_positive", 1, 2)
        self.assertIn("s3pl_massnet/GBM108_positive_p3_rng_init1_order2", str(log).replace("\\", "/"))
        log, _ = c.repeat_locations("GBM12_2", 1)
        self.assertIn("gate_repeat/GBM12_2_p3_seed1_repeat_r2", str(log).replace("\\", "/"))
        log, _ = c.repeat_locations("GBM108_negative", 0)
        self.assertEqual(str(log).replace("\\", "/"),
                         "logs/s3pl/GBM108_negative_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_3.json")


class RuleTests(unittest.TestCase):
    def test_initialisation_dominant_and_identical_repeats(self):
        summary, sections, runs, _ = label(lambda s, i: 0.1 * i, lambda s, o: 0.1 + 0.001 * o,
                                           lambda s, r: 0.1)
        self.assertEqual(len(runs), 39)
        self.assertEqual(summary["dominant_label"], "initialisation dominant")
        self.assertEqual(summary["nondeterminism_label"], "not dominated by nondeterminism")
        self.assertEqual(summary["sections_repeats_bit_identical"], 3)
        self.assertTrue(all(r["repeat_sd"] == 0 for r in sections))

    def test_order_dominant_in_two_of_three(self):
        init = lambda s, i: 0.1 + (0.001 * i if s != "GBM12_2" else 0.1 * i)  # noqa: E731
        summary, _, _, _ = label(init, lambda s, o: 0.1 * o, lambda s, r: 0.1)
        self.assertEqual(summary["sections_order_ge_2x_init"], 2)
        self.assertEqual(summary["dominant_label"], "data order dominant")

    def test_neither_and_zero_sd_edge(self):
        summary, _, _, _ = label(lambda s, i: 0.3, lambda s, o: 0.3, lambda s, r: 0.3)
        self.assertEqual(summary["dominant_label"], "neither component dominant")
        self.assertEqual(summary["nondeterminism_label"], "not dominated by nondeterminism")
        summary, _, _, _ = label(lambda s, i: 0.1 * i, lambda s, o: 0.1 * o, lambda s, r: 0.3)
        self.assertEqual(summary["dominant_label"], "neither component dominant")

    def test_nondeterminism_clause(self):
        summary, sections, _, _ = label(lambda s, i: 0.1 * i, lambda s, o: 0.1 + 0.01 * o,
                                        lambda s, r: 0.1 + 0.01 * r, repeat_tag=lambda s, r: r)
        # order SD = 0.0158, repeat SD = 0.01 >= half of it, in all 3 sections.
        self.assertEqual(summary["sections_repeat_ge_half_smaller_arm"], 3)
        self.assertEqual(summary["nondeterminism_label"], "dominated by nondeterminism")
        self.assertEqual(summary["sections_repeats_bit_identical"], 0)
        self.assertEqual(sections[0]["repeat_distinct_peak_lists"], 3)


class RefusalTests(unittest.TestCase):
    def test_wrong_saved_seeds_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build(root, lambda s, i: 0.1, lambda s, o: 0.1, lambda s, r: 0.1)
            write(root, "order", "GBM12_2", 1, 4, None, 0.1, seeds=(1, 1))
            with self.assertRaises(ValueError):
                c.summarise(root)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build(root, lambda s, i: 0.1, lambda s, o: 0.1, lambda s, r: 0.1)
            write(root, "repeat", "GBM108_negative", None, None, 2, 0.1, seeds=(1, 1))
            with self.assertRaises(ValueError):
                c.summarise(root)

    def test_existing_output_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            out.mkdir()
            self.assertEqual(c.run(Path(tmp), out), 3)

    def test_run_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build(root, lambda s, i: 0.1 * i, lambda s, o: 0.1, lambda s, r: 0.1)
            out = root / "out"
            self.assertEqual(c.run(root, out), 0)
            result = json.loads((out / "summary.json").read_text())
            self.assertEqual(result["C"]["dominant_label"], "initialisation dominant")
            # 39 arm slots, 36 distinct runs (init 1 / order 1 is in both arms), 3 files each.
            self.assertEqual(len(result["provenance"]["inputs"]), 36 * 3)


if __name__ == "__main__":
    unittest.main()
