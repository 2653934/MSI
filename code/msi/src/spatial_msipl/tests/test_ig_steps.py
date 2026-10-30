"""IG completeness reruns (protocol 18 Section 6.3 amendment "30 October: IG
completeness reruns"; supervisor chat 2026-10-30 12:58 item 1 and 13:30 ruling).

1. Job scripts: the task table equals the summariser's; outputs go to new
   dated roots, never into a saved seed folder; the IG call is the RCC campaign's
   except --ig-steps and --align-gmm-labels-to-production; the matched evaluation
   and fair-scoring calls are Test R's; no training call and no --exclusive; the
   GPU submitter excludes the CUDA quarantine on the sbatch command line; both
   array jobs refuse an existing output (exit 3) before doing anything.
2. The saved 64-step summaries: the four rerun arms fail completeness, the four
   controls pass, and every saved checkpoint path equals the task table's.
3. summarise_ig_steps.py on a synthetic tree: the decision step count, the GMM
   gate, the control comparisons (delta mSCF1, Jaccard, reproduction flag) and
   the refusal of an existing output.
Dependency-free apart from bash and NumPy.
"""

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

ROOT = Path(__file__).resolve().parents[3]
JOBS = ROOT / "slurm_jobs"
SCRIPTS = ROOT / "scripts"
BASH = shutil.which("bash")
sys.path.insert(0, str(SCRIPTS))
import summarise_ig_steps as summary_module  # noqa: E402


def bash_path(path):
    """A path as bash sees it (Git Bash on Windows wants /c/..., not C:/...)."""
    if os.name != "nt":
        return Path(path).as_posix()
    return subprocess.run([BASH, "-c", 'cygpath -u "$1"', "_", str(path)],
                          capture_output=True, text=True, check=True).stdout.strip()


def fake_home():
    """A temporary HOME whose msi/slurm_jobs holds copies of the job scripts."""
    home = Path(tempfile.mkdtemp())
    shutil.copytree(JOBS, home / "msi" / "slurm_jobs")
    return home


def sourced(command, home):
    script = f'source "$HOME/msi/slurm_jobs/ig_steps_sections.sh"; {command}'
    return subprocess.run([BASH, "-c", script], capture_output=True, text=True,
                          env=dict(os.environ, HOME=bash_path(home)))


def block(text, start, end):
    """The command text from `start` to `end`, whitespace-normalised."""
    match = re.search(re.escape(start) + r".*?" + re.escape(end), text, re.DOTALL)
    if match is None:
        raise AssertionError(f"no block {start} ... {end}")
    return " ".join(match.group(0).replace("\\\n", " ").split())


@unittest.skipUnless(BASH, "bash not available")
class JobScriptTests(unittest.TestCase):
    def setUp(self):
        self.home = fake_home()
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)

    def table(self):
        result = sourced('for row in "${IG_STEPS_TASKS[@]}"; do echo "$row"; done', self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = []
        for line in result.stdout.splitlines():
            section, seed, arm, steps, kind = line.split()
            rows.append((section, int(seed), arm, int(steps), kind))
        return rows

    def test_task_table_equals_the_summariser_and_the_amendment(self):
        rows = self.table()
        self.assertEqual(tuple(rows), summary_module.TASKS)
        failed = {("RCC_UH0505_12", 1, "uniform_mean"), ("RCC_UH0505_12", 2, "central_only"),
                  ("RCC_UH9912_01", 3, "uniform_mean"), ("GBM39_2", 3, "uniform_mean")}
        controls = {("RCC_UH0505_12", 1, "central_only"), ("RCC_UH9912_01", 1, "uniform_mean"),
                    ("GBM39_2", 1, "uniform_mean"), ("40TopL", 1, "uniform_mean")}
        self.assertEqual({r[:3] for r in rows[0:4]}, failed)
        self.assertEqual({r[3] for r in rows[0:4]} | {r[4] for r in rows[0:4]}, {128, "rerun"})
        self.assertEqual({r[:3] for r in rows[4:8]}, controls)
        self.assertEqual({(r[3], r[4]) for r in rows[4:8]}, {(64, "control")})
        self.assertEqual({r[:3] for r in rows[8:12]}, controls)
        self.assertEqual({(r[3], r[4]) for r in rows[8:12]}, {(128, "control")})
        self.assertEqual([r[:3] for r in rows[12:16]], [r[:3] for r in rows[0:4]])
        self.assertEqual({(r[3], r[4]) for r in rows[12:16]}, {(256, "rerun")})
        self.assertNotEqual(sourced("ig_steps_task 16", self.home).returncode, 0)

    def test_new_roots_are_dated_and_saved_paths_match_the_summariser(self):
        home_posix = bash_path(self.home)
        for index, (section, seed, arm, steps, kind) in enumerate(summary_module.TASKS):
            result = sourced(
                f'ig_steps_task {index}; '
                'ig_steps_result_root "$TASK_SECTION" "$TASK_SEED" "$TASK_ARM" "$TASK_STEPS" "$TASK_KIND"; '
                'ig_steps_saved_attribution "$TASK_SECTION" "$TASK_SEED" "$TASK_ARM"; '
                'ig_steps_fair_output bin_level_only "$TASK_SECTION" "$TASK_SEED" "$TASK_ARM" "$TASK_STEPS"',
                self.home)
            self.assertEqual(result.returncode, 0, result.stderr)
            root, saved, fair = result.stdout.splitlines()
            project = Path(home_posix) / "msi"
            self.assertEqual(root, summary_module.result_root(
                project, section, seed, arm, steps, kind).as_posix())
            self.assertEqual(saved, summary_module.saved_attribution(
                project, section, seed, arm).as_posix())
            self.assertEqual(fair, summary_module.rerun_fair_bin_level(
                project, section, seed, arm, steps).as_posix())
            self.assertRegex(root, r"/results/experiments/ig_steps_(rerun|control)_20261030/")
            self.assertRegex(fair, r"/fair_scoring_baselines/ig_steps_20261030/")
            self.assertFalse(root.startswith(saved.rsplit("/attribution", 1)[0] + "/"))

    def test_ig_call_is_the_rcc_campaign_call_except_steps_and_alignment(self):
        campaign = block((JOBS / "run_rcc_campaign.sh").read_text(),
                         "scripts/run_spatial_msipl_gmm_integrated_gradients.py", "--sampling-seed 1")
        rerun = block((JOBS / "run_ig_steps_rerun.sh").read_text(),
                      "scripts/run_spatial_msipl_gmm_integrated_gradients.py",
                      '--align-gmm-labels-to-production "$SAVED"')
        campaign = (campaign.replace('"$RESULT_ROOT/attribution"', '"$ROOT/attribution"')
                    .replace('"$RCC_GMM_COMPONENTS"', '"$GMM_COMPONENTS"')
                    .replace("--ig-steps 64", '--ig-steps "$STEPS"'))
        self.assertEqual(rerun, campaign + ' --align-gmm-labels-to-production "$SAVED"')

    def test_matched_evaluation_and_fair_scoring_calls_are_test_r_calls(self):
        test_r = block((JOBS / "run_test_r_campaign.sh").read_text(),
                       "scripts/evaluate_spatial_msipl_attributed_peaks.py", "--chunk-size 1024")
        rerun = block((JOBS / "run_ig_steps_rerun.sh").read_text(),
                      "scripts/evaluate_spatial_msipl_attributed_peaks.py", "--chunk-size 1024")
        self.assertEqual(rerun, test_r.replace('"$RESULT_ROOT/attribution"', '"$ROOT/attribution"'))
        test_r_fair = block((JOBS / "run_test_r_fair_scoring.sh").read_text(),
                            "scripts/evaluate_fair_scoring_baselines.py", "--chunk-size 1024")
        fair = block((JOBS / "run_ig_steps_fair_scoring.sh").read_text(),
                     "scripts/evaluate_fair_scoring_baselines.py", "--chunk-size 1024")
        self.assertEqual(fair, test_r_fair.replace('"$attribution"', '"$ROOT/attribution"')
                         .replace('"$saved"', '"$SAVED"'))
        for name in ("run_test_r_fair_scoring.sh", "run_ig_steps_fair_scoring.sh"):
            text = (JOBS / name).read_text()
            self.assertIn("SCOPES=(bin_level_only)\n", text)
            self.assertIn('--no-legacy --reference-budget "$(test_r_rcc_budget "$DATASET")"', text)

    def test_no_training_no_exclusive_and_quarantine_on_the_command_line(self):
        rerun = (JOBS / "run_ig_steps_rerun.sh").read_text()
        self.assertNotIn("train_spatial_msipl_production", rerun)
        self.assertNotIn("#SBATCH --exclusive", rerun)
        self.assertIn("#SBATCH --partition=bigbatch", rerun)
        self.assertIn("#SBATCH --partition=batch", (JOBS / "run_ig_steps_fair_scoring.sh").read_text())
        submitter = (JOBS / "submit_ig_steps.sh").read_text()
        self.assertIn('sbatch_options+=(--exclude="$exclude")', submitter)
        self.assertIn("gpu_cuda_quarantine.txt", submitter)
        self.assertIn("sbatch --parsable", submitter)
        self.assertNotIn("SBATCH_EXCLUDE", submitter)

    def run_job(self, name, task):
        return subprocess.run(
            [BASH, bash_path(self.home / "msi" / "slurm_jobs" / name)],
            capture_output=True, text=True,
            env=dict(os.environ, HOME=bash_path(self.home), SLURM_ARRAY_TASK_ID=str(task),
                     SLURM_ARRAY_JOB_ID="1"))

    def test_rerun_job_refuses_an_existing_output_before_anything_runs(self):
        section, seed, arm, steps, kind = summary_module.TASKS[0]
        root = summary_module.result_root(self.home / "msi", section, seed, arm, steps, kind)
        (root / "attribution").mkdir(parents=True)
        result = self.run_job("run_ig_steps_rerun.sh", 0)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("never overwritten", result.stderr)
        self.assertEqual(sorted(p.name for p in root.iterdir()), ["attribution"])

    def test_fair_job_refuses_an_existing_output(self):
        section, seed, arm, steps, kind = summary_module.TASKS[7]
        output = summary_module.rerun_fair_bin_level(self.home / "msi", section, seed, arm, steps)
        output.mkdir(parents=True)
        result = self.run_job("run_ig_steps_fair_scoring.sh", 7)
        self.assertEqual(result.returncode, 3, result.stderr)


class SavedRunTests(unittest.TestCase):
    """The saved 64-step summaries (read explicitly, never written)."""

    def summary(self, section, seed, arm):
        path = summary_module.saved_attribution(ROOT, section, seed, arm) / "summary.json"
        if not path.exists():
            self.skipTest(f"saved summary not synced: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_rerun_arms_fail_and_controls_pass_at_64_steps(self):
        for section, seed, arm, steps, kind in summary_module.TASKS:
            saved = self.summary(section, seed, arm)
            self.assertEqual(saved["integrated_gradients"]["steps"], 64)
            self.assertEqual(saved["integrated_gradients"]["completeness"]["passed"],
                             kind == "control", (section, seed, arm))
            self.assertEqual(saved["gmm"]["seed"], 1)
            self.assertEqual(saved["integrated_gradients"]["sampling_seed"], 1)

    @unittest.skipUnless(BASH, "bash not available")
    def test_checkpoint_paths_equal_the_saved_summaries(self):
        home = fake_home()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        for index, (section, seed, arm, steps, kind) in enumerate(summary_module.TASKS):
            saved = self.summary(section, seed, arm)
            result = sourced(f'ig_steps_task {index}; '
                             'ig_steps_checkpoint "$TASK_SECTION" "$TASK_SEED" "$TASK_ARM"', home)
            self.assertEqual(result.stdout.strip(), saved["checkpoint"])


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def attribution_summary(steps, passed, p95):
    return {"status": "valid" if passed else "needs_more_ig_steps",
            "integrated_gradients": {"steps": steps, "completeness": {
                "passed": passed, "median_normalized_residual": 0.001,
                "percentile_95_normalized_residual": p95}}}


def fair_output(folder, k_bin, score, bins):
    write_json(folder / "summary.json", {
        "status": "complete", "K_bin": k_bin,
        "bin_level": {"integrated_gradients": {"1.0": {"mSCF1": score}}}})
    np.savez(folder / "rankings_prefix.npz", integrated_gradients=np.asarray(bins, dtype=np.int64))


def gate(passed=True):
    return {"passed": passed, "identity_permutation": passed, "model_state_equal": True,
            "hard_assignment_equal": passed, "alignment_max_posterior_diff": 1e-6,
            "descriptive": {"latent_mean_max_abs_diff": 0.0, "assigned_posterior_max_abs_diff": 0.0,
                            "gmm_parameters_max_abs_diff": {"component_means": 0.0}}}


class SummariserTests(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        seen = set()
        for section, seed, arm, steps, kind in summary_module.TASKS:
            if (section, seed, arm) not in seen:
                seen.add((section, seed, arm))
                write_json(summary_module.saved_attribution(self.project, section, seed, arm)
                           / "summary.json", attribution_summary(64, kind == "control", 0.2))
                if kind == "control":
                    fair_output(summary_module.saved_fair_bin_level(self.project, section, seed, arm),
                                4, 0.40, [0, 1, 2, 3, 9])

    def add_rerun(self, index, passed=True, gate_passed=True, fair=None):
        section, seed, arm, steps, kind = summary_module.TASKS[index]
        root = summary_module.result_root(self.project, section, seed, arm, steps, kind)
        write_json(root / "gmm_gate.json", gate(gate_passed))
        write_json(root / "attribution" / "summary.json", attribution_summary(steps, passed, 0.1))
        if fair is not None:
            fair_output(summary_module.rerun_fair_bin_level(self.project, section, seed, arm, steps),
                        4, *fair)

    def test_decision_steps(self):
        self.add_rerun(0, passed=True)                      # 128 passes
        self.add_rerun(1, passed=False)                     # 128 fails, 256 passes
        self.add_rerun(13, passed=True)
        self.add_rerun(2, passed=False)                     # 128 and 256 fail
        self.add_rerun(14, passed=False)
        self.add_rerun(3, passed=True, gate_passed=False)   # GMM gate fails
        decisions = summary_module.summarise(self.project)["decision_steps"]
        self.assertEqual(decisions["RCC_UH0505_12 s1 uniform_mean"], 128)
        self.assertEqual(decisions["RCC_UH0505_12 s2 central_only"], 256)
        self.assertEqual(decisions["RCC_UH9912_01 s3 uniform_mean"], "not done")
        self.assertTrue(decisions["GBM39_2 s3 uniform_mean"].startswith("GMM gate failed"))

    def test_pending_when_a_step_count_has_no_output(self):
        self.add_rerun(1, passed=False)
        decisions = summary_module.summarise(self.project)["decision_steps"]
        self.assertEqual(decisions["RCC_UH0505_12 s2 central_only"], "pending")
        self.assertEqual(decisions["RCC_UH0505_12 s1 uniform_mean"], "pending")

    def test_control_comparisons_and_reproduction_flag(self):
        for index in (4, 5, 7):    # 64-step reruns identical to saved
            self.add_rerun(index, fair=(0.40, [0, 1, 2, 3, 9]))
        self.add_rerun(6, fair=(0.39, [0, 1, 2, 5, 9]))     # GBM39_2: one bin swapped
        for index in (8, 9, 10, 11):
            self.add_rerun(index, fair=(0.41, [0, 1, 2, 4, 9]))
        controls = {c["section"]: c for c in summary_module.summarise(self.project)["controls"]}
        rcc = controls["RCC_UH0505_12"]
        self.assertTrue(rcc["rerun64_reproduces_saved"])
        self.assertAlmostEqual(rcc["rerun128_vs_saved64"]["delta_mSCF1"], 0.01)
        self.assertAlmostEqual(rcc["rerun128_vs_saved64"]["jaccard"], 3 / 5)   # first 4 bins
        self.assertEqual(rcc["rerun128_vs_saved64"]["bins_only_in_reference_ranks"], [4])
        gbm = controls["GBM39_2"]
        self.assertFalse(gbm["rerun64_reproduces_saved"])
        self.assertAlmostEqual(gbm["rerun64_vs_saved64"]["delta_mSCF1"], -0.01)
        self.assertAlmostEqual(gbm["rerun128_vs_rerun64"]["jaccard"], 3 / 5)

    def test_small_delta_with_identical_set_reproduces(self):
        reference = (4, 0.400, np.array([0, 1, 2, 3]))
        result = summary_module.compare(reference, (4, 0.404, np.array([1, 0, 2, 3])))
        self.assertEqual(result["jaccard"], 1.0)
        self.assertEqual(result["bins_only_in_reference_ranks"], [])

    def test_missing_control_output_is_reported_not_guessed(self):
        controls = summary_module.summarise(self.project)["controls"]
        self.assertTrue(all(c["status"].startswith("missing") for c in controls))

    def test_existing_output_is_refused(self):
        output = self.project / "out"
        output.mkdir()
        result = subprocess.run([sys.executable, str(SCRIPTS / "summarise_ig_steps.py"),
                                 "--project-root", str(self.project), "--output", str(output)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 3, result.stderr)


if __name__ == "__main__":
    unittest.main()
