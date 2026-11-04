"""Label-free K (protocol 18 Section 6.10; decision log D56).

1. Job scripts: 48 section-arms in the Test R order, equal to the summariser's;
   the BIC table is exactly the 28 section-arms without an earlier selection; the
   IG call is the production campaign call except --gmm-components, --ig-steps and
   (above 64 steps) the alignment to the arm's own 64-step folder; the matched
   evaluation is Test R's call plus --no-component-mapping; fair scoring is Test R's
   call at bin level; no training and no --exclusive; the submitter passes
   --exclude (quarantine plus mscluster144), --partition and --dependency on the
   sbatch command line; every job refuses an existing output (exit 3) and an
   escalation whose previous step count is not needs_more_ig_steps.
2. resolve_label_free_k.py: K from the BIC record, never typed; K = 1 uses the
   recorded best K >= 2 (flagged); a different latent or an incomplete record stops.
3. The matched evaluator: default path bit-identical to the frozen pre-change copy
   (fixtures/pre_label_free_k/, HEAD 8f6e4b42); --no-component-mapping runs at a K
   different from the class count (ARI/NMI only), the default path refuses it; the
   unchanged fair evaluator scores such a run.
4. summarise_label_free_k.py on a synthetic tree: rule labels with not-done
   sections, the decisive step count, pending runs, the K-independent gate and the
   refusal of an existing output.
5. Read-only provenance on synced results (skipped when absent): every existing BIC
   selection was made on the production latent the jobs start from.
6. The IG script's figure palette (after 81467): the production colours are kept,
   there are at least 6, the palette is indexed modulo its length only, and the three
   IG figures render at K = 6 and K = 9 (torch; runs in the cluster test job).
Bash and NumPy; part 3 also needs h5py, sklearn and matplotlib.
"""

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

try:
    import h5py  # noqa: F401
    import sklearn.mixture  # noqa: F401
    import matplotlib  # noqa: F401
    DEPENDENCIES = True
except ImportError:  # pragma: no cover - environments without these
    DEPENDENCIES = False

ROOT = Path(__file__).resolve().parents[3]
JOBS = ROOT / "slurm_jobs"
SCRIPTS = ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pre_label_free_k"
FIXTURE_SHA256 = "bf5e4e118d2fc3092e13a1e14b51604970f62761b64cf343f2d1137de2ef32f4"
BASH = shutil.which("bash")
sys.path.insert(0, str(SCRIPTS))
import resolve_label_free_k as resolve_module  # noqa: E402
import summarise_label_free_k as summary_module  # noqa: E402

EXISTING_BIC = ({(s, a) for s in ("GBM108_positive", "40TopL")
                 for a in ("central_only", "uniform_mean")}
                | {(s, a) for s in summary_module.SECTIONS["RCC"]
                   for a in ("central_only", "uniform_mean")})


def bash_path(path):
    """A path as bash sees it (Git Bash on Windows wants /c/..., not C:/...)."""
    if os.name != "nt":
        return Path(path).as_posix()
    return subprocess.run([BASH, "-c", 'cygpath -u "$1"', "_", str(path)],
                          capture_output=True, text=True, check=True).stdout.strip()


def fake_home():
    home = Path(tempfile.mkdtemp())
    shutil.copytree(JOBS, home / "msi" / "slurm_jobs")
    return home


def sourced(command, home):
    script = f'source "$HOME/msi/slurm_jobs/label_free_k_sections.sh"; {command}'
    return subprocess.run([BASH, "-c", script], capture_output=True, text=True,
                          env=dict(os.environ, HOME=bash_path(home)))


def block(text, start, end):
    match = re.search(re.escape(start) + r".*?" + re.escape(end), text, re.DOTALL)
    if match is None:
        raise AssertionError(f"no block {start} ... {end}")
    return " ".join(match.group(0).replace("\\\n", " ").split())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@unittest.skipUnless(BASH, "bash not available")
class JobScriptTests(unittest.TestCase):
    def setUp(self):
        self.home = fake_home()
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        probe = sourced("lfk_task 0", self.home)
        if probe.returncode != 0:
            self.skipTest(f"cannot source the job table here: {probe.stderr.strip()}")

    def rows(self, command):
        result = sourced(command, self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [line.split() for line in result.stdout.splitlines()]

    def test_task_tables(self):
        tasks = self.rows('for i in $(seq 0 47); do lfk_task $i; echo "$TASK_SECTION $TASK_ARM"; done')
        expected = {(s, a) for sections in summary_module.SECTIONS.values()
                    for s in sections for a in summary_module.ARMS}
        self.assertEqual(len(tasks), 48)
        self.assertEqual({tuple(t) for t in tasks}, expected)
        self.assertNotEqual(sourced("lfk_task 48", self.home).returncode, 0)
        bic = self.rows('for i in $(seq 0 27); do lfk_bic_task $i; echo "$TASK_SECTION $TASK_ARM"; done')
        self.assertEqual({tuple(t) for t in bic}, expected - EXISTING_BIC)
        self.assertEqual(len(bic), 28)
        self.assertNotEqual(sourced("lfk_bic_task 28", self.home).returncode, 0)

    def test_selection_paths_and_new_roots(self):
        rows = self.rows('for i in $(seq 0 47); do lfk_task $i; echo "$TASK_SECTION $TASK_ARM '
                         '$(lfk_bic_selection $TASK_SECTION $TASK_ARM) '
                         '$(lfk_result_root $TASK_SECTION $TASK_ARM 64) '
                         '$(lfk_fair_output $TASK_SECTION $TASK_ARM 64)"; done')
        for section, arm, selection, root, fair in rows:
            if (section, arm) in EXISTING_BIC:
                self.assertRegex(selection, r"/diagnostics/gate_d_bic(_rcc|_rcc_ig_steps_20261030)?/")
            else:
                self.assertIn("/diagnostics/gate_d_bic_label_free_k_20261104/", selection)
            self.assertTrue(selection.endswith(f"/{section}_seed1/{arm}/bic_selection.json"))
            self.assertIn(f"/experiments/label_free_k_20261104/{section}_seed1/{arm}/steps64", root)
            self.assertIn("/fair_scoring_baselines/label_free_k_20261104/bin_level_only/", fair)
        steps = self.rows("for s in 128 256 512 1024; do lfk_previous_steps $s; done")
        self.assertEqual([int(r[0]) for r in steps], [64, 128, 256, 512])
        self.assertNotEqual(sourced("lfk_check_steps 2048", self.home).returncode, 0)

    def test_ig_call_is_the_campaign_call_except_k_steps_and_alignment(self):
        campaign = block((JOBS / "run_rcc_campaign.sh").read_text(),
                         "scripts/run_spatial_msipl_gmm_integrated_gradients.py", "--sampling-seed 1")
        job = block((JOBS / "run_label_free_k_ig.sh").read_text(),
                    "scripts/run_spatial_msipl_gmm_integrated_gradients.py",
                    '${ALIGN_ARGUMENTS[@]+"${ALIGN_ARGUMENTS[@]}"}')
        campaign = (campaign.replace('"$RESULT_ROOT/attribution"', '"$ROOT/attribution"')
                    .replace('"$RCC_GMM_COMPONENTS"', '"$GMM_COMPONENTS"')
                    .replace("--ig-steps 64", '--ig-steps "$STEPS"'))
        self.assertEqual(job, campaign + ' ${ALIGN_ARGUMENTS[@]+"${ALIGN_ARGUMENTS[@]}"}')
        text = (JOBS / "run_label_free_k_ig.sh").read_text()
        self.assertIn('[ "$STEPS" = 64 ] || ALIGN_ARGUMENTS=(--align-gmm-labels-to-production "$FIRST/attribution")', text)
        self.assertIn("scripts/resolve_label_free_k.py", text)
        self.assertLess(text.index("scripts/check_ig_steps_gate.py"),
                        text.index("scripts/evaluate_spatial_msipl_attributed_peaks.py"))

    def test_evaluation_calls(self):
        test_r = block((JOBS / "run_test_r_campaign.sh").read_text(),
                       "scripts/evaluate_spatial_msipl_attributed_peaks.py", "--chunk-size 1024")
        job = block((JOBS / "run_label_free_k_ig.sh").read_text(),
                    "scripts/evaluate_spatial_msipl_attributed_peaks.py", "--chunk-size 1024")
        expected = test_r.replace('"$RESULT_ROOT/attribution"', '"$ROOT/attribution"').replace(
            '"${LEGACY_ARGUMENTS[@]}"', '"${LEGACY_ARGUMENTS[@]}" --no-component-mapping')
        self.assertEqual(job, expected)
        test_r_fair = block((JOBS / "run_test_r_fair_scoring.sh").read_text(),
                            "scripts/evaluate_fair_scoring_baselines.py", "--chunk-size 1024")
        fair = block((JOBS / "run_label_free_k_fair_scoring.sh").read_text(),
                     "scripts/evaluate_fair_scoring_baselines.py", "--chunk-size 1024")
        self.assertEqual(fair, test_r_fair.replace('"$attribution"', '"$ROOT/attribution"')
                         .replace('"$saved"', '"$SAVED"').replace('"$output"', '"$OUTPUT"'))
        text = (JOBS / "run_label_free_k_fair_scoring.sh").read_text()
        self.assertNotIn("--partition-dir", text)
        self.assertIn('--no-legacy --reference-budget "$(test_r_rcc_budget "$DATASET")"', text)

    def test_no_training_no_exclusive_and_options_on_the_command_line(self):
        for name in ("run_label_free_k_ig.sh", "run_label_free_k_bic.sh",
                     "run_label_free_k_fair_scoring.sh", "submit_label_free_k.sh"):
            text = (JOBS / name).read_text()
            code = "\n".join(line for line in text.splitlines()
                             if not line.lstrip().startswith("#") or line.startswith("#SBATCH"))
            self.assertNotIn("train_spatial_msipl_production", code)
            self.assertNotIn("--exclusive", code)
            self.assertNotIn("SBATCH_EXCLUDE", text)
            self.assertNotIn("SBATCH_DEPENDENCY", text)
        self.assertIn("#SBATCH --partition=batch", (JOBS / "run_label_free_k_bic.sh").read_text())
        self.assertIn("#SBATCH --partition=batch",
                      (JOBS / "run_label_free_k_fair_scoring.sh").read_text())

    def fake_sbatch(self):
        bin_dir = self.home / "bin"
        bin_dir.mkdir(exist_ok=True)
        record = self.home / "sbatch_args.txt"
        script = bin_dir / "sbatch"
        script.write_text(f'#!/bin/bash\nprintf "%s\\n" "$@" > "{bash_path(record)}"\necho 4242\n',
                          newline="\n")
        script.chmod(0o755)
        return bin_dir, record

    def submit(self, *arguments):
        bin_dir, record = self.fake_sbatch()
        environment = dict(os.environ, HOME=bash_path(self.home))
        command = f'export PATH="{bash_path(bin_dir)}:$PATH"; bash "$HOME/msi/slurm_jobs/submit_label_free_k.sh" "$@"'
        result = subprocess.run([BASH, "-c", command, "_", *arguments], capture_output=True,
                                text=True, env=environment)
        return result, (record.read_text().splitlines() if record.exists() else [])

    def test_submitter_passes_exclude_partition_and_dependency_as_options(self):
        result, args = self.submit("ig", "64", "0-47", "--partition", "batch",
                                   "--after", "777", "--concurrency", "3")
        self.assertEqual(result.returncode, 0, result.stderr)
        exclude = [a for a in args if a.startswith("--exclude=")]
        self.assertEqual(len(exclude), 1)
        nodes = set(exclude[0].split("=", 1)[1].split(","))
        self.assertIn("mscluster144", nodes)
        self.assertIn("mscluster129", nodes)
        self.assertIn("--partition=batch", args)
        self.assertIn("--dependency=afterok:777", args)
        self.assertIn("--array=0-47%3", args)
        self.assertEqual(args[-2:], ["slurm_jobs/run_label_free_k_ig.sh", "64"])
        self.assertIn("--parsable", args)
        log = self.home / "msi/results/experiments/label_free_k_20261104/provenance/slurm_job_ids.txt"
        self.assertIn("4242 stage=ig steps=64", log.read_text())

    def test_submitter_refuses_existing_outputs_and_unwarranted_escalation(self):
        root = (self.home / "msi/results/experiments/label_free_k_20261104"
                / "RCC_MH0204_33_seed1/central_only")
        (root / "steps64").mkdir(parents=True)
        result, args = self.submit("ig", "64", "0")
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(args, [])
        write_json(root / "steps64/attribution/summary.json", {"status": "valid"})
        result, args = self.submit("ig", "128", "0")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(args, [])
        write_json(root / "steps64/attribution/summary.json", {"status": "needs_more_ig_steps"})
        result, args = self.submit("ig", "128", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        result, _ = self.submit("ig", "96", "0")
        self.assertNotEqual(result.returncode, 0)

    def run_job(self, name, task, *arguments):
        return subprocess.run(
            [BASH, bash_path(self.home / "msi" / "slurm_jobs" / name), *arguments],
            capture_output=True, text=True,
            env=dict(os.environ, HOME=bash_path(self.home), SLURM_ARRAY_TASK_ID=str(task),
                     SLURM_ARRAY_JOB_ID="1", SLURM_JOB_ID="1"))

    def test_jobs_refuse_existing_outputs_before_anything_runs(self):
        root = (self.home / "msi/results/experiments/label_free_k_20261104"
                / "RCC_MH0204_33_seed1/central_only/steps64")
        (root / "attribution").mkdir(parents=True)
        result = self.run_job("run_label_free_k_ig.sh", 0, "64")
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(sorted(p.name for p in root.iterdir()), ["attribution"])
        selection = (self.home / "msi/results/diagnostics/gate_d_bic_label_free_k_20261104"
                     / "160TopL_seed1/central_only/bic_selection.json")
        write_json(selection, {"status": "complete"})
        result = self.run_job("run_label_free_k_bic.sh", 0)
        self.assertEqual(result.returncode, 3, result.stderr)

    def test_ig_job_refuses_escalation_without_a_failed_previous_run(self):
        result = self.run_job("run_label_free_k_ig.sh", 0, "256")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(result.returncode, 3)

    def test_fair_job_reports_not_done_and_waits_for_pending_escalations(self):
        base = (self.home / "msi/results/experiments/label_free_k_20261104"
                / "RCC_MH0204_33_seed1/central_only")
        write_json(base / "steps64/not_done.json",
                   {"status": "not_done", "reason": "GMM component under 44 px at K = 6"})
        result = self.run_job("run_label_free_k_fair_scoring.sh", 0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("not done", result.stdout)
        base = (self.home / "msi/results/experiments/label_free_k_20261104"
                / "RCC_MH0204_33_seed1/uniform_mean")
        write_json(base / "steps64/attribution/summary.json", {"status": "needs_more_ig_steps"})
        result = self.run_job("run_label_free_k_fair_scoring.sh", 1)
        self.assertEqual(result.returncode, 1)
        self.assertIn("escalation pending", result.stderr)


def bic_record(k=6, best=None, sha="abc", status="complete"):
    return {"status": status, "selected_k": k, "best_k_at_least_2": best, "production_k": 3,
            "provenance": {"parameters": {"candidates": [1, 2, 3, 4, 5, 6]},
                           "source_artifacts": {"latent_mean.npy": {"sha256": sha}}}}


class ResolveTests(unittest.TestCase):
    def test_selected_k_and_boundary(self):
        record = resolve_module.resolve(bic_record(6), "abc")
        self.assertEqual(record["label_free_k"], 6)
        self.assertTrue(record["at_boundary_of_tested_range"])
        self.assertIsNone(record["flag"])
        record = resolve_module.resolve(bic_record(4), "abc")
        self.assertEqual(record["label_free_k"], 4)
        self.assertFalse(record["at_boundary_of_tested_range"])

    def test_k_one_uses_the_recorded_best_k_at_least_2(self):
        record = resolve_module.resolve(bic_record(1, best=3), "abc")
        self.assertEqual((record["label_free_k"], record["bic_selected_k"]), (3, 1))
        self.assertIn("best K >= 2", record["flag"])
        with self.assertRaises(ValueError):
            resolve_module.resolve(bic_record(1, best=None), "abc")

    def test_other_latent_or_incomplete_record_stops(self):
        with self.assertRaises(ValueError):
            resolve_module.resolve(bic_record(6, sha="other"), "abc")
        with self.assertRaises(ValueError):
            resolve_module.resolve(bic_record(6, status="running"), "abc")

    def test_command_line_reads_the_latent_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "production").mkdir()
            latent = tmp / "production" / "latent_mean.npy"
            np.save(latent, np.zeros((3, 2), dtype=np.float32))
            sha = hashlib.sha256(latent.read_bytes()).hexdigest()
            write_json(tmp / "bic.json", bic_record(6, sha=sha))
            arguments = [sys.executable, str(SCRIPTS / "resolve_label_free_k.py"),
                         "--bic-selection", str(tmp / "bic.json"),
                         "--production-attribution", str(tmp / "production"),
                         "--output", str(tmp / "out" / "label_free_k.json")]
            result = subprocess.run(arguments, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "6")
            self.assertEqual(subprocess.run(arguments, capture_output=True).returncode, 3)
            write_json(tmp / "bic.json", bic_record(6, sha="different"))
            arguments[-1] = str(tmp / "out2" / "label_free_k.json")
            self.assertEqual(subprocess.run(arguments, capture_output=True).returncode, 1)
            self.assertFalse((tmp / "out2").exists())


@unittest.skipUnless(DEPENDENCIES, "h5py/sklearn/matplotlib not importable")
class MatchedEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from spatial_msipl.tests.test_rcc_pipeline import build_section, run
        from sklearn.mixture import GaussianMixture
        from sklearn.preprocessing import StandardScaler

        cls.script = staticmethod(run)
        cls.tmp = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.tmp.name)
        cls.input, cls.attribution, labels, mz, centres = build_section(root, "SYN2", 2, seed=0)
        cls.k_bin = 20
        # The same section segmented at K = 4 (more components than classes).
        cls.attribution4 = root / "SYN2_attribution_k4"
        shutil.copytree(cls.attribution, cls.attribution4)
        latent = np.load(cls.attribution4 / "latent_mean.npy").astype(np.float64)
        scaler = StandardScaler().fit(latent)
        gmm = GaussianMixture(4, covariance_type="full", random_state=1).fit(scaler.transform(latent))
        posterior = gmm.predict_proba(scaler.transform(latent))
        component = np.argmax(posterior, axis=1)
        saved = np.load(cls.attribution4 / "coordinates_and_gmm.npz")
        np.savez(cls.attribution4 / "gmm_parameters.npz",
                 scaler_mean=scaler.mean_, scaler_scale=scaler.scale_,
                 mixture_weights=gmm.weights_.astype(np.float32),
                 component_means=gmm.means_.astype(np.float32),
                 covariances=gmm.covariances_.astype(np.float32),
                 precision_cholesky=gmm.precisions_cholesky_.astype(np.float32))
        np.savez(cls.attribution4 / "coordinates_and_gmm.npz", x=saved["x"], y=saved["y"],
                 component=component,
                 assigned_posterior=posterior[np.arange(len(component)), component].astype(np.float32))
        rng = np.random.default_rng(5)
        arrays = dict(np.load(cls.attribution4 / "attributions.npz"))
        for c in range(4):
            ig = np.abs(rng.normal(size=len(mz))) * 0.1
            ig[centres[c::4]] += 1.0
            arrays[f"component_{c}_combined_absolute_mean"] = ig.astype(np.float32)
        np.savez(cls.attribution4 / "attributions.npz", **arrays)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def matched(self, output, attribution, *extra, directory=SCRIPTS, check=True):
        return self.script("evaluate_spatial_msipl_attributed_peaks.py", "--input", self.input,
                        "--attribution-dir", attribution, "--no-legacy", "--output", output,
                        "--matched-count", self.k_bin, "--chunk-size", 64, "--ion-images", 2,
                        "--consolidated-candidates", 5, *extra, directory=directory, check=check)

    @staticmethod
    def comparable(path):
        summary = json.loads(Path(path).read_text())
        summary.pop("runtime_seconds", None)
        summary.get("provenance", {}).pop("code", None)
        return summary

    def test_fixture_is_the_pre_change_script(self):
        digest = hashlib.sha256(
            (FIXTURES / "evaluate_spatial_msipl_attributed_peaks.py").read_bytes()).hexdigest()
        self.assertEqual(digest, FIXTURE_SHA256)

    def test_default_path_is_unchanged(self):
        new, old = self.root / "default_new", self.root / "default_old"
        self.matched(new, self.attribution)
        self.matched(old, self.attribution, directory=FIXTURES)
        self.assertEqual(self.comparable(new / "summary.json"), self.comparable(old / "summary.json"))
        for name in sorted(p.name for p in old.glob("*.csv")):
            self.assertEqual((new / name).read_bytes(), (old / name).read_bytes(), name)
        self.assertEqual(sorted(p.name for p in new.iterdir()), sorted(p.name for p in old.iterdir()))

    def test_flag_scores_a_k_that_differs_from_the_class_count(self):
        refused = self.matched(self.root / "k4_default", self.attribution4, check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("component and expert-label counts must match", refused.stderr)
        output = self.root / "k4_flag"
        self.matched(output, self.attribution4, "--no-component-mapping")
        summary = json.loads((output / "summary.json").read_text())
        agreement = summary["cluster_mapping"]
        self.assertIsNone(agreement["mapping"])
        self.assertEqual((agreement["components"], agreement["classes"]), (4, 2))
        self.assertNotIn("balanced_accuracy", agreement)
        self.assertIn("adjusted_rand_index", agreement)
        self.assertFalse((output / "gmm_expert_mapping.png").exists())
        self.assertEqual(summary["matched_peak_evaluation"]["count"], self.k_bin)
        # The unchanged fair evaluator scores the K = 4 run.
        budget = self.root / "budget.json"
        write_json(budget, {"status": "complete", "K_bin": self.k_bin, "provenance": {
            "input": {"sha256": hashlib.sha256(Path(self.input).read_bytes()).hexdigest()}}})
        fair = self.script("evaluate_fair_scoring_baselines.py", "--input", self.input,
                        "--attribution-dir", self.attribution4, "--saved-evaluation-dir", output,
                        "--no-legacy", "--reference-budget", budget,
                        "--output", self.root / "k4_fair", "--random-draws", 5,
                        "--chunk-size", 64, "--allow-outside-slurm", check=False)
        self.assertEqual(fair.returncode, 0, fair.stderr)
        scored = json.loads((self.root / "k4_fair" / "summary.json").read_text())
        self.assertIn("posterior_abs_pcc_balanced", scored["bin_level"])


def fair_summary(k_bin, scores):
    return {"status": "complete", "K_bin": k_bin,
            "bin_level": {method: {"1.0": {"mSCF1": value}} for method, value in scores.items()}}


class SummariserTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.results = self.tmp / "results"
        self.composite = self.tmp / "composite"
        self.experiments = self.results / "experiments/label_free_k_20261104"
        self.fair = self.results / "diagnostics/fair_scoring_baselines/label_free_k_20261104/bin_level_only"
        for collection, sections in summary_module.SECTIONS.items():
            for section in sections:
                for arm in summary_module.ARMS:
                    self.add(collection, section, arm, correlation=0.5, ig=0.3)

    def base_scores(self, collection):
        scores = {"mean_intensity": 0.2, "variance": 0.25, "morans_i": 0.45, "oracle": 0.8}
        if collection != "RCC":
            scores["legacy_msipl"] = 0.22
        return scores

    def add(self, collection, section, arm, correlation, ig, steps_status=("valid",), not_done=None):
        base = self.experiments / f"{section}_seed1" / arm
        if base.exists():
            shutil.rmtree(base)
        write_json(base / "steps64/label_free_k.json",
                   {"label_free_k": 6, "bic_selected_k": 6, "flag": None,
                    "at_boundary_of_tested_range": True, "production_k": 3})
        scope = "rcc/bin_level_only" if collection == "RCC" else "bin_level_only"
        production = dict(self.base_scores(collection), integrated_gradients=0.35,
                          posterior_abs_pcc_balanced=0.6)
        write_json(self.composite / "results/diagnostics/fair_scoring_baselines" / scope
                   / f"{section}_seed1" / arm / "summary.json", fair_summary(100, production))
        if not_done:
            write_json(base / "steps64/not_done.json", {"reason": not_done})
            return
        for steps, status in zip(summary_module.STEPS, steps_status):
            root = base / f"steps{steps}"
            write_json(root / "attribution/summary.json", {
                "status": status, "integrated_gradients": {"completeness": {
                    "median_normalized_residual": 0.001,
                    "percentile_95_normalized_residual": 0.1 if status == "valid" else 0.2}}})
            write_json(root / "identity_check.json", {"passed": True})
            if steps != 64:
                write_json(root / "gmm_gate_v2.json", {"passed": True})
            if status == "valid":
                evaluation = root / ("peak_evaluation_released_target" if collection == "RCC"
                                     else "peak_evaluation")
                write_json(evaluation / "summary.json", {"cluster_mapping": {
                    "adjusted_rand_index": 0.3, "normalized_mutual_information": 0.4}})
                scores = dict(self.base_scores(collection), integrated_gradients=ig,
                              posterior_abs_pcc_balanced=correlation)
                write_json(self.fair / f"{section}_seed1" / arm / f"steps{steps}" / "summary.json",
                           fair_summary(100, scores))

    def summarise(self, name="out"):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "summarise_label_free_k.py"),
             "--results-root", str(self.results), "--composite-root", str(self.composite),
             "--output", str(self.tmp / name)], capture_output=True, text=True)

    def cell(self, decisions, collection, arm):
        return next(c for c in decisions["cells"]
                    if c["collection"] == collection and c["arm"] == arm)

    def test_rule_labels(self):
        self.assertEqual(summary_module.rule_label(7, 0), "holds")
        self.assertEqual(summary_module.rule_label(8, 0), "holds")
        self.assertEqual(summary_module.rule_label(6, 1), "incomplete; no verdict")
        self.assertEqual(summary_module.rule_label(5, 1), "does not hold")
        self.assertEqual(summary_module.rule_label(6, 0), "does not hold")
        self.assertEqual(summary_module.rule_label(5, 2), "incomplete; no verdict")

    def test_table_labels_steps_and_wording(self):
        gbm = summary_module.SECTIONS["GBM"]
        self.add("GBM", gbm[0], "central_only", correlation=0.2, ig=0.3)       # IG wins
        self.add("GBM", gbm[1], "central_only", correlation=0.5, ig=0.3,
                 not_done="GMM component under 44 px at K = 6")
        self.add("CAC", "40TopL", "uniform_mean", correlation=0.5, ig=0.3,
                 steps_status=("needs_more_ig_steps", "needs_more_ig_steps", "valid"))
        result = self.summarise()
        self.assertEqual(result.returncode, 0, result.stderr)
        decisions = json.loads((self.tmp / "out/decisions.json").read_text())
        cell = self.cell(decisions, "GBM", "central_only")
        self.assertEqual((cell["correlation_beats_ig"], cell["not_done"]), (6, 1))
        self.assertEqual(cell["label"], "incomplete; no verdict")
        self.assertEqual(self.cell(decisions, "RCC", "uniform_mean")["label"], "holds")
        self.assertEqual(self.cell(decisions, "RCC", "uniform_mean")
                         ["descriptive_means_label_free_k"]["legacy_msipl"],
                         "not rescored at the label-free K")
        record = next(r for r in decisions["sections"]
                      if r["section"] == "40TopL" and r["arm"] == "uniform_mean")
        self.assertEqual(record["steps"], 256)
        self.assertEqual(len(record["ig_residual_trajectory"]), 3)
        self.assertIn("boundary of the tested range", decisions["label_free_k_wording"])
        self.assertIn("GBM central_only: incomplete", decisions["overall"])
        with open(self.tmp / "out/per_section.csv", encoding="utf-8") as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 48)
        self.assertEqual(self.summarise().returncode, 3)

    def test_all_hold_gives_the_overall_sentence(self):
        result = self.summarise()
        self.assertEqual(result.returncode, 0, result.stderr)
        decisions = json.loads((self.tmp / "out/decisions.json").read_text())
        self.assertEqual(decisions["overall"],
                         "The IG < correlation result does not depend on the class-informed K.")

    def test_pending_run_writes_nothing(self):
        self.add("RCC", "RCC_UH0505_12", "central_only", correlation=0.5, ig=0.3,
                 steps_status=("needs_more_ig_steps",))
        result = self.summarise()
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.tmp / "out").exists())

    def test_k_independent_gate_stops(self):
        path = (self.fair / "GBM12_1_seed1/central_only/steps64/summary.json")
        summary = json.loads(path.read_text())
        summary["bin_level"]["morans_i"]["1.0"]["mSCF1"] += 1e-4
        path.write_text(json.dumps(summary))
        result = self.summarise()
        self.assertEqual(result.returncode, 5)
        self.assertFalse((self.tmp / "out/decisions.json").exists())
        failure = json.loads((self.tmp / "out/gate_failure.json").read_text())
        self.assertEqual(failure[0]["section"], "GBM12_1")


PRODUCTION_PALETTE = ("#457B9D", "#E76F51", "#6D597A", "#2A9D8F")
IG_SCRIPT = SCRIPTS / "run_spatial_msipl_gmm_integrated_gradients.py"


class IgFigurePaletteTests(unittest.TestCase):
    """The IG figures at K = 6 (81467 crashed in save_attribution_figure; P18 Section 6.10)."""

    def palette(self):
        import ast
        tree = ast.parse(IG_SCRIPT.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    getattr(target, "id", None) == "CLUSTER_COLOURS" for target in node.targets):
                return ast.literal_eval(node.value)
        raise AssertionError("CLUSTER_COLOURS not found")

    def test_palette_keeps_production_colours_and_covers_k6(self):
        palette = self.palette()
        self.assertEqual(tuple(palette[:4]), PRODUCTION_PALETTE)
        self.assertGreaterEqual(len(palette), 6)
        self.assertEqual(len(set(palette)), len(palette))

    def test_palette_is_never_indexed_directly(self):
        text = IG_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("CLUSTER_COLOURS[int(component) % len(CLUSTER_COLOURS)]", text)
        self.assertEqual(len(re.findall(r"CLUSTER_COLOURS\[", text)), 1)

    def test_figures_render_at_k6_and_beyond(self):
        try:
            import torch  # noqa: F401
            import run_spatial_msipl_gmm_integrated_gradients as ig
        except ImportError as error:  # pragma: no cover - local machines without torch
            self.skipTest(f"IG script not importable here: {error}")
        rng = np.random.default_rng(0)
        mz = np.linspace(100.0, 200.0, 60)
        xs, ys = np.meshgrid(np.arange(1, 13), np.arange(1, 9))
        x, y = xs.reshape(-1), ys.reshape(-1)
        self.assertEqual([ig.cluster_colour(c) for c in range(4)], list(PRODUCTION_PALETTE))
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for k in (6, 9):
                labels = np.arange(len(x)) % k
                ig.save_gmm_figure(labels, rng.uniform(0.5, 1.0, len(x)), x, y, "uniform_mean",
                                   tmp / f"gmm_{k}.png")
                aggregate = {c: {"combined_absolute_mean": rng.random(len(mz))} for c in range(k)}
                ig.save_attribution_figure(mz, aggregate, "central_only", tmp / f"ig_{k}.png")
                records = [{"component": c, "removed_bins": b,
                            "integrated_gradients_mean_posterior_drop": 0.1,
                            "first_layer_l2_mean_posterior_drop": 0.05,
                            "random_mean_posterior_drop": 0.0}
                           for c in range(k) for b in (32, 128)]
                ig.save_faithfulness_figure(records, tmp / f"faith_{k}.png")
                for name in (f"gmm_{k}.png", f"ig_{k}.png", f"faith_{k}.png"):
                    self.assertGreater((tmp / name).stat().st_size, 0, name)


class SyncedProvenanceTests(unittest.TestCase):
    """Read-only, explicit paths: skipped when the results are not synced."""

    def test_existing_bic_selections_were_made_on_the_production_latents(self):
        results = ROOT / "results"
        checked = 0
        for section, arm in sorted(EXISTING_BIC):
            if section.startswith("RCC_"):
                if (section, arm) == ("RCC_UH0505_12", "uniform_mean"):
                    production = (results / "experiments/ig_steps_rerun_20261030"
                                  / "RCC_UH0505_12_seed1/uniform_mean/steps128/attribution")
                    selection = (results / "diagnostics/gate_d_bic_rcc_ig_steps_20261030"
                                 / "RCC_UH0505_12_seed1/uniform_mean/bic_selection.json")
                else:
                    production = results / f"experiments/rcc_spatial_msipl/{section}_seed1/{arm}/attribution"
                    selection = results / f"diagnostics/gate_d_bic_rcc/{section}_seed1/{arm}/bic_selection.json"
            else:
                folder = ("spatial_msipl_gmm_integrated_gradients" if section.startswith("GBM")
                          else "spatial_msipl_cac_gmm_integrated_gradients")
                production = results / f"experiments/{folder}/{section}_seed1/{arm}"
                selection = results / f"diagnostics/gate_d_bic/{section}_seed1/{arm}/bic_selection.json"
            if not (selection.exists() and (production / "latent_mean.npy").exists()):
                continue
            record = resolve_module.resolve(
                json.loads(selection.read_text()),
                resolve_module.sha256(production / "latent_mean.npy"))
            self.assertGreaterEqual(record["label_free_k"], 2)
            checked += 1
        if checked == 0:
            self.skipTest("BIC selections or production latents not synced")


if __name__ == "__main__":
    unittest.main()
