"""msiPL Beta re-tune (protocol 18 Section 6.8; supervisor chat 2026-10-30 12:58 item 2
and 17:33 ruling).

1. retune_msipl_beta.py: the selection rule (closest raw count, ties to the larger Beta,
   tolerance 50; msipl_cap above the grid maximum; closest_outside_tolerance otherwise),
   targets equal simple_baselines.budgets, the grid is the existing tuner's beta_grid
   over -2.0..2.5 step 0.01 (451 values), the legacy functions are imported from the
   existing tuner modules, argument pairing, and refusal of an existing output.
2. score_msipl_retune.py: the prefix gate, count-matched scoring, refusal of an
   existing output, and the evaluator functions are imported (production evaluator
   unchanged).
3. summarise_msipl_retune.py on a synthetic tree: clause 3 at every multiplier, capped
   flags, the overall rule, the RCC count-matched table and the refusals.
4. Job scripts: batch, no --exclusive, msipl_legacy for the sweep, new roots, the
   RCC_UH0505_12 uniform rerun paths, the GBM22_2 pilot index, refusal of existing
   outputs, and (with local files) K_bin equal to the saved legacy unique count.
Dependency-free apart from bash, NumPy and the fair-scoring modules.
"""

import ast
import json
import os
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
import retune_msipl_beta as retune  # noqa: E402
import summarise_msipl_retune as summary_module  # noqa: E402
from spatial_msipl.simple_baselines import budgets  # noqa: E402


def bash_path(path):
    if os.name != "nt":
        return Path(path).as_posix()
    return subprocess.run([BASH, "-c", 'cygpath -u "$1"', "_", str(path)],
                          capture_output=True, text=True, check=True).stdout.strip()


def function_from(path, name):
    """Compile one top-level function of a script without importing the script."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


def records(counts):
    return [{"beta": beta, "selected_peaks": count} for beta, count in counts]


class SelectionTests(unittest.TestCase):
    def test_closest_within_tolerance_with_ties_to_the_larger_beta(self):
        sweep = records([(2.0, 400), (1.5, 500), (1.4, 520), (1.3, 480)])
        chosen, status = retune.select(sweep, 500)
        self.assertEqual((chosen["beta"], status), (1.5, "within_tolerance"))
        chosen, status = retune.select(sweep, 490)   # 480 and 500 tie at 10
        self.assertEqual((chosen["beta"], status), (1.5, "within_tolerance"))

    def test_target_above_the_grid_maximum_is_capped_at_the_maximum(self):
        sweep = records([(0.1, 1150), (0.0, 1154), (-0.5, 1154), (-2.0, 1153)])
        chosen, status = retune.select(sweep, 2200)
        self.assertEqual((chosen["beta"], chosen["selected_peaks"], status),
                         (0.0, 1154, "msipl_cap"))
        chosen, status = retune.select(sweep, 1190)  # within tolerance of the maximum
        self.assertEqual(status, "within_tolerance")

    def test_gap_or_below_the_minimum_is_closest_outside_tolerance(self):
        sweep = records([(2.5, 300), (1.0, 900)])
        self.assertEqual(retune.select(sweep, 600)[1], "closest_outside_tolerance")
        chosen, status = retune.select(sweep, 100)
        self.assertEqual((chosen["beta"], status), (2.5, "closest_outside_tolerance"))

    def test_targets_equal_the_fair_scoring_budgets(self):
        for k_bin in (133, 315, 584, 911, 1028, 1448, 2013, 2200):
            expected = budgets(k_bin, 10 ** 6)
            for multiplier in retune.MULTIPLIERS:
                self.assertEqual(retune.target_for(k_bin, multiplier), expected[str(multiplier)])
                self.assertEqual(retune.label(multiplier), "m" + str(multiplier))

    def test_grid_is_the_existing_tuners_beta_grid_over_the_ruled_range(self):
        beta_grid = function_from(SCRIPTS / "tune_msipl_massnet_beta.py", "beta_grid")
        grid = beta_grid(*retune.GRID)
        self.assertEqual(retune.GRID, (-2.0, 2.5, 0.01))
        self.assertEqual(len(grid), 451)
        self.assertEqual((max(grid), min(grid)), (2.5, -2.0))
        self.assertEqual(retune.TOLERANCE, 50)

    def test_legacy_functions_come_from_the_existing_tuner_modules(self):
        text = (SCRIPTS / "retune_msipl_beta.py").read_text(encoding="utf-8")
        self.assertIn("from run_msipl_legacy_gbm import VAE_BN, LearnPeaks, load_dataset, "
                      "tic_normalise", text)
        self.assertIn("from tune_msipl_massnet_beta import beta_grid", text)
        # Python 3.6 (msipl_legacy): the script must at least parse under 3.6 grammar.
        ast.parse(text, feature_version=(3, 6))

    def test_arguments_and_existing_output(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        base = [sys.executable, str(SCRIPTS / "retune_msipl_beta.py"), "--input", "x.h5",
                "--weights", "w.h5", "--output", str(tmp), "--k-bin", "100"]
        result = subprocess.run(base + ["--saved-beta", "1.0"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        (tmp / "summary.json").write_text("{}")
        result = subprocess.run(base, capture_output=True, text=True)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual((tmp / "summary.json").read_text(), "{}")


class SweepLearnPeaksTests(unittest.TestCase):
    """The once-per-section fast path equals LearnPeaks at every Beta of the ruled grid."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "baselines" / "msipl"))
        from LearnPeaks import LearnPeaks
        cls.legacy = staticmethod(LearnPeaks)
        cls.grid = function_from(SCRIPTS / "tune_msipl_massnet_beta.py", "beta_grid")(
            *retune.GRID)

    def case(self, seed, bins, dtype, integer_mz=False):
        rng = np.random.default_rng(seed)
        if integer_mz:   # evenly spaced m/z: equidistant local maxima, argmin ties
            mz = np.arange(100, 100 + bins).astype(dtype)
        else:
            mz = np.sort(rng.uniform(100, 1000, bins)).astype(dtype)
        weights = [rng.normal(size=(bins, 16)).astype(dtype)] + [None] * 5 + \
            [rng.normal(size=(16, 5)).astype(dtype)]
        return (mz, weights, rng.random(bins).astype(dtype), 5,
                rng.random(bins).astype(dtype))

    def assert_identical_over_grid(self, mz, weights, deviation, latent, mean):
        fast = retune.SweepLearnPeaks(mz, weights, deviation, latent, mean, chunk=37)
        counts = set()
        for beta in self.grid:
            _, expected, _, _ = self.legacy(mz, weights, deviation, latent, beta, mean)
            got = fast(beta)
            self.assertEqual(got.dtype, np.asarray(expected).dtype, beta)
            np.testing.assert_array_equal(got, expected, err_msg=str(beta))
            counts.add(got.size)
        self.assertGreater(len(counts), 20)   # the grid really spans many list sizes

    def test_identical_to_learnpeaks_float64(self):
        self.assert_identical_over_grid(*self.case(0, 600, np.float64))

    def test_identical_to_learnpeaks_float32(self):
        self.assert_identical_over_grid(*self.case(1, 600, np.float32))

    def test_identical_with_equidistant_ties(self):
        self.assert_identical_over_grid(*self.case(2, 500, np.float64, integer_mz=True))

    def test_job_uses_fast_path_with_legacy_check(self):
        source = (SCRIPTS / "retune_msipl_beta.py").read_text(encoding="utf-8")
        self.assertIn("peaks = sweep_learn(beta)", source)
        self.assertIn("check_betas = [GRID[1], 0.0, GRID[0]]", source)
        self.assertIn("fast_path_check.json", source)
        self.assertIn("fast_path_check.json", (JOBS / "run_msipl_retune_sweep.sh").read_text())


class ScorerTests(unittest.TestCase):
    def setUp(self):
        import score_msipl_retune
        self.scorer = score_msipl_retune

    def test_prefix_gate(self):
        rankings = {"a": np.array([3, 1, 2, 0]), "b": np.array([0, 1, 2, 3])}
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        np.savez(tmp / "ok.npz", a=np.array([3, 1]), b=np.array([0, 1, 2]))
        self.assertEqual(self.scorer.check_prefixes(rankings, np.load(tmp / "ok.npz")),
                         {"a": 2, "b": 3})
        np.savez(tmp / "bad.npz", a=np.array([1, 3]))
        with self.assertRaises(ValueError):
            self.scorer.check_prefixes(rankings, np.load(tmp / "bad.npz"))
        np.savez(tmp / "extra.npz", c=np.array([0]))
        with self.assertRaises(ValueError):
            self.scorer.check_prefixes(rankings, np.load(tmp / "extra.npz"))

    def test_count_matched_scores_every_ranking_at_the_legacy_count(self):
        n_bins = 10
        correlations = {0: np.linspace(-1, 1, n_bins), 1: np.linspace(1, -1, n_bins)}
        legacy = np.array([0, 9, 4])
        rankings = {"integrated_gradients": np.arange(n_bins)[::-1].copy(),
                    "variance": np.arange(n_bins)}
        record = self.scorer.count_matched(rankings, legacy, correlations, n_bins)
        self.assertEqual(record["n_unique_bins"], 3)
        expected = self.scorer.score_indices(rankings["integrated_gradients"][:3],
                                             correlations, n_bins)["mSCF1"]
        self.assertEqual(record["rankings"]["integrated_gradients"], expected)
        self.assertAlmostEqual(record["ig_minus_legacy"], expected - record["legacy_msipl"])

    def test_production_evaluator_is_imported_not_copied_and_output_is_refused(self):
        text = (SCRIPTS / "score_msipl_retune.py").read_text(encoding="utf-8")
        self.assertIn("from evaluate_fair_scoring_baselines import", text)
        self.assertIn("check_legacy", text)
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "summary.json").write_text("{}")
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "score_msipl_retune.py"), "--input", "x.h5",
             "--attribution-dir", "a", "--saved-evaluation-dir", "e", "--saved-fair-dir", "f",
             "--retune-dir", "r", "--output", str(tmp), "--allow-outside-slurm"],
            capture_output=True, text=True,
            env=dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(SCRIPTS)])))
        self.assertEqual(result.returncode, 3, result.stderr)


def write_score(project, collection, section, arm, differences, statuses=None, code="c",
                k_bin=100, n=None):
    statuses = statuses or {}
    per_multiplier = {}
    for m, difference in zip(summary_module.MULTIPLIERS, differences):
        status = statuses.get(m, "saved_list_reproduced" if m == "m1.0" and collection != "RCC"
                              else "within_tolerance")
        rankings = {name: 0.5 for name in summary_module.RCC_METHODS}
        rankings["integrated_gradients"] = 0.5 + difference
        per_multiplier[m] = {"n_unique_bins": n or k_bin, "legacy_msipl": 0.5,
                             "rankings": rankings, "ig_minus_legacy": difference,
                             "selection": {"status": status, "beta": 0.0}}
    path = project / summary_module.SCORE_ROOT / f"{section}_seed1" / arm / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": "complete", "dataset": section, "K_bin": k_bin,
                                "provenance": {"code": {"x": code}},
                                "per_multiplier": per_multiplier}))


class SummariserTests(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        clause = {"sections": 8, "positive_sections": 8, "mean_difference": 0.1}
        decisions = {f"{c}/{a}": {"ig_minus_legacy_bin": clause,
                                  "ig_minus_legacy_collapse_diagnostic_P1": clause}
                     for c in ("GBM", "CAC") for a in summary_module.ARMS}
        path = self.project / summary_module.PARTITION_DECISIONS
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(decisions))
        for collection, sections in summary_module.SECTIONS.items():
            for section in sections:
                for arm in summary_module.ARMS:
                    write_score(self.project, collection, section, arm, [0.1] * 5)

    def run_summary(self):
        output = self.project / "out"
        result = subprocess.run([sys.executable, str(SCRIPTS / "summarise_msipl_retune.py"),
                                 "--project-root", str(self.project), "--output", str(output)],
                                capture_output=True, text=True)
        return result, output

    def test_rule_met_when_every_multiplier_has_at_least_seven_of_eight(self):
        write_score(self.project, "GBM", "GBM39_2", "uniform_mean", [0.1, -0.1, 0.1, 0.1, 0.1])
        result, output = self.run_summary()
        self.assertEqual(result.returncode, 0, result.stderr)
        decisions = json.loads((output / "decisions.json").read_text())
        clause = decisions["ig_beats_legacy"]["GBM/uniform_mean"]["clause_3_budget_stability"]
        self.assertTrue(clause["met"])
        self.assertEqual(clause["per_multiplier"]["m0.75"]["ig_above_legacy"], 7)
        self.assertTrue(decisions["ig_beats_legacy"]["GBM/uniform_mean"]
                        ["ig_beats_legacy_robust_to_scoring"])

    def test_one_multiplier_at_six_of_eight_fails_clause_three(self):
        for section in ("40TopL", "160TopL"):
            write_score(self.project, "CAC", section, "central_only", [0.1, 0.1, 0.1, 0.1, -0.1])
        result, output = self.run_summary()
        self.assertEqual(result.returncode, 0, result.stderr)
        rule = json.loads((output / "decisions.json").read_text())["ig_beats_legacy"]
        self.assertFalse(rule["CAC/central_only"]["clause_3_budget_stability"]["met"])
        self.assertFalse(rule["CAC/central_only"]["ig_beats_legacy_robust_to_scoring"])
        self.assertTrue(rule["CAC/uniform_mean"]["ig_beats_legacy_robust_to_scoring"])

    def test_capped_points_are_included_and_flagged(self):
        write_score(self.project, "GBM", "GBM22_2", "central_only", [0.1] * 5,
                    statuses={"m2.0": "msipl_cap"})
        result, output = self.run_summary()
        clause = json.loads((output / "decisions.json").read_text())[
            "ig_beats_legacy"]["GBM/central_only"]["clause_3_budget_stability"]
        self.assertTrue(clause["met"])
        self.assertEqual(len(clause["flagged_points"]), 1)
        self.assertIn("msipl_cap", clause["flagged_points"][0])

    def test_rcc_count_matched_table(self):
        write_score(self.project, "RCC", "RCC_MH0204_33", "central_only", [0.1] * 5,
                    statuses={"m1.0": "msipl_cap"}, k_bin=2200, n=1154)
        result, output = self.run_summary()
        self.assertEqual(result.returncode, 0, result.stderr)
        rcc = json.loads((output / "decisions.json").read_text())["rcc_count_matched"]
        self.assertEqual(rcc["runs_capped"], 1)
        self.assertIn("outside Holm", rcc["label"])
        self.assertTrue((output / "rcc_count_matched.csv").is_file())

    def test_refusals(self):
        write_score(self.project, "GBM", "GBM12_1", "central_only", [0.1] * 5, code="other")
        result, _ = self.run_summary()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("different scorer code", result.stderr)
        write_score(self.project, "GBM", "GBM12_1", "central_only", [0.1] * 5)
        (self.project / "out").mkdir()
        result, _ = self.run_summary()
        self.assertEqual(result.returncode, 3)


@unittest.skipUnless(BASH, "bash not available")
class JobScriptTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        shutil.copytree(JOBS, self.home / "msi" / "slurm_jobs")

    def sourced(self, command):
        script = f'source "$HOME/msi/slurm_jobs/msipl_retune_sections.sh"; {command}'
        return subprocess.run([BASH, "-c", script], capture_output=True, text=True,
                              env=dict(os.environ, HOME=bash_path(self.home)))

    def test_section_table_pilot_and_paths(self):
        result = self.sourced('echo "${#MSIPL_RETUNE_SECTIONS[@]}"; '
                              'msipl_retune_section "$MSIPL_RETUNE_PILOT_INDEX"; '
                              'msipl_retune_attribution RCC_UH0505_12 uniform_mean; '
                              'msipl_retune_saved_fair RCC_UH0505_12 uniform_mean; '
                              'msipl_retune_attribution RCC_UH0505_12 central_only; '
                              'msipl_retune_output GBM22_2; msipl_retune_weights 40TopL; '
                              'msipl_retune_score_output RCC_UH9912_01 central_only; '
                              'msipl_retune_saved_dir RCC_UH9912_01 || echo no-saved-rcc')
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], "24")
        self.assertEqual(lines[1], "GBM22_2")
        self.assertTrue(lines[2].endswith(
            "/ig_steps_rerun_20261030/RCC_UH0505_12_seed1/uniform_mean/steps128/attribution"))
        self.assertTrue(lines[3].endswith(
            "/ig_steps_20261030/bin_level_only/RCC_UH0505_12_seed1/uniform_mean/steps128"))
        self.assertTrue(lines[4].endswith("/rcc_spatial_msipl/RCC_UH0505_12_seed1/central_only/attribution"))
        self.assertTrue(lines[5].endswith("/results/baselines/msipl/retune_20261030/GBM/GBM22_2"))
        self.assertEqual(lines[6], "/datasets/zsuliman/msi_checkpoints/baselines/msipl/cac/40TopL/msipl_weights.h5")
        self.assertTrue(lines[7].endswith(
            "/fair_scoring_baselines/msipl_retune_20261030/RCC_UH9912_01_seed1/central_only"))
        self.assertEqual(lines[8], "no-saved-rcc")

    def test_resources_env_and_no_exclusive(self):
        sweep = (JOBS / "run_msipl_retune_sweep.sh").read_text()
        scoring = (JOBS / "run_msipl_retune_scoring.sh").read_text()
        for text in (sweep, scoring):
            self.assertIn("#SBATCH --partition=batch", text)
            self.assertNotIn("#SBATCH --exclusive", text)
        self.assertIn("conda activate msipl_legacy", sweep)
        for training_entry_point in ("run_msipl_legacy_gbm.py --", "msiPL_Run", "model.fit"):
            self.assertNotIn(training_entry_point, sweep)   # no retraining: saved weights only
        self.assertIn("s3pl_env", scoring)

    def run_job(self, name, task):
        return subprocess.run([BASH, bash_path(self.home / "msi" / "slurm_jobs" / name)],
                              capture_output=True, text=True,
                              env=dict(os.environ, HOME=bash_path(self.home),
                                       SLURM_ARRAY_TASK_ID=str(task), SLURM_ARRAY_JOB_ID="1"))

    def test_jobs_refuse_existing_outputs(self):
        sweep_out = self.home / "msi/results/baselines/msipl/retune_20261030/GBM/GBM22_2"
        sweep_out.mkdir(parents=True)
        (sweep_out / "sweep.csv").write_text("x")
        result = self.run_job("run_msipl_retune_sweep.sh", 5)
        self.assertEqual(result.returncode, 3, result.stderr)
        score_out = (self.home / "msi/results/diagnostics/fair_scoring_baselines/"
                     "msipl_retune_20261030/40TopL_seed1/uniform_mean")
        score_out.mkdir(parents=True)
        (score_out / "summary.json").write_text("{}")
        result = self.run_job("run_msipl_retune_scoring.sh", 8)
        self.assertEqual(result.returncode, 3, result.stderr)

    def test_gbm_cac_k_bin_equals_the_saved_legacy_unique_count(self):
        checked = 0
        for section in summary_module.SECTIONS["GBM"] + summary_module.SECTIONS["CAC"]:
            result = self.sourced(f"test_r_k_bin {section}; msipl_retune_saved_dir {section}")
            k_bin, saved = result.stdout.splitlines()
            local = ROOT / saved.split("/msi/", 1)[1] / "peak_metrics.json"
            if not local.is_file():
                continue
            self.assertEqual(json.loads(local.read_text())["unique_nearest_bins"], int(k_bin))
            selection = json.loads((local.parent / "beta_selection.json").read_text())
            self.assertIn("beta", selection["chosen"])
            checked += 1
        if checked == 0:
            self.skipTest("saved legacy msiPL files not present")
        self.assertEqual(checked, 16)


if __name__ == "__main__":
    unittest.main()
