"""Item 3, C3 training length (supervisor chat 2026-10-30 12:58 item 3, 20:16 request 4).

1. train_vae(snapshot_epochs=...) saves snapshot_epoch<NNN>.pt after the listed
   epochs and leaves training unchanged: the history and final weights equal a run
   without snapshots; the default () saves nothing (torch; skipped without it).
2. Opt-in flags with production defaults: the trainer's --snapshot-epochs (default
   none) and the IG script's --expected-epochs (default 100, the production check).
3. Job scripts: cached loader, the production recipe plus snapshots, the two
   development sections and both arms at seed 1, new roots, the quarantine passed as
   --exclude on the command line, no --exclusive.
4. summarise_training_length.py on a synthetic tree: per-epoch scores and loss, the
   epoch-100 reproduction check (pass, score mismatch, prefix mismatch), "not done"
   epochs and refusal of an existing output.
"""

import ast
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
JOBS = ROOT / "slurm_jobs"
sys.path.insert(0, str(SCRIPTS))
import summarise_training_length as summariser  # noqa: E402

try:
    import torch
except ImportError:  # local tier: no torch
    torch = None


def argument_default(path, flag):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument"
                and node.args and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == flag):
            for keyword in node.keywords:
                if keyword.arg == "default":
                    return ast.literal_eval(keyword.value)
    raise AssertionError(f"{flag} not found in {path}")


@unittest.skipIf(torch is None, "torch not installed (covered by the cluster test job)")
class SnapshotTrainingTests(unittest.TestCase):
    def setUp(self):
        from spatial_msipl.model import NeighbourhoodSpatialVAE
        from spatial_msipl.tests.test_neighbourhood import TinyNeighbourhoodDataset
        from spatial_msipl.training import set_random_seed, train_vae
        self.train_vae, self.dataset = train_vae, TinyNeighbourhoodDataset

        def build():
            set_random_seed(1)
            return NeighbourhoodSpatialVAE(spectral_dim=6, neighbourhood="uniform_mean",
                                           hidden_dim=4, latent_dim=2, attention_dim=2)
        self.build = build
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)

    def run_training(self, name, **options):
        model = self.build()
        _, history = self.train_vae(
            model=model, dataset=self.dataset(), output_directory=self.directory / name,
            checkpoint_directory=self.directory / f"{name}_checkpoints", epochs=4,
            batch_size=4, seed=1, **options)
        timing = {"epoch_seconds", "samples_per_second"}
        return model, [{k: v for k, v in r.items() if k not in timing} for r in history]

    def test_snapshots_saved_and_training_unchanged(self):
        plain_model, plain_history = self.run_training("plain")
        snap_model, snap_history = self.run_training("snap", snapshot_epochs=(1, 3))
        self.assertEqual(plain_history, snap_history)
        for key, value in plain_model.state_dict().items():
            self.assertTrue(torch.equal(value, snap_model.state_dict()[key]), key)
        saved = sorted(p.name for p in (self.directory / "snap_checkpoints").glob("snapshot_*"))
        self.assertEqual(saved, ["snapshot_epoch001.pt", "snapshot_epoch003.pt"])
        snapshot = torch.load(self.directory / "snap_checkpoints" / "snapshot_epoch003.pt",
                              map_location="cpu", weights_only=False)
        self.assertEqual(snapshot["completed_epochs"], 3)
        self.assertIn("model_state_dict", snapshot)
        self.assertIn("model_configuration", snapshot)
        self.assertEqual(list(self.directory.glob("plain_checkpoints/snapshot_*")), [])

    def test_snapshot_epochs_are_validated(self):
        for bad in ((0,), (4,), (5,)):
            with self.assertRaises(ValueError):
                self.run_training(f"bad{bad[0]}", snapshot_epochs=bad)


class FlagDefaultTests(unittest.TestCase):
    def test_production_defaults_unchanged(self):
        self.assertEqual(argument_default(SCRIPTS / "train_spatial_msipl_production.py",
                                          "--snapshot-epochs"), [])
        self.assertEqual(argument_default(SCRIPTS / "run_spatial_msipl_gmm_integrated_gradients.py",
                                          "--expected-epochs"), 100)
        source = (SCRIPTS / "run_spatial_msipl_gmm_integrated_gradients.py").read_text(
            encoding="utf-8")
        self.assertIn("def load_model(path, spectral_dim, variant, device, checkpoint=None, "
                      "expected_epochs=100):", source)
        self.assertIn("attribution requires the complete 100-epoch checkpoint", source)
        training = (ROOT / "src" / "spatial_msipl" / "training.py").read_text(encoding="utf-8")
        self.assertIn("    snapshot_epochs=(),\n):", training)


class JobScriptTests(unittest.TestCase):
    def setUp(self):
        self.run = (JOBS / "run_training_length.sh").read_text(encoding="utf-8")
        self.sections = (JOBS / "training_length_sections.sh").read_text(encoding="utf-8")
        self.submit = (JOBS / "submit_training_length.sh").read_text(encoding="utf-8")

    def test_production_recipe_plus_snapshots(self):
        for text in ("--cache-spectra", "--epochs 100", "--batch-size 128", "--hidden-dim 512",
                     "--latent-dim 5", "--learning-rate 0.001", "--spatial-lambda 0",
                     "--seed 1", "--snapshot-epochs $TRAINING_LENGTH_SNAPSHOTS",
                     "--expected-epochs \"$epoch\"", "--ig-steps 64", "--gmm-n-init 20",
                     "--matched-count \"$K_BIN\"", "evaluate_fair_scoring_baselines.py"):
            self.assertIn(text, self.run)
        self.assertIn('TRAINING_LENGTH_SNAPSHOTS="10 25 50"', self.sections)
        self.assertIn("for epoch in $TRAINING_LENGTH_SNAPSHOTS 100; do", self.run)

    def test_scope_roots_and_partition(self):
        self.assertIn("TRAINING_LENGTH_SECTIONS=(GBM108_positive 40TopL)", self.sections)
        self.assertIn("TRAINING_LENGTH_ARMS=(central_only uniform_mean)", self.sections)
        for root in ("results/experiments/training_length_20261030",
                     "msi_checkpoints/spatial_msipl/training_length_20261030",
                     "fair_scoring_baselines/training_length_20261030/bin_level_only"):
            self.assertIn(root, self.sections)
        self.assertNotIn("#SBATCH --exclusive", self.run)
        self.assertIn('--exclude="$exclude"', self.submit)
        self.assertIn("gpu_cuda_quarantine.txt", self.submit)
        self.assertIn("Row $index output exists", self.submit)


class SummariserTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.prefix = {"integrated_gradients": np.array([3, 1, 2]),
                       "posterior_abs_pcc_balanced": np.array([0, 2, 1])}
        for section in summariser.SECTIONS:
            for arm in summariser.ARMS:
                history = [{"epoch": e, "total_loss": 100.0 / e, "reconstruction_loss": 90.0 / e,
                            "kl_loss": 10.0 / e} for e in range(1, 101)]
                self.write(summariser.EXPERIMENT / f"{section}_seed1" / arm /
                           "training_history.json", history)
                for epoch in summariser.EPOCHS:
                    self.fair(summariser.FAIR / f"{section}_seed1" / arm / f"epoch{epoch}",
                              0.4 + epoch / 1000, 0.6)
                self.fair(summariser.PRODUCTION / f"{section}_seed1" / arm, 0.5, 0.6)

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def fair(self, relative, ig, posterior, prefix=None):
        self.write(relative / "summary.json", {
            "status": "complete", "K_bin": 3,
            "bin_level": {"integrated_gradients": {"1.0": {"mSCF1": ig}},
                          "posterior_abs_pcc_balanced": {"1.0": {"mSCF1": posterior}}}})
        np.savez(self.root / relative / "rankings_prefix.npz", **(prefix or self.prefix))

    def summarise(self):
        output = self.root / "out"
        self.assertEqual(summariser.main(["--project-root", str(self.root),
                                          "--output", str(output)]), 0)
        return json.loads((output / "summary.json").read_text(encoding="utf-8")), output

    def test_scores_loss_and_reproduction(self):
        summary, output = self.summarise()
        self.assertTrue(summary["all_epoch_100_reproduced"])
        self.assertEqual(len(summary["scores_by_epoch"]), 16)
        first = summary["scores_by_epoch"][0]
        self.assertEqual(first["epoch"], 10)
        self.assertAlmostEqual(first["integrated_gradients_mSCF1"], 0.41)
        self.assertAlmostEqual(first["total_loss"], 10.0)
        self.assertEqual(len((output / "training_loss.csv").read_text().splitlines()), 401)
        self.assertEqual(summariser.main(["--project-root", str(self.root),
                                          "--output", str(output)]), 3)

    def test_mismatch_and_not_done(self):
        self.fair(summariser.FAIR / "GBM108_positive_seed1/central_only/epoch100", 0.5001, 0.6)
        self.fair(summariser.FAIR / "40TopL_seed1/uniform_mean/epoch100", 0.5, 0.6,
                  prefix={**self.prefix, "integrated_gradients": np.array([3, 2, 1])})
        (self.root / summariser.FAIR / "40TopL_seed1/central_only/epoch25/summary.json").unlink()
        summary, _ = self.summarise()
        checks = summary["epoch_100_reproduction"]
        self.assertFalse(summary["all_epoch_100_reproduced"])
        self.assertFalse(checks["GBM108_positive/central_only"]["reproduced"])
        self.assertFalse(checks["40TopL/uniform_mean"]["ranking_prefixes_identical"])
        self.assertTrue(checks["GBM108_positive/uniform_mean"]["reproduced"])
        not_done = [r for r in summary["scores_by_epoch"] if r["status"] == "not done"]
        self.assertEqual([(r["section"], r["arm"], r["epoch"]) for r in not_done],
                         [("40TopL", "central_only", 25)])


if __name__ == "__main__":
    unittest.main()
