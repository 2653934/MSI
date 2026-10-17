"""Runtime table v2 (supervisor chat 2026-10-17 09:48, item 1).

The v1 table must stay byte-identical; v2 adds a seed and a loader column and the
RCC, S3PL 100-epoch, S3PL seed 2/3 and Test R cached rows. Tests on the real
artifacts are skipped where those artifacts are not present (e.g. on the cluster
test job, which has no synced copy of every reproducibility folder).
"""

import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import build_runtime_and_training_curves as builder  # noqa: E402

V1_CSV = ROOT / "results" / "publication" / "current_evidence" / "runtime_all_sections.csv"


def have_local_artifacts():
    return (V1_CSV.exists()
            and (builder.RCC_EXPERIMENTS / "RCC_MH0204_33_seed1").exists()
            and builder.S3PL_E100.exists() and builder.S3PL_RCC.exists()
            and builder.S3PL_CAC_SEEDS.exists())


def csv_text(rows):
    handle = io.StringIO()
    fields = list(rows[0])
    for row in rows[1:]:
        fields += [key for key in row if key not in fields]
    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue()


def write_vae_run(folder, seed=2, loader="cached_float32", epochs=3, status="complete"):
    folder.mkdir(parents=True)
    history = [{"epoch": e, "epoch_seconds": 1.5, "total_loss": 1.0,
                "reconstruction_loss": 1.0, "kl_loss": 0.0} for e in range(1, epochs + 1)]
    controls = {"seed": seed}
    if loader is not None:
        controls["data_loader"] = loader
    (folder / "summary.json").write_text(json.dumps({
        "status": status, "controls": controls, "training_seconds": 1.5 * epochs,
        "dataset_load_seconds": 0.25, "peak_gpu_memory_allocated_bytes": 10,
        "resumed_from_epoch": 0, "samples_per_epoch": 7}), encoding="utf-8")
    (folder / "metadata.json").write_text(json.dumps({
        "epochs": epochs, "seed": seed, "device_name": "NVIDIA GeForce RTX 3090"}),
        encoding="utf-8")
    (folder / "training_history.json").write_text(json.dumps(history), encoding="utf-8")


def write_s3pl_run(root, section, epochs, seed, patch, peaks, initialization=None,
                   normalization="reference_spatial_max"):
    name = f"{section}_Attention3DConvAutoencoder_{epochs}epochs_{peaks}_spectral_patch_size_{patch}"
    results = root / "results" / "baselines" / "s3pl" / name
    logs = root / "logs" / "s3pl"
    results.mkdir(parents=True)
    logs.mkdir(parents=True, exist_ok=True)
    (results / "runtime_metrics.json").write_text(json.dumps({
        "dataset": section, "normalization": normalization, "device": "NVIDIA GeForce RTX 3090",
        "training_seconds": 10.0 * epochs, "peak_gpu_memory_bytes": 5}), encoding="utf-8")
    log = {"n_epochs": epochs, "random_seed": seed, "training_name": name}
    if initialization is not None:
        log["initialization_seed"] = initialization
    (logs / f"{name}.json").write_text(json.dumps(log), encoding="utf-8")


class V1Unchanged(unittest.TestCase):
    @unittest.skipUnless(have_local_artifacts(), "local runtime artifacts not present")
    def test_v1_rows_are_byte_identical_to_the_committed_table(self):
        self.assertEqual(csv_text(builder.runtime_rows()),
                         V1_CSV.read_text(encoding="utf-8"))

    def test_v1_and_v2_files_are_distinct(self):
        self.assertEqual(builder.V1_NAME, "runtime_all_sections.csv")
        self.assertEqual(builder.V2_NAME, "runtime_all_sections_v2.csv")


class V2OnLocalArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not have_local_artifacts():
            raise unittest.SkipTest("local runtime artifacts not present")
        cls.v1 = builder.runtime_rows()
        cls.v2 = builder.runtime_rows_v2(test_r_root=Path(tempfile.mkdtemp()))

    def test_every_v1_row_is_carried_over_unchanged(self):
        carried = self.v2[:len(self.v1)]
        for old, new in zip(self.v1, carried):
            stripped = {k: v for k, v in new.items() if k not in ("seed", "loader")}
            self.assertEqual(stripped, old)
            self.assertEqual(list(new)[:5], ["section", "collection", "development_section",
                                             "method", "seed"])
            self.assertEqual(list(new)[5], "loader")

    def test_loader_column(self):
        for row in self.v2[:len(self.v1)]:
            expected = "streaming" if row["timer_boundary"] == builder.STREAMED else "cached"
            self.assertEqual(row["loader"], expected, (row["section"], row["method"]))
        streaming = [r for r in self.v2 if r["loader"] == "streaming"]
        self.assertEqual(len(streaming), 32)   # GBM/CAC production centre-only and uniform
        self.assertTrue(all(r["method"] in ("vae_central_only", "vae_uniform_mean")
                            and r["collection"] in ("GBM", "CAC") for r in streaming))

    def test_added_rows_without_test_r(self):
        added = self.v2[len(self.v1):]
        def count(**match):
            return sum(all(r[k] == v for k, v in match.items()) for r in added)
        self.assertEqual(len(added), 16 + 24 + 16 + 16 + 8)
        self.assertEqual(count(collection="RCC", method="vae_central_only", seed=1), 8)
        self.assertEqual(count(collection="RCC", method="vae_uniform_mean", seed=1), 8)
        for seed in (1, 2, 3):
            self.assertEqual(count(collection="RCC", method="s3pl_10_epochs", seed=seed), 8)
        for seed in (2, 3):
            self.assertEqual(count(collection="CAC", method="s3pl_10_epochs", seed=seed), 8)
        self.assertEqual(count(method="s3pl_100_epochs", seed=1), 16)
        self.assertTrue(all(r["loader"] == "cached" for r in added
                            if r["method"] != "legacy_msipl_whole_job"))
        legacy = [r for r in added if r["method"] == "legacy_msipl_whole_job"]
        self.assertEqual([r["section"] for r in legacy], list(builder.RCC))
        self.assertTrue(all(r["training_seconds"] is None and r["slurm_job_wall_seconds"] > 0
                            and r["timer_boundary"] == builder.LEGACY_WALL for r in legacy))
        self.assertEqual(legacy[1]["slurm_job"], "69625_1")   # UH0505_12 retry
        self.assertTrue(all(r["epochs"] == 100 for r in added if r["method"] == "s3pl_100_epochs"))
        self.assertFalse(any(r["development_section"] for r in added if r["collection"] == "RCC"))

    def test_rows_are_unique(self):
        keys = [(r["section"], r["method"], r["seed"]) for r in self.v2]
        self.assertEqual(len(keys), len(set(keys)))


class LoaderAndSeedChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_cached_summary_under_the_streaming_timer_is_refused(self):
        write_vae_run(self.tmp / "run", seed=1, loader="cached_float32")
        with self.assertRaises(SystemExit):
            builder.vae_loader(self.tmp / "run", builder.STREAMED)

    def test_streaming_summary_under_the_cached_timer_is_refused(self):
        for loader in ("streaming_hdf5", None):
            folder = self.tmp / f"run_{loader}"
            write_vae_run(folder, seed=1, loader=loader)
            with self.assertRaises(SystemExit):
                builder.vae_loader(folder, builder.CACHED_TIMER)

    def test_historical_summary_without_loader_field_is_streaming(self):
        write_vae_run(self.tmp / "run", seed=1, loader=None)
        self.assertEqual(builder.vae_loader(self.tmp / "run", builder.STREAMED), "streaming")

    def test_s3pl_seed_mismatch_is_refused(self):
        write_s3pl_run(self.tmp, "MH0204_33", 10, seed=3, patch=5, peaks=1024)
        with self.assertRaises(SystemExit):
            builder.s3pl_seed_row("RCC_MH0204_33", self.tmp, epochs=10, seed=2)

    def test_s3pl_controlled_rng_or_other_normalisation_is_refused(self):
        write_s3pl_run(self.tmp / "a", "MH0204_33", 10, seed=2, patch=5, peaks=1024,
                       initialization=2)
        with self.assertRaises(SystemExit):
            builder.s3pl_seed_row("RCC_MH0204_33", self.tmp / "a", epochs=10, seed=2)
        write_s3pl_run(self.tmp / "b", "MH0204_33", 10, seed=2, patch=5, peaks=1024,
                       normalization="paper_tic")
        with self.assertRaises(SystemExit):
            builder.s3pl_seed_row("RCC_MH0204_33", self.tmp / "b", epochs=10, seed=2)

    def test_s3pl_row(self):
        write_s3pl_run(self.tmp, "40TopL", 100, seed=1, patch=9, peaks=256)
        row = builder.s3pl_seed_row("40TopL", self.tmp, epochs=100, seed=1)
        self.assertEqual((row["method"], row["seed"], row["loader"], row["epochs"]),
                         ("s3pl_100_epochs", 1, "cached", 100))
        self.assertEqual(row["seconds_per_epoch"], 10.0)
        self.assertEqual(row["timer_boundary"], builder.S3PL_TIMER)


LEGACY_LINES = ["# comment"] + [
    f"69570_{i}|msipl-rcc|COMPLETED|00:01:00|{60 + i}|n{i}|0:0|a|b" for i in range(8)]


class LegacyRows(unittest.TestCase):
    def write(self, lines):
        path = Path(tempfile.mkdtemp()) / "sacct.txt"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_rows_keep_wall_time_out_of_the_training_columns(self):
        lines = list(LEGACY_LINES)
        lines[2] = "69570_1|msipl-rcc|FAILED|00:00:00|0|n1|1:0|a|b"
        lines.append("69625_1|msipl-rcc|COMPLETED|00:03:55|235|m74|0:0|a|b")
        rows = builder.legacy_rcc_rows(self.write(lines))
        self.assertEqual(len(rows), 8)
        self.assertEqual((rows[1]["slurm_job"], rows[1]["slurm_job_wall_seconds"]), ("69625_1", 235))
        self.assertTrue(all(r["training_seconds"] is None and r["seconds_per_epoch"] is None
                            for r in rows))
        self.assertEqual(rows[0]["loader"], "not applicable (whole job)")

    def test_missing_or_duplicate_completed_task_is_refused(self):
        with self.assertRaises(SystemExit):
            builder.legacy_rcc_rows(self.write(LEGACY_LINES[:-1]))
        with self.assertRaises(SystemExit):
            builder.legacy_rcc_rows(self.write(
                LEGACY_LINES + ["69625_1|msipl-rcc|COMPLETED|00:03:55|235|m74|0:0|a|b"]))


class TestRRows(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_absent_root_gives_no_rows(self):
        rows, counts = builder.test_r_rows(self.root / "missing")
        self.assertEqual((rows, counts), ([], {2: 0, 3: 0}))

    def test_present_runs_are_tabulated_with_seed_and_cached_loader(self):
        write_vae_run(self.root / "RCC_MH0204_33_seed2" / "central_only", seed=2)
        write_vae_run(self.root / "GBM12_1_seed3" / "uniform_mean", seed=3)
        rows, counts = builder.test_r_rows(self.root)
        self.assertEqual(counts, {2: 1, 3: 1})
        self.assertEqual([(r["section"], r["method"], r["seed"], r["loader"]) for r in rows],
                         [("RCC_MH0204_33", "vae_central_only", 2, "cached"),
                          ("GBM12_1", "vae_uniform_mean", 3, "cached")])
        self.assertEqual(rows[0]["collection"], "RCC")
        self.assertEqual(rows[0]["timer_boundary"], builder.CACHED_TIMER)

    def test_seed_mismatch_streaming_or_incomplete_is_refused(self):
        cases = (dict(seed=3), dict(seed=2, loader="streaming_hdf5"),
                 dict(seed=2, status="running"))
        for index, case in enumerate(cases):
            root = self.root / str(index)
            write_vae_run(root / "40TopL_seed2" / "central_only", **case)
            with self.assertRaises(SystemExit, msg=str(case)):
                builder.test_r_rows(root)

    def test_seed_one_or_unknown_section_is_refused(self):
        for name in ("40TopL_seed1", "XYZ_seed2"):
            root = self.root / name
            write_vae_run(root / name / "central_only", seed=int(name[-1]))
            with self.assertRaises(SystemExit, msg=name):
                builder.test_r_rows(root)


if __name__ == "__main__":
    unittest.main()
