"""Fail-closed provenance checks of summarise_s3pl_seed_runs.py (supervisor chat
2026-10-17 07:16).

A synthetic workspace with all 24 RCC runs (and the CAC seed-1 pre-provenance
format) passes; a wrong seed, a wrong picked count, a wrong normalisation, a
missing training log, a missing manifest or an ablation run is refused with a
non-zero exit and no table written. Dependency-free (numpy only).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "summarise_s3pl_seed_runs.py"
sys.path.insert(0, str(ROOT / "scripts"))
from summarise_s3pl_seed_runs import COLLECTIONS  # noqa: E402

TARGET = 6


def write_run(project, collection, section, seed, pre=False):
    spec = COLLECTIONS[collection]
    name = spec["name"].format(section)
    results = project / spec["seeds"][seed]
    artifact = results.parents[2]
    run = results / name
    run.mkdir(parents=True, exist_ok=True)
    metrics = {"dataset": section, "number_picked_peaks": TARGET,
               "mixed_f1": {"0.3": 0.6, "0.4": 0.5, "0.5": 0.4, "0.6": 0.3 + seed / 100},
               "mSCF1": 0.45}
    if not pre:
        metrics.update({"normalization": "reference_spatial_max",
                        "source_training_name": name, "frozen_input_ablation": "none",
                        "training_input_context_mode": "none",
                        "effective_input_context_mode": "none"})
    (run / "metrics.json").write_text(json.dumps(metrics))
    z, p = spec["settings"]["peaks_per_spectral_patch"], spec["settings"]["spectral_patch_size"]
    (run / f"picked_peaks_{section}_{z}peaks_z_patchsize_{p}.csv").write_text(
        "0\n" + "".join(f"{100 + i}.5\n" for i in range(TARGET)))
    relative = artifact.relative_to(project).as_posix()
    log = {"data_dir": f"/datasets/x/{section}{spec['data_suffix']}",
           "artifact_root": "/home/u/msi" + ("" if relative == "." else "/" + relative),
           "number_peaks": None, "kernel_depth_d1": 51, "kernel_depth_d2": 1,
           "n_epochs": 10, "batch_size": 16, "learning_rate": 0.01, "random_seed": seed,
           "training_name": name, "train_history": [1.0], **spec["settings"]}
    if not pre:
        log["normalization"] = "reference_spatial_max"
    (artifact / "logs" / "s3pl").mkdir(parents=True, exist_ok=True)
    (artifact / "logs" / "s3pl" / f"{name}.json").write_text(json.dumps(log))
    if not pre:
        (artifact / "provenance").mkdir(exist_ok=True)
        (artifact / "provenance" / "manifest.txt").write_text(
            f"purpose=test\nrandom_seed={seed}; released RNG path\n"
            f"settings={', '.join(spec['manifest_settings'])}\n")
    return run, artifact / "logs" / "s3pl" / f"{name}.json"


def build(project, collection):
    spec = COLLECTIONS[collection]
    for section in spec["sections"]:
        for seed in spec["seeds"]:
            write_run(project, collection, section, seed, pre=(collection, seed) == ("cac", 1))
    sections = COLLECTIONS["cac"]["sections"] + COLLECTIONS["rcc"]["sections"]
    (project / "data_configs.py").write_text(
        "number_classes = {}\nnum_GT_peaks = {\n"
        + "".join(f"    '{s}': {TARGET},\n" for s in sections) + "}\n")


class S3plSeedProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "msi"
        build(self.project, "rcc")
        build(self.project, "cac")
        self.output = Path(self.tmp.name) / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def summarise(self, collection="rcc"):
        environment = dict(os.environ, PYTHONPATH=str(ROOT / "scripts"))
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--collection", collection, "--output",
             self.output, "--project-root", self.project, "--data-configs",
             self.project / "data_configs.py"],
            env=environment, capture_output=True, text=True)

    def run_paths(self, collection="rcc", section="UH0710_33", seed=2):
        spec = COLLECTIONS[collection]
        name = spec["name"].format(section)
        results = self.project / spec["seeds"][seed]
        return (results / name / "metrics.json",
                results.parents[2] / "logs" / "s3pl" / f"{name}.json",
                results.parents[2] / "provenance" / "manifest.txt")

    def edit(self, path, **changes):
        record = json.loads(path.read_text())
        record.update(changes)
        path.write_text(json.dumps(record))

    def assert_refused(self, result, text):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("no table written", result.stderr)
        self.assertIn(text, result.stderr)
        self.assertFalse((self.output / "summary.json").exists())
        self.assertFalse((self.output / "section_table.csv").exists())

    def test_valid_workspace_passes_and_records_hashes(self):
        result = self.summarise()
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((self.output / "summary.json").read_text())
        checks = summary["provenance_checks"]
        self.assertEqual((checks["status"], checks["runs"], checks["with_manifest"]),
                         ("passed", 24, 24))
        record = summary["provenance"]["UH0710_33/seed2"]
        self.assertEqual(record["seed"], 2)
        self.assertEqual(set(record["sha256"]), {"metrics.json", "picked_peaks", "training_log"})
        self.assertEqual(len(record["manifest_sha256"]), 64)
        self.assertIn("manifest_seed", record["verified"])

    def test_cac_seed1_pre_provenance_format_passes_with_the_gaps_recorded(self):
        result = self.summarise("cac")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((self.output / "summary.json").read_text())
        self.assertEqual(summary["provenance_checks"]["pre_provenance_runs"], 8)
        record = summary["provenance"]["40TopL/seed1"]
        self.assertEqual(record["manifest"], "no manifest (pre-manifest run)")
        self.assertIsNone(record["manifest_sha256"])
        self.assertTrue(record["normalization"].startswith("not recorded"))
        self.assertEqual(summary["provenance"]["40TopL/seed2"]["normalization"],
                         "reference_spatial_max")

    def test_wrong_seed_in_training_log_is_refused(self):
        _, log, _ = self.run_paths()
        self.edit(log, random_seed=3)
        self.assert_refused(self.summarise(), "training log seed 3, table assigns 2")

    def test_wrong_seed_in_manifest_is_refused(self):
        _, _, manifest = self.run_paths()
        manifest.write_text(manifest.read_text().replace("random_seed=2", "random_seed=1"))
        self.assert_refused(self.summarise(), "manifest random_seed is not 2")

    def test_wrong_peak_count_is_refused(self):
        metrics, _, _ = self.run_paths()
        self.edit(metrics, number_picked_peaks=TARGET + 1)
        self.assert_refused(self.summarise(), f"num_GT_peaks is {TARGET}")

    def test_wrong_normalisation_is_refused(self):
        metrics, _, _ = self.run_paths()
        self.edit(metrics, normalization="paper_tic")
        self.assert_refused(self.summarise(), "metrics normalisation 'paper_tic'")

    def test_missing_training_log_is_refused(self):
        _, log, _ = self.run_paths()
        log.unlink()
        self.assert_refused(self.summarise(), "missing")

    def test_missing_field_outside_the_pre_provenance_runs_is_refused(self):
        metrics, _, _ = self.run_paths()
        record = json.loads(metrics.read_text())
        del record["normalization"]
        metrics.write_text(json.dumps(record))
        self.assert_refused(self.summarise(), "metrics normalisation None")

    def test_missing_manifest_outside_the_pre_provenance_runs_is_refused(self):
        _, _, manifest = self.run_paths()
        manifest.unlink()
        self.assert_refused(self.summarise(), "manifest.txt")

    def test_ablation_run_and_wrong_settings_are_refused(self):
        metrics, log, _ = self.run_paths()
        self.edit(metrics, frozen_input_ablation="zero_noncentral")
        self.assert_refused(self.summarise(), "frozen_input_ablation 'zero_noncentral'")
        self.edit(metrics, frozen_input_ablation="none")
        self.edit(log, spectral_patch_size=9)
        self.assert_refused(self.summarise(), "training log spectral_patch_size 9")

    def test_pre_provenance_field_that_is_present_must_still_be_right(self):
        _, log, _ = self.run_paths("cac", "40TopL", 1)
        self.edit(log, normalization="paper_tic")
        self.assert_refused(self.summarise("cac"), "training log normalisation 'paper_tic'")


if __name__ == "__main__":
    unittest.main()
