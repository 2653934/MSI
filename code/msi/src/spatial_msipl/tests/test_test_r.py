"""Test R (protocol 18 Section 6.3; supervisor chat 2026-10-17 09:45).

1. Job scripts: the training and IG calls are the production RCC campaign's,
   except that the training seed is the job's SEED; seed 1 is refused, so no
   seed-1 path is ever written; seeds 2/3 go to new roots; the GPU submitter
   excludes the CUDA quarantine with sbatch --exclude; the fair scoring uses the
   seed-1 evaluator arguments, with RCC at bin level only.
2. The K_bin table equals the seed-1 fair-scoring K_bin and the legacy count.
3. summarise_test_r.py: decisions 1-3 and the refuse paths, on synthetic
   summaries.
No existing script is changed, so the seed-1 default paths are untouched by
construction. Dependency-free apart from bash.
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
FAIR = ROOT / "results" / "diagnostics" / "fair_scoring_baselines"
BASH = shutil.which("bash")


def sourced(command, home="/home/test"):
    """Run a command after sourcing test_r_sections.sh, with a fixed HOME."""
    script = f'source "{(JOBS / "test_r_sections.sh").as_posix()}"; {command}'
    return subprocess.run([BASH, "-c", script], capture_output=True, text=True,
                          env=dict(os.environ, HOME=home))


def bash_path(path):
    """A path as bash sees it (Git Bash on Windows wants /c/..., not C:/...)."""
    if os.name != "nt":
        return Path(path).as_posix()
    return subprocess.run([BASH, "-c", 'cygpath -u "$1"', "_", str(path)],
                          capture_output=True, text=True, check=True).stdout.strip()


def block(text, start, end):
    """The command text from `start` to `end`, whitespace-normalised."""
    match = re.search(re.escape(start) + r".*?" + re.escape(end), text, re.DOTALL)
    if match is None:
        raise AssertionError(f"no block {start} ... {end}")
    return " ".join(match.group(0).replace("\\\n", " ").split())


@unittest.skipUnless(BASH, "bash not available")
class JobScriptTests(unittest.TestCase):
    def test_sections_order_and_task_mapping(self):
        result = sourced('echo "${#TEST_R_SECTIONS[@]} ${TEST_R_SECTIONS[0]} '
                         '${TEST_R_SECTIONS[8]} ${TEST_R_SECTIONS[16]} ${TEST_R_ARMS[*]}"')
        self.assertEqual(result.stdout.split(),
                         ["24", "RCC_MH0204_33", "40TopL", "GBM108_negative",
                          "central_only", "uniform_mean"])
        for task, expected in ((0, "RCC_MH0204_33 central_only"),
                               (31, "520TopL uniform_mean"), (47, "GBM39_2 uniform_mean")):
            mapped = sourced(f'echo "${{TEST_R_SECTIONS[{task} / 2]}} ${{TEST_R_ARMS[{task} % 2]}}"')
            self.assertEqual(mapped.stdout.strip(), expected)

    def test_seed_one_is_refused_and_new_roots_carry_the_seed(self):
        for seed in ("1", "4", "x"):
            self.assertNotEqual(sourced(f"test_r_check_seed {seed}").returncode, 0)
        for seed in ("2", "3"):
            self.assertEqual(sourced(f"test_r_check_seed {seed}").returncode, 0)
        root = sourced("test_r_result_root GBM12_1 2 uniform_mean").stdout.strip()
        self.assertEqual(root, "/home/test/msi/results/experiments/test_r_training_seeds/"
                               "GBM12_1_seed2/uniform_mean")
        checkpoint = sourced("test_r_checkpoint_dir RCC_UH0710_33 3 central_only").stdout.strip()
        self.assertEqual(checkpoint, "/datasets/zsuliman/msi_checkpoints/spatial_msipl/test_r/"
                                     "RCC_UH0710_33_seed3/central_only")
        for name in ("run_test_r_campaign.sh", "run_test_r_fair_scoring.sh", "submit_test_r.sh"):
            text = (JOBS / name).read_text()
            self.assertIn("test_r_check_seed", text, name)
            self.assertNotIn("_seed1/$ARM", text, name)

    def test_training_and_ig_calls_equal_the_rcc_campaign_except_the_seed(self):
        new = (JOBS / "run_test_r_campaign.sh").read_text()
        rcc = (JOBS / "run_rcc_campaign.sh").read_text()
        train = ("scripts/train_spatial_msipl_production.py", "--cache-spectra")
        self.assertEqual(block(new, *train),
                         block(rcc, *train).replace("--seed 1 ", '--seed "$SEED" '))
        ig = ("scripts/run_spatial_msipl_gmm_integrated_gradients.py", "--sampling-seed 1")
        self.assertEqual(block(new, *ig).replace('"$GMM_COMPONENTS"', "K"),
                         block(rcc, *ig).replace('"$RCC_GMM_COMPONENTS"', "K"))
        self.assertIn('signature.get("seed") != seed', new)
        self.assertIn("--cache-spectra", new)

    def test_gpu_submitter_excludes_the_quarantine_on_the_command_line(self):
        text = (JOBS / "submit_test_r.sh").read_text()
        self.assertIn("gpu_cuda_quarantine.txt", text)
        self.assertIn('--exclude="$exclude"', text)
        self.assertNotIn("SBATCH_EXCLUDE=", text)
        self.assertIn('concurrency="${concurrency:-3}"', text)  # 2 seeds x 3 <= 6 GPU jobs

    def test_training_phases_are_rcc_and_cac_first_then_gbm(self):
        def sections_of(phase):
            names = sourced(f'for i in $(test_r_expand_indices "$TEST_R_PHASE_{phase}"); do '
                            'echo "${TEST_R_SECTIONS[i / 2]}"; done').stdout.split()
            return names
        first, gbm = sections_of("FIRST"), sections_of("GBM")
        self.assertEqual(len(first), 32)
        self.assertEqual(len(gbm), 16)
        self.assertTrue(all(s.startswith("RCC_") or s.endswith("TopL") for s in first))
        self.assertTrue(all(s.startswith("GBM") for s in gbm))
        both = sourced('test_r_expand_indices "$TEST_R_PHASE_FIRST,$TEST_R_PHASE_GBM"')
        self.assertEqual([int(i) for i in both.stdout.split()], list(range(48)))
        self.assertEqual(sourced("test_r_indices_in_phase first 0-31").returncode, 0)
        self.assertEqual(sourced("test_r_indices_in_phase gbm 32,40-47").returncode, 0)
        for phase, indices in (("first", "30-32"), ("gbm", "31"), ("gbm", "a-b"), ("gbm", ",")):
            self.assertNotEqual(sourced(f"test_r_indices_in_phase {phase} {indices}").returncode,
                                0, (phase, indices))

    def submit(self, *arguments, sacct_states="COMPLETED"):
        """Run submit_test_r.sh with fake sbatch/sacct; it stops before any real call."""
        with tempfile.TemporaryDirectory() as home:
            home = Path(home)
            (home / "msi" / "slurm_jobs").mkdir(parents=True)
            for name in ("test_r_sections.sh", "run_test_r_campaign.sh",
                         "run_test_r_fair_scoring.sh", "gpu_cuda_quarantine.txt"):
                shutil.copy(JOBS / name, home / "msi" / "slurm_jobs")
            fake = home / "bin"
            fake.mkdir()
            (fake / "sbatch").write_text("#!/bin/bash\necho FAKE-SBATCH \"$@\"\n")
            (fake / "sacct").write_text(f"#!/bin/bash\nprintf '%s\\n' {sacct_states}\n")
            for tool in ("sbatch", "sacct"):
                (fake / tool).chmod(0o755)
            environment = dict(os.environ, HOME=bash_path(home),
                               TEST_R_CHECKPOINTS=bash_path(home / "checkpoints"))
            command = (f'export PATH="{bash_path(fake)}:$PATH"; '
                       f'bash "{(JOBS / "submit_test_r.sh").as_posix()}" ' + " ".join(arguments))
            return subprocess.run([BASH, "-c", command], capture_output=True, text=True,
                                  env=environment)

    def test_submitter_enforces_the_phases(self):
        cases = (
            (("train", "2"), "Use train-first, then train-gbm"),
            (("train-first", "2", "--after", "99"), "train-first takes no dependency"),
            (("train-first", "2", "--indices", "30-33"), "outside the first phase"),
            (("train-gbm", "2"), "needs exactly one of"),
            (("train-gbm", "2", "--after", "9", "--after-reviewed", "9"), "needs exactly one of"),
            (("train-gbm", "3", "--indices", "16", "--after", "9"), "outside the gbm phase"),
            (("train-first", "1"), "seeds 2 and 3 only"),
        )
        for arguments, text in cases:
            result = self.submit(*arguments)
            self.assertNotEqual(result.returncode, 0, arguments)
            self.assertIn(text, result.stderr, arguments)
            self.assertNotIn("FAKE-SBATCH", result.stdout, arguments)
        running = self.submit("train-gbm", "2", "--after-reviewed", "9",
                              sacct_states="COMPLETED RUNNING")
        self.assertNotEqual(running.returncode, 0)
        self.assertIn("has not finished", running.stderr)
        # Accepted plans reach the input checks. Without the data (local) they stop
        # there; with it (cluster) the fake sbatch shows the exact submission.
        for arguments, dependency in (
                (("train-gbm", "2", "--after-reviewed", "9"), None),
                (("train-gbm", "3", "--after", "9"), "--dependency=afterok:9"),
                (("train-first", "2"), None)):
            result = self.submit(*arguments, sacct_states="COMPLETED FAILED")
            if "Missing input" in result.stderr:
                self.assertNotIn("FAKE-SBATCH", result.stdout)
                continue
            self.assertEqual(result.returncode, 0, result.stderr)
            call = next(l for l in result.stdout.splitlines() if l.startswith("FAKE-SBATCH"))
            phase = "32-47" if arguments[0] == "train-gbm" else "0-31"
            self.assertIn(f"--array={phase}%3", call)
            self.assertIn("--exclude=", call)
            self.assertEqual("--dependency" in call, dependency is not None, call)
            if dependency:
                self.assertIn(dependency, call)

    def test_fair_scoring_uses_the_seed1_evaluator_arguments(self):
        text = (JOBS / "run_test_r_fair_scoring.sh").read_text()
        self.assertIn("scripts/evaluate_fair_scoring_baselines.py", text)
        self.assertIn("--random-draws 100 --chunk-size 1024", text)
        self.assertIn("SCOPES=(bin_level_only)\n", text)  # RCC: bin level only
        self.assertIn("--no-legacy --reference-budget", text)
        self.assertNotIn("--class-subset", text)

    def test_k_bin_table_matches_seed1_fair_scoring_and_legacy(self):
        sections = sourced('echo "${TEST_R_SECTIONS[@]:8}"').stdout.split()
        self.assertEqual(len(sections), 16)
        checked = legacy_checked = 0
        for section in sections:
            k_bin = int(sourced(f"test_r_k_bin {section}").stdout)
            for arm in ("central_only", "uniform_mean"):
                path = FAIR / "with_approved_partitions" / f"{section}_seed1" / arm / "summary.json"
                if path.is_file():
                    self.assertEqual(json.loads(path.read_text())["K_bin"], k_bin, section)
                    checked += 1
            # The legacy folder relative to the workspace (HOME/msi -> ROOT).
            legacy = sourced(f"test_r_legacy_dir {section}").stdout.strip()
            relative = legacy.replace("/home/test/msi/", "")
            self.assertTrue(relative.startswith("results/baselines/msipl/"), legacy)
            metrics = ROOT / relative / "peak_metrics.json"
            if metrics.is_file():
                self.assertEqual(json.loads(metrics.read_text())["unique_nearest_bins"], k_bin)
                legacy_checked += 1
        if checked == 0:
            self.skipTest("seed-1 fair-scoring summaries not present in this workspace")
        self.assertEqual((checked, legacy_checked), (32, 16))


# ----- summariser -----
sys.path.insert(0, str(SCRIPTS))
from summarise_test_r import SECTIONS  # noqa: E402

PREFIX = "/home-mscluster/zsuliman/msi/"


def write_summary(fair_root, project_root, collection, section, arm, seed, ig, posterior,
                  morans=0.5, code="h", k_bin=100, attribution=None, p1=True,
                  balanced_accuracy=0.8):
    if seed == 1:
        scope = fair_root / ("rcc/bin_level_only" if collection == "RCC"
                             else "with_approved_partitions")
        attribution = attribution or f"{PREFIX}results/experiments/x/{section}_seed1/{arm}"
    else:
        scope = fair_root / "test_r" / ("bin_level_only" if collection == "RCC"
                                        else "with_approved_partitions")
        attribution = attribution or (f"{PREFIX}results/experiments/test_r_training_seeds/"
                                      f"{section}_seed{seed}/{arm}/attribution")
    evaluation = f"results/eval/{section}_seed{seed}_{arm}/summary.json"
    local = project_root / evaluation
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(json.dumps({"cluster_mapping": {"balanced_accuracy": balanced_accuracy}}))
    methods = {"integrated_gradients": ig, "posterior_abs_pcc_balanced": posterior,
               "morans_i": morans}
    summary = {
        "status": "complete", "dataset": section, "K_bin": k_bin,
        "provenance": {"evaluation_version": 4, "parameters": {"p": 1},
                       "partition_approval": None, "code": {"x": code},
                       "source_artifacts": {
                           "latent_mean": {"path": f"{attribution}/latent_mean.npy"},
                           "saved_evaluation_summary": {"path": PREFIX + evaluation}}},
        "bin_level": {name: {"1.0": {"mSCF1": v}} for name, v in methods.items()},
        "peak_level": {},
    }
    if p1 and collection != "RCC":
        summary["peak_level"]["P1"] = {"methods": {
            name: {"matched_K_peak": {"mSCF1": v}} for name, v in methods.items()}}
    target = scope / f"{section}_seed{seed}" / arm
    target.mkdir(parents=True, exist_ok=True)
    (target / "summary.json").write_text(json.dumps(summary))
    return target / "summary.json"


class SummariserTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.fair = self.project / "fair"
        self.output = self.project / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def fill(self, gap=-0.1, context=0.0, skip=()):
        """Every collection x arm x seed: IG = posterior + gap; uniform IG += context."""
        for collection, sections in SECTIONS.items():
            for section in sections:
                for arm in ("central_only", "uniform_mean"):
                    for seed in (1, 2, 3):
                        if (collection, section, arm, seed) in skip:
                            continue
                        ig = 0.5 + gap + (context if arm == "uniform_mean" else 0.0)
                        write_summary(self.fair, self.project, collection, section, arm,
                                      seed, ig, 0.5 + (context if arm == "uniform_mean" else 0))

    def summarise(self, check=True):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "summarise_test_r.py"), "--fair-root", self.fair,
             "--project-root", self.project, "--output", self.output],
            capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(SCRIPTS)))
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads((self.output / "decisions.json").read_text())
        return result

    def set_ig(self, collection, section, arm, seed, ig, posterior=0.5, **extra):
        write_summary(self.fair, self.project, collection, section, arm, seed, ig, posterior,
                      **extra)

    def test_headline_holds_when_every_complete_seed_replicates(self):
        self.fill(gap=-0.1)
        decisions = self.summarise()
        d1 = decisions["decision_1"]
        self.assertTrue(d1["headline_holds_overall"])
        self.assertEqual(d1["failures"], [])
        self.assertEqual(d1["per_collection_arm_seed"]["GBM/uniform_mean/seed2"]["label"],
                         "replicates")
        self.assertEqual(d1["per_collection_arm_seed"]["RCC/central_only/seed3"]
                         ["IG_minus_posterior"].keys(), {"bin"})

    def test_six_of_eight_below_or_a_small_mean_does_not_replicate(self):
        self.fill(gap=-0.1)
        for section in SECTIONS["CAC"][:2]:  # two sections above posterior at seed 2
            self.set_ig("CAC", section, "central_only", 2, 0.6)
        for section in SECTIONS["RCC"]:      # all below, but mean -0.019 at seed 3
            self.set_ig("RCC", section, "uniform_mean", 3, 0.481)
        d1 = self.summarise()["decision_1"]
        self.assertFalse(d1["headline_holds_overall"])
        self.assertEqual(sorted(d1["failures"]),
                         ["CAC/central_only/seed2", "RCC/uniform_mean/seed3"])

    def test_gbm_needs_p1_too(self):
        self.fill(gap=-0.1)
        for section in SECTIONS["GBM"]:
            path = self.fair / "test_r/with_approved_partitions" / f"{section}_seed3" / \
                "central_only" / "summary.json"
            summary = json.loads(path.read_text())
            summary["peak_level"]["P1"]["methods"]["integrated_gradients"]["matched_K_peak"][
                "mSCF1"] = 0.49  # P1 mean -0.01: below in 8/8 but not <= -0.02
            path.write_text(json.dumps(summary))
        d1 = self.summarise()["decision_1"]
        self.assertEqual(d1["failures"], ["GBM/central_only/seed3"])

    def test_incomplete_seed_is_listed_and_excluded_from_the_headline(self):
        self.fill(gap=-0.1, skip={("RCC", "RCC_UH0505_12", "uniform_mean", 2)})
        d1 = self.summarise()["decision_1"]
        self.assertTrue(d1["headline_holds_overall"])
        self.assertEqual(d1["incomplete"], ["RCC/uniform_mean/seed2: incomplete (7/8 sections)"])

    def test_context_uses_the_three_seed_average_and_reports_each_seed(self):
        self.fill(gap=-0.1, context=0.0)
        # GBM: seed 1 context +0.05 everywhere ("helps" at seed 1), seeds 2/3 0.0; mean 0.0167.
        for section in SECTIONS["GBM"]:
            self.set_ig("GBM", section, "uniform_mean", 1, 0.45, posterior=0.5)
        d2 = self.summarise()["decision_2"]["GBM"]
        self.assertEqual(d2["seed1_label"], "helps")
        self.assertEqual(d2["three_seed_label"], "equivalent")
        self.assertTrue(d2["labels_differ"])
        self.assertTrue(d2["seed1_label_superseded_by_three_seed_label"])
        sd = d2["per_section_seed_sd"]["bin"]["GBM12_1"]
        self.assertAlmostEqual(sd, float(np.std([0.05, 0.0, 0.0], ddof=1)), places=12)
        self.assertEqual(d2["per_seed_labels"]["seed2"], "equivalent")

    def test_context_is_incomplete_without_all_three_seeds(self):
        self.fill(gap=-0.1, skip={("RCC", "RCC_UH0505_12", "uniform_mean", 1)})
        d2 = self.summarise()["decision_2"]["RCC"]
        self.assertEqual(d2["three_seed_label"], "incomplete (7/8 sections)")
        self.assertEqual(d2["per_seed_labels"]["seed1"], "incomplete (7/8 sections)")

    def test_descriptive_sd_balanced_accuracy_and_rcc_morans(self):
        self.fill(gap=-0.1)
        self.set_ig("RCC", "RCC_UH0710_33", "central_only", 2, 0.4, morans=0.3,
                    balanced_accuracy=0.6)
        d3 = self.summarise()["decision_3"]["RCC/central_only"]
        sd = d3["seed_sd"]["bin:integrated_gradients"]["per_section"]["RCC_UH0710_33"]
        self.assertEqual(sd["seeds"], 3)
        self.assertAlmostEqual(sd["sd"], float(np.std([0.4, 0.4, 0.4], ddof=1)))
        accuracy = d3["gmm_balanced_accuracy"]["seed2"]
        self.assertAlmostEqual(accuracy["mean"], (7 * 0.8 + 0.6) / 8)
        morans = d3["morans_i_minus_posterior_bin"]["seed2"]
        self.assertEqual((morans["sections"], morans["negative_sections"]), (8, 1))

    def assert_refused(self, text):
        result = self.summarise(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(text, result.stderr)
        self.assertFalse((self.output / "decisions.json").exists())

    def test_mixed_code_within_a_seed_and_collection_is_refused(self):
        self.fill(gap=-0.1)
        self.set_ig("CAC", "40TopL", "central_only", 2, 0.4, code="other")
        self.assert_refused("different evaluator code")

    def test_k_bin_that_differs_between_seeds_is_refused(self):
        self.fill(gap=-0.1)
        self.set_ig("GBM", "GBM12_1", "central_only", 3, 0.4, k_bin=101)
        self.assert_refused("K_bin differs between seeds")

    def test_attribution_from_the_wrong_seed_root_is_refused(self):
        self.fill(gap=-0.1)
        self.set_ig("CAC", "40TopL", "uniform_mean", 2, 0.4,
                    attribution=f"{PREFIX}results/experiments/test_r_training_seeds/"
                                "40TopL_seed3/uniform_mean/attribution")
        self.assert_refused("is not the seed-2 root")

    def test_p1_missing_on_cac_or_present_on_rcc_is_refused(self):
        self.fill(gap=-0.1)
        self.set_ig("CAC", "40TopL", "uniform_mean", 2, 0.4, p1=False)
        self.assert_refused("P1 missing for CAC")
        shutil.rmtree(self.fair)
        self.fill(gap=-0.1)
        path = self.fair / "test_r/bin_level_only/RCC_MH0204_33_seed2/central_only/summary.json"
        summary = json.loads(path.read_text())
        summary["peak_level"]["P1"] = {"methods": {}}
        path.write_text(json.dumps(summary))
        self.assert_refused("P1 present for RCC")


if __name__ == "__main__":
    unittest.main()
