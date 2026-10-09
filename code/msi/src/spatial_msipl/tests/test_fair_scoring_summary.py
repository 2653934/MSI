"""Provenance checks of the fair-scoring decision-table script.

Writes minimal synthetic per-section summaries (no HDF5 or model inputs) and
checks when summarise_fair_scoring_baselines.py may combine them. The real
approval approves P1 for every section but P3 for CAC only, so GBM and CAC
summaries legitimately record different approved partition parameters.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "summarise_fair_scoring_baselines.py"
GBM = ["GBM108_positive", "GBM108_negative", "GBM12_1", "GBM12_2",
       "GBM22_1", "GBM22_2", "GBM39_1", "GBM39_2"]
CAC = ["40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL", "400TopL", "520TopL"]
P1 = {"hard_break_ppm": 50}
P3 = {"connect_ppm": 20}


def provenance(partitions):
    return {
        "evaluation_version": 4,
        "protocol": "v3.2",
        "parameters": {"thresholds": [0.4], "random_seed": 20261009,
                       "approved_partition_parameters": partitions},
        "partition_approval": {"sha256": "abc"} if partitions else None,
        "code": {"evaluate_fair_scoring_baselines.py": "c0de"},
    }


def summary(partitions, ig=0.5, posterior=0.6):
    scores = {"1.0": {"mSCF1": ig}}
    return {
        "status": "complete",
        "provenance": provenance(partitions),
        "bin_level": {
            "integrated_gradients": scores,
            "posterior_abs_pcc_balanced": {"1.0": {"mSCF1": posterior}},
            "legacy_msipl": {"1.0": {"mSCF1": 0.4}},
            "random": {"1.0": {"mSCF1_mean": 0.1}},
        },
        "peak_level": {
            name: {"methods": {
                "integrated_gradients": {"matched_K_peak": {"mSCF1": ig},
                                         "collapse_K_bin": {"mSCF1": ig}},
                "posterior_abs_pcc_balanced": {"matched_K_peak": {"mSCF1": posterior}},
                "legacy_msipl": {"collapse_K_bin": {"mSCF1": 0.4}},
            }} for name in partitions},
    }


class SummaryProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "results"
        self.output = Path(self.tmp.name) / "summary"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, section, record, arm="central_only"):
        path = self.root / f"{section}_seed1" / arm / "summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record), encoding="utf-8")

    def write_campaign(self):
        for section in GBM:
            self.write(section, summary({"P1": P1}))
        for section in CAC:
            self.write(section, summary({"P1": P1, "P3": P3}))

    def summarise(self):
        return subprocess.run([sys.executable, str(SCRIPT), "--root", self.root,
                               "--output", self.output],
                              env=dict(os.environ), capture_output=True, text=True)

    def test_collection_specific_partitions_are_accepted(self):
        self.write_campaign()
        result = self.summarise()
        self.assertEqual(result.returncode, 0, result.stderr)
        decisions = json.loads((self.output / "decisions.json").read_text())
        self.assertEqual(decisions["GBM/central_only"]["peak_level_partitions_used"], ["P1"])
        self.assertEqual(decisions["CAC/central_only"]["peak_level_partitions_used"],
                         ["P1", "P3"])
        campaign = decisions["_campaign_provenance"]
        self.assertEqual(campaign["approved_partition_parameters_by_collection"],
                         {"GBM": {"P1": P1}, "CAC": {"P1": P1, "P3": P3}})
        self.assertNotIn("approved_partition_parameters", campaign["parameters"])

    def test_bin_level_campaign_has_no_partitions(self):
        for section in GBM + CAC:
            self.write(section, summary({}))
        result = self.summarise()
        self.assertEqual(result.returncode, 0, result.stderr)
        campaign = json.loads((self.output / "decisions.json").read_text())[
            "_campaign_provenance"]
        self.assertEqual(campaign["approved_partition_parameters_by_collection"],
                         {"GBM": {}, "CAC": {}})

    def test_partition_mismatch_within_a_collection_is_refused(self):
        self.write_campaign()
        self.write("GBM12_1", summary({"P1": P1, "P3": P3}))
        result = self.summarise()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to mix", result.stderr)
        self.assertFalse((self.output / "decisions.json").exists())

    def test_code_mismatch_across_collections_is_refused(self):
        self.write_campaign()
        for section in CAC:
            record = summary({"P1": P1, "P3": P3})
            record["provenance"]["code"]["evaluate_fair_scoring_baselines.py"] = "other"
            self.write(section, record)
        result = self.summarise()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("collections come from different code", result.stderr)

    def test_other_parameter_mismatch_across_collections_is_refused(self):
        self.write_campaign()
        for section in GBM:
            record = summary({"P1": P1})
            record["provenance"]["parameters"]["random_seed"] = 1
            self.write(section, record)
        result = self.summarise()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to mix", result.stderr)

    def test_approval_mismatch_within_a_collection_is_refused(self):
        self.write_campaign()
        record = summary({"P1": P1})
        record["provenance"]["partition_approval"]["sha256"] = "different"
        self.write("GBM39_2", record)
        result = self.summarise()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to mix", result.stderr)


if __name__ == "__main__":
    unittest.main()
