#!/usr/bin/env python3
"""Protocol 18 Section 6.6 ("Stats"): paired tests beside the predeclared labels.

Family and Holm families as fixed in the Section 6.6 addendum (supervisor chat
2026-10-20 10:46). Local only, on saved per-section results: every difference is
built from a committed section table and must reproduce the saved decision's
per-section values (as a multiset, to 1e-12), or the script stops. Item 3
(Mann-Whitney) is "not done": per-bin mask PCCs are not saved for the
posterior-selected bins. Mixed models are descriptive.
"""

import argparse
import csv
import hashlib
import json
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from spatial_msipl import paired_statistics as ps  # noqa: E402

DIAG = Path("results") / "diagnostics"
FSB = DIAG / "fair_scoring_baselines"
SOURCES = {
    "test_r": FSB / "test_r" / "decisions_20261017_local",
    "core_bin": FSB / "bin_level_only" / "summary_66097",
    "extra_arms": FSB / "extra_arms" / "decisions_20261016_local",
    "test_s": DIAG / "spatial_segmentation_S" / "decisions_20261017_local",
    "test_v": DIAG / "segmentation_control_V" / "decisions_20261017_local",
    "test_v_seed_mean": DIAG / "segmentation_control_V" / "decisions_20261017_with_test_r_local",
    "test_n": DIAG / "s3pl_cac_shuffle_control" / "decisions_20261017_local",
}
DEFAULT_OUTPUT = DIAG / "statistics_6_6"
SECTIONS = {
    "GBM": ("GBM108_negative", "GBM108_positive", "GBM12_1", "GBM12_2",
            "GBM22_1", "GBM22_2", "GBM39_1", "GBM39_2"),
    "CAC": ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL",
            "400TopL", "520TopL"),
    "RCC": ("RCC_MH0204_33", "RCC_UH0505_12", "RCC_UH0710_33", "RCC_UH9610_15",
            "RCC_UH9812_03", "RCC_UH9905_18", "RCC_UH9911_05", "RCC_UH9912_01"),
}
ARMS = ("central_only", "uniform_mean")
SEEDS = (1, 2, 3)
FAMILIES = {"F1 primary ranking": range(1, 7), "F2 vs legacy": range(7, 11),
            "F3 encoder context and variants": range(11, 28),
            "F4 segmentation": range(28, 37), "F5 S3PL": range(37, 39)}
TOLERANCE = 1e-12
ALPHA = 0.05
PROTOCOL = ("protocol 18 Section 6.6, with the addendum of 2026-10-20 "
            "(supervisor chat 10:28 plan; 10:46 family and Holm families)")
NOTES = (
    "p-values describe these sections, not a population.",
    "With exact Wilcoxon the smallest attainable two-sided p is 2/2^n (n = nonzero "
    "differences): 0.0078 at n = 8, 0.125 at n = 4 (GBM PDX line).",
    "Zero differences: scipy drops them (zero_method='wilcox') and applies the exact "
    "null distribution to the remaining n; there is no fallback to the normal "
    "approximation and no warning. Zeros are counted in n_zero; the HL estimate and CI "
    "use all n differences. With tied |differences| scipy still uses the untied exact "
    "distribution; n_tied_abs reports them.",
    "Holm is applied within each family, separately for the primary (bin) and the "
    "secondary (P1, GBM/CAC) scale. PDX-line and seed-mean-beside rows are outside "
    "the Holm families.",
    "Rows 7-10 (IG vs legacy) have no P1 test: legacy msiPL is not K_peak-matched and "
    "its peak-level value is a collapse diagnostic only. Rows 37-38 are S3PL matched "
    "peaks (one scale). RCC rows are bin level only.",
    "GBM PDX-line value = mean of the line's available section differences; "
    "`sections_per_line` records how many sections each line has.",
    "The practical labels are unchanged; these tests are reported beside them.",
)


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def number(text):
    return None if text in ("", None) else float(text)


def check_saved(values, saved, where):
    """Recomputed differences must equal the saved per-section values as a multiset."""
    mine, theirs = np.sort(np.asarray(values, float)), np.sort(np.asarray(saved, float))
    if mine.shape != theirs.shape or np.max(np.abs(mine - theirs), initial=0.0) > TOLERANCE:
        raise ValueError(f"{where}: recomputed differences do not reproduce the saved "
                         f"decision ({len(mine)} vs {len(theirs)} values)")


class Inputs:
    def __init__(self, root):
        self.root = Path(root)
        self.files = {}

    def path(self, source, name):
        path = self.root / SOURCES[source] / name
        self.files[str((SOURCES[source] / name).as_posix())] = path
        return path

    def csv(self, source):
        return read_csv(self.path(source, "section_table.csv"))

    def decisions(self, source):
        return read_json(self.path(source, "decisions.json"))


def test_r_index(inputs):
    index = {}
    for row in inputs.csv("test_r"):
        key = (row["collection"], row["section"], row["arm"], int(row["seed"]), row["scale"])
        index[key] = (number(row["ig_mSCF1"]), number(row["posterior_mSCF1"]))
    return index


def ig_minus_posterior_seed_mean(inputs, collection, arm, scale):
    index, saved = test_r_index(inputs), inputs.decisions("test_r")
    for seed in SEEDS:
        per_seed = [index[(collection, s, arm, seed, scale)] for s in SECTIONS[collection]
                    if (collection, s, arm, seed, scale) in index]
        check_saved([ig - post for ig, post in per_seed],
                    saved["decision_1"]["per_collection_arm_seed"]
                    [f"{collection}/{arm}/seed{seed}"]["IG_minus_posterior"][scale]["per_section"],
                    f"Test R decision 1 {collection}/{arm}/seed{seed}/{scale}")
    sections, values = [], []
    for section in SECTIONS[collection]:
        keys = [(collection, section, arm, seed, scale) for seed in SEEDS]
        if all(key in index for key in keys):
            sections.append(section)
            values.append(np.mean([index[k][0] - index[k][1] for k in keys]))
    return sections, values


def context_seed_mean(inputs, collection, scale):
    index, saved = test_r_index(inputs), inputs.decisions("test_r")
    sections, values = [], []
    for section in SECTIONS[collection]:
        keys = {(arm, seed): (collection, section, arm, seed, scale)
                for arm in ARMS for seed in SEEDS}
        if all(key in index for key in keys.values()):
            sections.append(section)
            values.append(np.mean([index[keys[("uniform_mean", s)]][0]
                                   - index[keys[("central_only", s)]][0] for s in SEEDS]))
    check_saved(values, saved["decision_2"][collection]["seed_averaged"][scale]["per_section"],
                f"Test R decision 2 {collection}/{scale}")
    return sections, values


def ig_minus_legacy(inputs, collection, arm, scale):
    rows = [r for r in inputs.csv("core_bin") if r["collection"] == collection and r["arm"] == arm]
    sections = [r["section"] for r in rows]
    values = [number(r["bin:integrated_gradients"]) - number(r["bin:legacy_msipl"]) for r in rows]
    check_saved(values, inputs.decisions("core_bin")[f"{collection}/{arm}"]
                ["ig_minus_legacy_bin"]["per_section"], f"IG vs legacy {collection}/{arm}")
    return sections, values


def extra_arm_difference(inputs, collection, first, second, scale, saved_path):
    rows = {(r["arm"], r["section"]): r for r in inputs.csv("extra_arms")
            if r["collection"] == collection}
    sections = [s for s in SECTIONS[collection] if (first[0], s) in rows]
    values = [number(rows[(first[0], s)][f"{scale}:{first[1]}"])
              - number(rows[(second[0], s)][f"{scale}:{second[1]}"]) for s in sections]
    saved = inputs.decisions("extra_arms")
    for key in saved_path(scale):
        saved = saved[key]
    check_saved(values, saved, f"extra arms {collection} {first} - {second} {scale}")
    return sections, values


def s1_minus_plain(inputs, collection, arm, scale):
    rows = [r for r in inputs.csv("test_s") if r["collection"] == collection and r["arm"] == arm]
    sections = [r["section"] for r in rows]
    values = [number(r[f"{scale}:sa_posterior_abs_pcc_balanced"])
              - number(r[f"{scale}:posterior_abs_pcc_balanced"]) for r in rows]
    check_saved(values, inputs.decisions("test_s")[f"{collection}/{arm}"]["S1_minus_plain"]
                [scale]["per_section"], f"Test S {collection}/{arm}/{scale}")
    return sections, values


def vae_minus_pca5(inputs, collection, scale):
    rows = [r for r in inputs.csv("test_v") if r["collection"] == collection]
    sections = [r["section"] for r in rows]
    values = [number(r[f"{scale}:posterior_abs_pcc_balanced"])
              - number(r[f"{scale}:pca5_posterior_abs_pcc_balanced"]) for r in rows]
    check_saved(values, inputs.decisions("test_v")[collection]["vae_minus_pca5"][scale]
                ["per_section"], f"Test V {collection}/{scale}")
    return sections, values


def vae_seed_mean_minus_pca5(inputs, collection, scale):
    rows = [r for r in inputs.csv("test_v_seed_mean") if r["collection"] == collection
            and number(r[f"{scale}:vae_seed_mean_1_3"]) is not None]
    return ([r["section"] for r in rows],
            [number(r[f"{scale}:vae_seed_mean_1_3"])
             - number(r[f"{scale}:pca5_posterior_abs_pcc_balanced"]) for r in rows])


def s3pl_real_minus_shuffled(inputs, seed):
    rows = [r for r in inputs.csv("test_n") if int(r["seed"]) == seed]
    values = [number(r["real_minus_shuffled"]) for r in rows]
    check_saved(values, inputs.decisions("test_n")["per_seed"][str(seed)]["per_section"],
                f"Test N seed {seed}")
    return [r["section"] for r in rows], values


def family_rows():
    """The 38 predeclared rows: (row, comparison, collection, arm, unit, scales, builder)."""
    rows, n = [], 0

    def add(comparison, collection, arm, unit, scales, builder):
        nonlocal n
        n += 1
        rows.append({"row": n, "comparison": comparison, "collection": collection,
                     "arm": arm, "unit": unit, "scales": scales, "builder": builder})

    for collection in SECTIONS:
        for arm in ARMS:
            add("IG - posterior-|PCC|", collection, arm, "seed mean 1-3",
                ("bin",) if collection == "RCC" else ("bin", "P1"),
                lambda i, sc, c=collection, a=arm: ig_minus_posterior_seed_mean(i, c, a, sc))
    for collection in ("GBM", "CAC"):
        for arm in ARMS:
            add("IG - legacy msiPL", collection, arm, "seed 1", ("bin",),
                lambda i, sc, c=collection, a=arm: ig_minus_legacy(i, c, a, sc))
    for collection in SECTIONS:
        add("IG uniform_mean - central_only", collection, "", "seed mean 1-3",
            ("bin",) if collection == "RCC" else ("bin", "P1"),
            lambda i, sc, c=collection: context_seed_mean(i, c, sc))
    ig = "integrated_gradients"
    scale_key = {"bin": "bin_level", "P1": "P1"}
    for collection in ("GBM", "CAC"):
        add("attention - uniform_mean IG", collection, "attention", "seed 1", ("bin", "P1"),
            lambda i, sc, c=collection: extra_arm_difference(
                i, c, ("attention", ig), ("uniform_mean", ig), sc,
                lambda scale: ["comparisons", "A: attention vs uniform_mean", c,
                               scale_key[scale], "per_section"]))
    for comparison, second, key in (("G1 - attention", "attention", "G rule 2: G1 vs standard attention"),
                                    ("G1 - G2", "uniform_centremask_p50", "G rule 2: G1 vs G2")):
        for collection in ("GBM", "CAC"):
            add(comparison, collection, "attention_centremask_p50", "seed 1", ("bin", "P1"),
                lambda i, sc, c=collection, s=second, k=key: extra_arm_difference(
                    i, c, ("attention_centremask_p50", ig), (s, ig), sc,
                    lambda scale: ["comparisons", k, c, scale_key[scale], "per_section"]))
    for arm, label in (("attention_centremask_p50", "G1"), ("uniform_centremask_p50", "G2")):
        for collection in ("GBM", "CAC"):
            add(f"{label} IG - posterior-|PCC|", collection, arm, "seed 1", ("bin", "P1"),
                lambda i, sc, c=collection, a=arm: extra_arm_difference(
                    i, c, (a, ig), (a, "posterior_abs_pcc_balanced"), sc,
                    lambda scale: ["ig_vs_posterior", a, c, f"ig_minus_posterior_{scale}",
                                   "per_section"]))
    for arm, label in (("uniform_p7", "p7"), ("uniform_p9", "p9")):
        for collection in ("GBM", "CAC"):
            add(f"{label} - 3x3 IG", collection, arm, "seed 1", ("bin", "P1"),
                lambda i, sc, c=collection, a=arm: extra_arm_difference(
                    i, c, (a, ig), ("uniform_mean", ig), sc,
                    lambda scale: ["e_windows_vs_real_3x3", a, c, "all_8", scale_key[scale],
                                   "per_section"]))
    for collection in SECTIONS:
        for arm in ARMS:
            add("S1 - plain posterior-|PCC|", collection, arm, "seed 1",
                ("bin",) if collection == "RCC" else ("bin", "P1"),
                lambda i, sc, c=collection, a=arm: s1_minus_plain(i, c, a, sc))
    for collection in SECTIONS:
        add("VAE central_only posterior - PCA-5 posterior", collection, "central_only",
            "seed 1", ("bin",) if collection == "RCC" else ("bin", "P1"),
            lambda i, sc, c=collection: vae_minus_pca5(i, c, sc))
    for seed in (1, 2):
        add("S3PL real - retrained shuffled-nonlocal", "CAC", f"S3PL seed {seed}",
            f"seed {seed}", ("matched",), lambda i, sc, s=seed: s3pl_real_minus_shuffled(i, s))
    assert n == 38, n
    return rows


def family_of(row):
    return next(name for name, rows in FAMILIES.items() if row in rows)


def pdx_line(sections, values):
    lines = {}
    for section, value in zip(sections, values):
        lines.setdefault(section.split("_")[0], []).append(value)
    names = sorted(lines, key=lambda name: int(name[3:]))
    return names, [float(np.mean(lines[n])) for n in names], [len(lines[n]) for n in names]


def test_record(spec, scale, role, sections, values, family, extra=None):
    return {"row": spec["row"], "family": family, "role": role,
            "comparison": spec["comparison"], "collection": spec["collection"],
            "arm": spec["arm"], "unit": spec["unit"], "scale": scale,
            **ps.paired_summary(values), "holm_p": None,
            "sections": ";".join(sections),
            "differences": ";".join(repr(float(v)) for v in values), **(extra or {})}


def compute_tests(inputs):
    records = []
    for spec in family_rows():
        family = family_of(spec["row"])
        for scale in spec["scales"]:
            sections, values = spec["builder"](inputs, scale)
            role = "secondary" if scale == "P1" else "primary"
            records.append(test_record(spec, scale, role, sections, values, family))
            if spec["collection"] == "GBM":
                names, line_values, counts = pdx_line(sections, values)
                records.append(test_record(
                    spec, scale, "pdx_line (outside Holm)", names, line_values, "",
                    {"sections_per_line": ";".join(map(str, counts))}))
            if spec["row"] in (34, 35, 36):
                s, v = vae_seed_mean_minus_pca5(inputs, spec["collection"], scale)
                beside = dict(spec, unit="VAE seed mean 1-3 (beside)")
                records.append(test_record(beside, scale, "seed mean beside (outside Holm)",
                                           s, v, ""))
    families = {}
    for role in ("primary", "secondary"):
        for family in FAMILIES:
            members = [r for r in records if r["family"] == family and r["role"] == role]
            if not members:
                continue
            for record, adjusted in zip(members, ps.holm([r["p_exact"] for r in members])):
                record["holm_p"] = adjusted
            k = len(members)
            smallest = min(r["min_attainable_p"] for r in members if r["min_attainable_p"])
            families[f"{family} / {role}"] = {
                "rows": [r["row"] for r in members], "k": k,
                "holm_first_step_threshold": ALPHA / k,
                "smallest_attainable_p_in_family": smallest,
                "first_step_attainable": smallest < ALPHA / k,
                "holm_p_below_0.05": [r["row"] for r in members
                                      if r["holm_p"] is not None and r["holm_p"] < ALPHA],
            }
    return records, families


def fit_mixed(frame_rows, crossed):
    """score ~ is_first, with (1|section) [+ (1|seed) crossed]; REML; descriptive."""
    import pandas as pd
    import statsmodels.formula.api as smf

    frame = pd.DataFrame(frame_rows)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            if crossed:
                frame["group"] = 1
                model = smf.mixedlm("score ~ is_first", frame, groups="group", re_formula="0",
                                    vc_formula={"section": "0 + C(section)",
                                                "seed": "0 + C(seed)"})
            else:
                model = smf.mixedlm("score ~ is_first", frame, groups="section")
            result = model.fit(reml=True)
        except Exception as error:  # reported, never retried with other settings
            return {"status": "not converged", "error": str(error),
                    "warnings": " | ".join(sorted({str(w.message) for w in caught}))}
    messages = sorted({str(w.message) for w in caught})
    if not result.converged:
        # Protocol 18 Section 6.6 item 4: report "not converged", with no estimate.
        return {"status": "not converged", "n_obs": int(len(frame)),
                "n_sections": int(frame["section"].nunique()), "warnings": " | ".join(messages)}
    low, high = result.conf_int(alpha=ALPHA).loc["is_first"]
    variances = ({name: float(v) for name, v in zip(model.exog_vc.names, result.vcomp)}
                 if crossed else {"section": float(result.cov_re.iloc[0, 0])})
    boundary = (any(v < 1e-8 for v in variances.values())
                or any("boundary" in m.lower() or "singular" in m.lower() for m in messages))
    return {"status": "converged",
            "estimate": float(result.fe_params["is_first"]), "ci_low": float(low),
            "ci_high": float(high), "residual_variance": float(result.scale),
            "variance_components": json.dumps(variances, sort_keys=True),
            "singular_or_boundary": boundary, "n_obs": int(len(frame)),
            "n_sections": int(frame["section"].nunique()),
            "warnings": " | ".join(messages)}


def compute_mixed_models(inputs):
    index = test_r_index(inputs)
    results = []
    for collection in SECTIONS:
        for arm in ARMS:
            data = []
            for (c, section, a, seed, scale), (ig, post) in sorted(index.items()):
                if c == collection and a == arm and scale == "bin":
                    data += [{"section": section, "seed": seed, "is_first": 1, "score": ig},
                             {"section": section, "seed": seed, "is_first": 0, "score": post}]
            results.append({"model": "IG vs posterior-|PCC|", "collection": collection,
                            "arm": arm, "scale": "bin", "label": "descriptive",
                            "formula": "score ~ method + (1|section) + (1|seed)",
                            "first_minus": "IG - posterior", **fit_mixed(data, True)})
        data = [{"section": section, "seed": seed, "is_first": 1, "score": post}
                for (c, section, a, seed, scale), (_, post) in sorted(index.items())
                if c == collection and a == "central_only" and scale == "bin"]
        data += [{"section": r["section"], "seed": 0, "is_first": 0,
                  "score": number(r["bin:pca5_posterior_abs_pcc_balanced"])}
                 for r in inputs.csv("test_v") if r["collection"] == collection]
        results.append({"model": "VAE central_only vs PCA-5 posterior-|PCC|",
                        "collection": collection, "arm": "central_only", "scale": "bin",
                        "label": "descriptive", "formula": "score ~ method + (1|section)",
                        "first_minus": "VAE (seeds 1-3) - PCA-5", **fit_mixed(data, False)})
    return results


MANN_WHITNEY = [{
    "item": "3", "status": "not done",
    "reason": ("per-bin class-mask PCCs are saved locally only for the IG- and L2-selected "
               "bins (peak_evaluation*/ig_matched_<K>_bins.csv, first_layer_l2_matched_<K>"
               "_bins.csv); the posterior-|PCC|-selected bins exist only as rankings "
               "(rankings_prefix.npz). IG vs L2 is not substituted (chat 2026-10-20 10:46, Q6)."),
}]


def file_record(root, relative):
    path = Path(root) / relative
    data = path.read_bytes()
    return {"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def write_csv(path, rows):
    fields = []
    for row in rows:
        fields.extend(key for key in row if key not in fields)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def versions():
    import scipy
    import statsmodels
    return {"python": sys.version.split()[0], "numpy": np.__version__,
            "scipy": scipy.__version__, "statsmodels": statsmodels.__version__}


def run(root, output, mixed=True):
    output = Path(output)
    if output.exists():
        print(f"refusing: {output} exists; move it aside first", file=sys.stderr)
        return 3
    inputs = Inputs(root)
    records, families = compute_tests(inputs)
    models = compute_mixed_models(inputs) if mixed else []
    code = [Path(__file__).resolve(), Path(ps.__file__).resolve()]
    summary = {
        "protocol": PROTOCOL,
        "families": families,
        "rows_primary": sum(r["role"] == "primary" for r in records),
        "rows_secondary": sum(r["role"] == "secondary" for r in records),
        "mann_whitney": MANN_WHITNEY[0],
        "mixed_models": "descriptive only; one fit per model, no model selection",
        "notes": list(NOTES),
        "provenance": {
            "inputs": [file_record(root, rel) for rel in sorted(inputs.files)],
            "code": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in code},
            "versions": versions(),
            "validation": "every family difference reproduces its saved decision's "
                          f"per-section values to {TOLERANCE} (rows 1-38; the seed-mean-"
                          "beside rows are not a saved decision)",
        },
    }
    output.mkdir(parents=True)
    write_csv(output / "tests.csv", records)
    write_csv(output / "mann_whitney.csv", MANN_WHITNEY)
    write_csv(output / "mixed_models.csv", models)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="code/msi root that holds results/ (tests pass a temp root)")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    return run(args.root, args.output or args.root / DEFAULT_OUTPUT)


if __name__ == "__main__":
    sys.exit(main())
