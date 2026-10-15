"""Item A and G decision table, and the A(b) saved-list reproduction check.

Synthetic per-section summaries only (no HDF5, model or real section).
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import check_saved_list_reproduction as reproduction
import summarise_fair_scoring_arms as arms
from spatial_msipl.tests.test_fair_scoring_summary import CAC, GBM, P1, P3, provenance


def summary(partitions, ig, posterior=0.6, k_bin=100):
    return {
        "status": "complete", "provenance": provenance(partitions), "K_bin": k_bin,
        "bin_level": {"integrated_gradients": {"1.0": {"mSCF1": ig}},
                      "posterior_abs_pcc_balanced": {"1.0": {"mSCF1": posterior}}},
        "peak_level": {name: {"methods": {
            "integrated_gradients": {"matched_K_peak": {"mSCF1": ig}},
            "posterior_abs_pcc_balanced": {"matched_K_peak": {"mSCF1": posterior}}}}
            for name in partitions},
    }


class ArmsDecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.scopes = {"bin_level_only": (root / "base_bin", root / "extra_bin"),
                       "with_approved_partitions": (root / "base_part", root / "extra_part")}
        self.patches = [patch.object(arms, "SCOPES", self.scopes),
                        patch.object(arms, "CENTREMASK", root / "centremask")]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.tmp.cleanup()

    def write(self, section, arm, ig, code="c0de"):
        extra = arm not in arms.EXISTING_ARMS
        for index, scope in enumerate(("bin_level_only", "with_approved_partitions")):
            partitions = {} if index == 0 else (
                {"P1": P1} if section.startswith("GBM") else {"P1": P1, "P3": P3})
            record = summary(partitions, ig)
            record["provenance"]["code"] = {"evaluate_fair_scoring_baselines.py": code}
            path = self.scopes[scope][int(extra)] / f"{section}_seed1" / arm / "summary.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record), encoding="utf-8")

    def decide(self):
        out = Path(self.tmp.name) / "out"
        with patch("sys.argv", ["x", "--output", str(out)]):
            arms.main()
        return json.loads((out / "decisions.json").read_text(encoding="utf-8"))

    def test_rule_improves_equivalent_and_mixed(self):
        for i, section in enumerate(GBM):
            self.write(section, "uniform_mean", 0.50)
            self.write(section, "attention", 0.53)          # +0.03 in 8/8
        for i, section in enumerate(CAC):
            self.write(section, "uniform_mean", 0.50)
            self.write(section, "attention", 0.51 if i < 4 else 0.44)   # mean -0.025
        decisions = self.decide()["comparisons"]["A: attention vs uniform_mean"]
        self.assertEqual(decisions["GBM"]["verdict"], "attention improves on uniform_mean")
        self.assertEqual(decisions["CAC"]["verdict"], "mixed")
        self.assertEqual(decisions["GBM"]["P1"]["positive_sections"], 8)

    def test_equivalent_and_ig_vs_posterior_fall_through(self):
        for section in GBM:
            self.write(section, "uniform_mean", 0.50)
            self.write(section, "attention", 0.505)
        decisions = self.decide()
        self.assertEqual(decisions["comparisons"]["A: attention vs uniform_mean"]["GBM"]["verdict"],
                         "attention equivalent to uniform_mean")
        posterior = decisions["ig_vs_posterior"]["attention"]["GBM"]
        self.assertTrue(posterior["ig_vs_posterior_verdict"].startswith("mixed / not resolved"))
        self.assertEqual(posterior["ig_minus_posterior_bin"]["positive_sections"], 0)
        self.assertIn("Section 7.1", posterior["ig_vs_posterior_verdict"])

    def test_incomplete_collection_gets_no_verdict(self):
        for section in GBM[:7]:
            self.write(section, "uniform_mean", 0.5)
            self.write(section, "attention", 0.6)
        verdict = self.decide()["comparisons"]["A: attention vs uniform_mean"]["GBM"]["verdict"]
        self.assertIn("no verdict", verdict)

    def test_refuses_mixed_evaluator_code(self):
        for section in GBM:
            self.write(section, "uniform_mean", 0.5)
            self.write(section, "attention", 0.6, code="different")
        with self.assertRaises(SystemExit) as raised:
            self.decide()
        self.assertIn("refusing to mix", str(raised.exception))

    def test_g3_and_mechanism_rules(self):
        for section, real, shuffled in (("160TopL", 0.50, 0.47), ("GBM22_2", 0.50, 0.49)):
            self.write(section, "attention_centremask_p50", real)
            self.write(section, "shuffled_attention_centremask_p50", shuffled)
            path = (Path(self.tmp.name) / "centremask" / f"{section}_seed1"
                    / "attention_centremask_p50" / "mechanism" / "attention_weights.json")
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({
                "status": "valid",
                "centremask_p50": {"normalized_entropy": {"median": 0.90}},
                "unmasked_seed1_same_centres": {"normalized_entropy": {"median": 0.99}}}))
        decisions = self.decide()
        self.assertTrue(decisions["g3_spatial_specificity"]["result"].startswith("real-context "
                                                                                 "masked attention does not"))
        self.assertEqual(decisions["g_mechanism"]["result"], "masking made attention selective")


class SavedListReproductionTests(unittest.TestCase):
    def run_check(self, saved_bins, saved_mscf1):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attribution = root / "attribution"
            saved = root / "saved"
            attribution.mkdir()
            saved.mkdir()
            # Component 0 ranks bins 0 > 1 = 2 (exact tie) > 3; component 1 has no signal.
            np.savez(attribution / "attributions.npz",
                     component_0_combined_absolute_mean=np.array([4.0, 2.0, 2.0, 1.0, 0.0]),
                     component_1_combined_absolute_mean=np.zeros(5),
                     first_layer_combined_l2=np.array([5.0, 4.0, 3.0, 2.0, 1.0]))
            count = len(saved_bins)
            for name, bins in (("ig", saved_bins), ("first_layer_l2", [0, 1, 2][:count])):
                rows = "rank,bin_index\n" + "".join(f"{r + 1},{b}\n" for r, b in enumerate(bins))
                (saved / f"{name}_matched_{count}_bins.csv").write_text(rows)
            (saved / "summary.json").write_text(json.dumps({"matched_peak_evaluation": {
                "count": count, "methods": {"integrated_gradients": {"mSCF1": saved_mscf1},
                                            "first_layer_l2": {"mSCF1": 0.3}}}}))
            scores = {(0, 1, 2): 0.3}

            def fake_score(indices, correlations, n_bins):
                return {"mSCF1": 0.3 if tuple(sorted(int(i) for i in indices)) in scores else 0.1}

            output = root / "out.json"
            argv = ["x", "--input", str(root / "S.h5"), "--attribution-dir", str(attribution),
                    "--saved-evaluation-dir", str(saved), "--output", str(output),
                    "--allow-outside-slurm"]
            with patch("sys.argv", argv), \
                    patch.object(reproduction, "read_h5_metadata",
                                 return_value=(np.arange(5.0), np.zeros(4), None, None, True)), \
                    patch.object(reproduction, "load_correlations", return_value={}), \
                    patch.object(reproduction, "score_indices", side_effect=fake_score):
                try:
                    reproduction.main()
                    code = 0
                except SystemExit as stop:
                    code = stop.code
            return code, json.loads(output.read_text())

    def test_exact_tie_swap_passes(self):
        # Bins 1 and 2 tie exactly, so either order reproduces.
        code, record = self.run_check([0, 2, 1], 0.3)
        self.assertEqual(code, 0)
        self.assertEqual(record["status"], "passed")

    def test_different_bins_or_score_fail_with_exit_4(self):
        code, record = self.run_check([0, 1, 3], 0.3)
        self.assertEqual((code, record["status"]), (4, "failed"))
        code, record = self.run_check([0, 1, 2], 0.31)
        self.assertEqual((code, record["status"]), (4, "failed"))
        self.assertIn("mSCF1", record["error"])


if __name__ == "__main__":
    unittest.main()
