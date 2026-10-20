#!/usr/bin/env python3
"""Protocol 18 Section 6.7 (Investigation 21), Part A: S3PL seed variation from saved runs.

Local only, no training. Per collection:
- variance decomposition score ~ 1 + (1|section) + (1|seed) (statsmodels MixedLM, REML,
  descriptive), with the balanced two-way ANOVA moment estimates beside it;
- per-section seed mean, SD, min, max and the largest gap between sorted seed scores
  (descriptive bimodality item, supervisor chat 2026-10-20 11:46, Q6);
- pairwise Jaccard overlap of the saved picked-peak lists between seeds;
- last-batch final training loss beside mSCF1 (descriptive, n = seeds per section).

Seed sets:
- ``preliminary`` (chat 11:46, Q6): GBM = the controlled initialisation screen (init seeds
  1-3, sample-order seed 1); CAC = released ``random_seed`` 1-3. The two collections use
  different seed modes, and this is stated in every output.
- ``released`` (chat 11:46, Q6; after Part B): released ``random_seed`` 1-10 for GBM and
  CAC. This is the primary decomposition.

mSCF1 is S3PL's own in-job evaluator (``metrics.json``), not the fair-scoring evaluator.
It is recomputed unrounded as the mean of ``mixed_f1`` and must round to the saved
``mSCF1``, or the script stops.

Released runs must hold ``num_GT_peaks`` picked peaks. Fewer are accepted only when they
equal the run's logged distinct-selection count (released code keeps all of its pooled
distinct selections when there are fewer than ``num_GT_peaks``; supervisor chat
2026-10-20 20:39); such runs are listed in the outputs.
"""

import argparse
import csv
import hashlib
import itertools
import json
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "protocol 18 Section 6.7 (Investigation 21), Part A; supervisor chat 2026-10-20 10:53 and 11:46"
DEFAULT_OUTPUT = {"preliminary": Path("results") / "diagnostics" / "s3pl_seed_investigation_21"
                  / "part_a_preliminary"}
SECTIONS = {
    "GBM": ("GBM108_negative", "GBM108_positive", "GBM12_1", "GBM12_2",
            "GBM22_1", "GBM22_2", "GBM39_1", "GBM39_2"),
    "CAC": ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL",
            "400TopL", "520TopL"),
}
PATCH = {"GBM": 3, "CAC": 9}
SEED_MODE = {
    "preliminary": {
        "GBM": "controlled: initialization_seed = seed, sample_order_seed = 1 (investigation 16 screen)",
        "CAC": "released: random_seed = seed",
    },
}
NOTES = (
    "Descriptive only; no decision rule (protocol 18 Section 6.7, Part A).",
    "mSCF1 is S3PL's own in-job evaluator (metrics.json), not the fair-scoring evaluator.",
    "The final loss is the last-batch MSE of epoch 10 (train_history), not an epoch mean.",
    "A seed index has no shared meaning across sections, so the (1|seed) component is "
    "expected near zero; seed-to-seed variation within a section appears in the residual "
    "(the section x seed interaction).",
    "Preliminary set: GBM and CAC use different seed modes (see seed_mode). The primary "
    "decomposition is the same analysis on released seeds 1-10 after Part B.",
    "The largest gap is the largest difference between consecutive sorted seed scores in "
    "a section; it is a descriptive bimodality item and no bimodality wording is fixed.",
)


def run_name(collection, section):
    return f"{section}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_{PATCH[collection]}"


def preliminary_locations(collection, section, seed):
    """(log json, results folder), relative to the code/msi root."""
    name = run_name(collection, section)
    if collection == "GBM":
        base = Path("reproducibility") / "s3pl_massnet" / f"{section}_p3_rng_init{seed}_order1"
        return base / "logs" / "s3pl" / f"{name}.json", base / "results" / "baselines" / "s3pl" / name
    if seed == 1:
        return Path("logs") / "s3pl" / f"{name}.json", Path("results") / "baselines" / "s3pl" / name
    base = Path("reproducibility") / "s3pl_cac_seeds" / f"seed{seed}_released"
    return base / "logs" / "s3pl" / f"{name}.json", base / "results" / "baselines" / "s3pl" / name


INVESTIGATION_ROOT = Path("reproducibility") / "s3pl_investigation_21"


def _run_paths(base, name):
    return base / "logs" / "s3pl" / f"{name}.json", base / "results" / "baselines" / "s3pl" / name


def released_locations(collection, section, seed):
    """Released ``random_seed`` runs (Part B): saved runs reused after gate 72136 passed."""
    name = run_name(collection, section)
    if seed == 1:
        return _run_paths(Path(""), name)
    if collection == "GBM" and seed in (2, 3) and section in ("GBM108_negative", "GBM108_positive"):
        return _run_paths(Path("reproducibility") / "s3pl_massnet"
                          / f"{section}_p3_reference_spatial_max_seed{seed}", name)
    if collection == "CAC" and seed in (2, 3):
        return _run_paths(Path("reproducibility") / "s3pl_cac_seeds" / f"seed{seed}_released", name)
    return _run_paths(INVESTIGATION_ROOT / "released" / collection / f"seed{seed}", name)


def paper_tic_locations(collection, section, seed):
    """GBM paper-TIC runs (Part D); seed 1 predates the predeclaration."""
    if collection != "GBM":
        raise ValueError("Part D is GBM only")
    name = run_name(collection, section) + "_paper_tic"
    if seed == 1:
        return _run_paths(Path("reproducibility") / "s3pl_massnet" / f"{section}_p3_paper_tic_seed1", name)
    return _run_paths(INVESTIGATION_ROOT / "paper_tic" / "GBM" / f"seed{seed}", name)


LOCATORS = {"preliminary": (preliminary_locations, (1, 2, 3)),
            "released": (released_locations, tuple(range(1, 11)))}
SEED_MODE["released"] = {"GBM": "released: random_seed = seed", "CAC": "released: random_seed = seed"}
DEFAULT_OUTPUT["released"] = DEFAULT_OUTPUT["preliminary"].parent / "part_a_released"


# "length of peak selection before cut-off" per Investigation 21 task, transcribed from the
# Slurm .out files (task and cut-off lines only); runs saved earlier have no entry.
SELECTION_COUNTS = INVESTIGATION_ROOT / "provenance" / "selection_counts.tsv"


def native_counts(path=ROOT / "baselines" / "s3pl" / "data_configs.py"):
    """The released native peak counts (``num_GT_peaks``), read without importing S3PL."""
    import ast
    for node in ast.parse(Path(path).read_text()).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "num_GT_peaks" for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(f"{path}: num_GT_peaks not found")


def logged_selection_counts(root):
    """{(collection, section, seed, normalization): logged distinct-selection count}."""
    path = Path(root) / SELECTION_COUNTS
    if not path.exists():
        return {}
    with path.open(newline="") as handle:
        return {(r["collection"], r["section"], int(r["seed"]), r["normalization"]):
                int(r["logged_distinct_selection"]) for r in csv.DictReader(handle, delimiter="\t")}


def check_peak_count(record, native, logged, normalization="reference_spatial_max"):
    """Refuse a released run whose peak count is not explained by the released code.

    Released S3PL pools the distinct top-z selections of all patches and keeps the first
    ``num_GT_peaks`` (``test.py:167-184``). A run may therefore hold fewer peaks only if
    that equals its logged distinct-selection count. Returns a short-list record or None."""
    n = record["n_peaks"]
    key = (record["collection"], record["section"], record["seed"], normalization)
    if n == native and logged.get(key, native) >= native:
        return None
    if n < native and logged.get(key) == n:
        return {"collection": record["collection"], "section": record["section"],
                "seed": record["seed"], "n_peaks": n, "native": native,
                "results_folder": record["results_folder"]}
    raise ValueError(f"{record['results_folder']}: {n} peaks, native count {native}, "
                     f"logged distinct selection {logged.get(key)}")


def short_list_sentence(short, total):
    if not short:
        return f"0/{total} released runs returned fewer than num_GT_peaks peaks"
    if len(short) == 1:
        s = short[0]
        return (f"1/{total} released runs returned {s['n_peaks']} of {s['native']} peaks (released "
                f"distinct-m/z cut-off; {s['collection']} {s['section']} seed {s['seed']})")
    detail = "; ".join(f"{s['collection']} {s['section']} seed {s['seed']}: {s['n_peaks']} of {s['native']}"
                       for s in short)
    return (f"{len(short)}/{total} released runs returned fewer than num_GT_peaks peaks (released "
            f"distinct-m/z cut-off; {detail})")


def file_record(root, relative):
    data = (Path(root) / relative).read_bytes()
    return {"path": str(relative).replace("\\", "/"), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def read_peaks(path):
    lines = [line.strip() for line in Path(path).read_text().splitlines() if line.strip()]
    if not lines or lines[0] != "0":
        raise ValueError(f"{path}: expected the S3PL header line '0'")
    values = lines[1:]
    if len(set(values)) != len(values):
        raise ValueError(f"{path}: duplicate picked peaks")
    return values


def load_run(root, collection, section, seed, locate):
    log, results = locate(collection, section, seed)
    config = json.loads((Path(root) / log).read_text())
    metrics_rel = results / "metrics.json"
    metrics = json.loads((Path(root) / metrics_rel).read_text())
    peak_files = sorted((Path(root) / results).glob("picked_peaks_*.csv"))
    if len(peak_files) != 1:
        raise ValueError(f"{results}: expected one picked_peaks file, found {len(peak_files)}")
    if metrics.get("dataset") != section:
        raise ValueError(f"{metrics_rel}: dataset {metrics.get('dataset')!r} is not {section}")
    mixed = metrics["mixed_f1"]
    unrounded = float(np.mean([mixed[k] for k in sorted(mixed)]))
    if round(unrounded, 3) != metrics["mSCF1"]:
        raise ValueError(f"{metrics_rel}: mean(mixed_f1) {unrounded} does not round to mSCF1 {metrics['mSCF1']}")
    history = config.get("train_history") or []
    if len(history) != config.get("n_epochs"):
        raise ValueError(f"{log}: train_history has {len(history)} entries, n_epochs {config.get('n_epochs')}")
    peaks = read_peaks(peak_files[0])
    if len(peaks) != metrics["number_picked_peaks"]:
        raise ValueError(f"{peak_files[0]}: {len(peaks)} peaks, metrics say {metrics['number_picked_peaks']}")
    runtime_path = Path(root) / results / "runtime_metrics.json"
    runtime = json.loads(runtime_path.read_text()) if runtime_path.exists() else {}
    peaks_rel = peak_files[0].relative_to(Path(root))
    files = [log, metrics_rel, peaks_rel] + ([runtime_path.relative_to(Path(root))] if runtime else [])
    return {
        "collection": collection, "section": section, "seed": seed,
        "mscf1": unrounded, "mscf1_saved_rounded": metrics["mSCF1"],
        "final_loss_last_batch": float(history[-1]), "n_peaks": len(peaks),
        "peaks_sha256": hashlib.sha256(peak_files[0].read_bytes()).hexdigest(),
        "training_seconds": runtime.get("training_seconds"), "device": runtime.get("device"),
        "normalization": metrics.get("normalization"),
        "random_seed": config.get("random_seed"),
        "initialization_seed": config.get("initialization_seed"),
        "sample_order_seed": config.get("sample_order_seed"),
        "results_folder": str(results).replace("\\", "/"),
    }, set(peaks), files


def check_settings(record, mode, seed, normalization="reference_spatial_max"):
    """Refuse a run whose saved seed fields or normalisation differ from what the set claims.

    ``mode`` is "released" (random_seed = seed, controlled seeds unset) or "controlled"
    (initialization_seed = seed, sample_order_seed = 1). Runs from before the
    normalisation option existed carry no normalisation key; that is the released helper."""
    if mode == "released":
        ok = (record["random_seed"] == seed and record["initialization_seed"] is None
              and record["sample_order_seed"] is None)
    else:
        ok = record["initialization_seed"] == seed and record["sample_order_seed"] == 1
    allowed = (None, "reference_spatial_max") if normalization == "reference_spatial_max" else (normalization,)
    if not ok or record["normalization"] not in allowed:
        raise ValueError(f"{record['results_folder']}: saved settings do not match {mode} seed {seed}, "
                         f"{normalization}")


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 1.0


def largest_gap(values):
    ordered = sorted(values)
    gaps = [b - a for a, b in zip(ordered, ordered[1:])]
    if not gaps:
        return None, None
    i = int(np.argmax(gaps))
    return float(gaps[i]), f"{i + 1} below / {len(ordered) - i - 1} above"


def pearson(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def anova_components(matrix):
    """Two-way ANOVA without replication (rows sections, columns seeds); moment estimates.

    The residual mean square holds the section x seed interaction plus error. Negative
    moment estimates are reported as they are (not truncated)."""
    m = np.asarray(matrix, float)
    a, b = m.shape
    grand = m.mean()
    ss_rows = b * ((m.mean(axis=1) - grand) ** 2).sum()
    ss_cols = a * ((m.mean(axis=0) - grand) ** 2).sum()
    ss_res = ((m - m.mean(axis=1, keepdims=True) - m.mean(axis=0, keepdims=True) + grand) ** 2).sum()
    ms_rows, ms_cols = ss_rows / (a - 1), ss_cols / (b - 1)
    ms_res = ss_res / ((a - 1) * (b - 1))
    return {"section": (ms_rows - ms_res) / b, "seed": (ms_cols - ms_res) / a, "residual": ms_res}


def shares(components):
    positive = {k: max(v, 0.0) for k, v in components.items()}
    total = sum(positive.values())
    return {k: (v / total if total > 0 else None) for k, v in positive.items()}


def fit_crossed(rows):
    """score ~ 1 + (1|section) + (1|seed), REML, one fit, descriptive."""
    import pandas as pd
    import statsmodels.formula.api as smf

    frame = pd.DataFrame(rows)
    frame["group"] = 1
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            model = smf.mixedlm("score ~ 1", frame, groups="group", re_formula="0",
                                vc_formula={"section": "0 + C(section)", "seed": "0 + C(seed)"})
            result = model.fit(reml=True)
        except Exception as error:  # reported, never retried with other settings
            return {"status": "not converged", "error": str(error)}
    messages = sorted({str(w.message) for w in caught})
    if not result.converged:
        return {"status": "not converged", "warnings": " | ".join(messages)}
    components = {name: float(v) for name, v in zip(model.exog_vc.names, result.vcomp)}
    components["residual"] = float(result.scale)
    return {"status": "converged", "components": components, "shares": shares(components),
            "singular_or_boundary": bool(any(v < 1e-8 for v in components.values())
                                         or any("boundary" in m.lower() or "singular" in m.lower()
                                                for m in messages)),
            "intercept": float(result.fe_params["Intercept"]), "warnings": " | ".join(messages)}


def summarise(root, seed_set, mixed=True):
    locate, seeds = LOCATORS[seed_set]
    runs, sections, pairs, variance, collections, files = [], [], [], [], {}, []
    if seed_set == "released":
        native, logged = native_counts(), logged_selection_counts(root)
        if logged:
            files.append(SELECTION_COUNTS)
    for collection, names in SECTIONS.items():
        matrix, model_rows, short = [], [], []
        for section in names:
            loaded = [load_run(root, collection, section, seed, locate) for seed in seeds]
            mode = "controlled" if (seed_set, collection) == ("preliminary", "GBM") else "released"
            for (record, _, used), seed in zip(loaded, seeds):
                check_settings(record, mode, seed)
                if seed_set == "released":
                    note = check_peak_count(record, native[section], logged)
                    if note:
                        short.append(note)
                record["seed_mode"] = SEED_MODE[seed_set][collection]
                runs.append(record)
                files.extend(used)
            scores = [r["mscf1"] for r, _, _ in loaded]
            losses = [r["final_loss_last_batch"] for r, _, _ in loaded]
            matrix.append(scores)
            model_rows += [{"section": section, "seed": s, "score": v} for s, v in zip(seeds, scores)]
            overlaps = []
            for (ra, pa, _), (rb, pb, _) in itertools.combinations(loaded, 2):
                value = jaccard(pa, pb)
                overlaps.append(value)
                pairs.append({"collection": collection, "section": section, "seed_a": ra["seed"],
                              "seed_b": rb["seed"], "k": len(pa), "intersection": len(pa & pb),
                              "jaccard": value})
            gap, split = largest_gap(scores)
            sections.append({
                "collection": collection, "section": section, "n_seeds": len(scores),
                "mean": float(np.mean(scores)), "sd": float(np.std(scores, ddof=1)),
                "min": float(min(scores)), "max": float(max(scores)),
                "range": float(max(scores) - min(scores)),
                "largest_gap": gap, "gap_split": split,
                "sorted_scores": json.dumps([round(v, 6) for v in sorted(scores)]),
                "jaccard_mean": float(np.mean(overlaps)), "jaccard_min": float(min(overlaps)),
                "jaccard_max": float(max(overlaps)),
                "loss_vs_mscf1_pearson_r": pearson(losses, scores),
                "lowest_loss_seed": seeds[int(np.argmin(losses))],
                "highest_mscf1_seed": seeds[int(np.argmax(scores))],
            })
        seed_means = np.asarray(matrix).mean(axis=0)
        per_section_sd = [s["sd"] for s in sections if s["collection"] == collection]
        collections[collection] = {
            "seed_mode": SEED_MODE[seed_set][collection],
            "seeds": list(seeds),
            "collection_mean_per_seed": {str(s): float(v) for s, v in zip(seeds, seed_means)},
            "collection_mean_over_seeds": float(seed_means.mean()),
            "collection_sd_over_seeds": float(np.std(seed_means, ddof=1)),
            "section_seed_sd_median": float(np.median(per_section_sd)),
            "section_seed_sd_min": float(min(per_section_sd)),
            "section_seed_sd_max": float(max(per_section_sd)),
        }
        if seed_set == "released":
            collections[collection]["short_peak_lists"] = short
        anova = anova_components(matrix)
        record = {"collection": collection, "seed_mode": SEED_MODE[seed_set][collection],
                  "n_sections": len(names), "n_seeds": len(seeds), "label": "descriptive",
                  "formula": "score ~ 1 + (1|section) + (1|seed)"}
        for key, value in anova.items():
            record[f"anova_var_{key}"] = value
        for key, value in shares(anova).items():
            record[f"anova_share_{key}"] = value
        if mixed:
            fit = fit_crossed(model_rows)
            record["mixedlm_status"] = fit["status"]
            if fit["status"] == "converged":
                for key, value in fit["components"].items():
                    record[f"mixedlm_var_{key}"] = value
                for key, value in fit["shares"].items():
                    record[f"mixedlm_share_{key}"] = value
                record["mixedlm_singular_or_boundary"] = fit["singular_or_boundary"]
                record["mixedlm_warnings"] = fit["warnings"]
        variance.append(record)
    return runs, sections, pairs, variance, collections, files


def write_csv(path, rows):
    fields = []
    for row in rows:
        fields.extend(key for key in row if key not in fields)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def plot(sections, runs, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, len(SECTIONS), figsize=(6 * len(SECTIONS), 4), sharex=True)
    for ax, collection in zip(np.atleast_1d(axes), SECTIONS):
        names = SECTIONS[collection]
        for i, section in enumerate(names):
            values = [r["mscf1"] for r in runs if r["collection"] == collection and r["section"] == section]
            ax.scatter(values, [i] * len(values), s=28, color="#3b6ea5", zorder=3)
            ax.hlines(i, min(values), max(values), color="#9db4cf", lw=1.5, zorder=2)
        ax.set_yticks(range(len(names)), names)
        ax.set_xlabel("S3PL mSCF1 (in-job evaluator)")
        ax.set_title(f"{collection}: seed scores per section")
        ax.grid(axis="x", color="#e0e0e0", lw=0.6)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def versions():
    out = {"python": sys.version.split()[0], "numpy": np.__version__}
    try:
        import statsmodels
        out["statsmodels"] = statsmodels.__version__
    except ImportError:
        out["statsmodels"] = None
    return out


def run(root, output, seed_set, mixed=True, figure=True):
    output = Path(output)
    if output.exists():
        print(f"refusing: {output} exists; move it aside first", file=sys.stderr)
        return 3
    runs, sections, pairs, variance, collections, files = summarise(root, seed_set, mixed)
    summary = {
        "protocol": PROTOCOL, "part": "A", "seed_set": seed_set,
        "status": "preliminary" if seed_set == "preliminary" else "primary",
        "evaluator": "S3PL in-job mSCF1 (metrics.json); not the fair-scoring evaluator",
        "collections": collections, "variance": variance, "notes": list(NOTES),
        "provenance": {
            "inputs": [file_record(root, rel) for rel in sorted(set(files), key=str)],
            "code": {Path(__file__).name: hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()},
            "versions": versions(),
        },
    }
    if seed_set == "released":
        short = [s for c in collections.values() for s in c["short_peak_lists"]]
        summary["short_peak_lists"] = short_list_sentence(short, len(runs))
    output.mkdir(parents=True)
    write_csv(output / "runs.csv", runs)
    write_csv(output / "sections.csv", sections)
    write_csv(output / "jaccard_pairs.csv", pairs)
    write_csv(output / "variance.csv", variance)
    if figure:
        plot(sections, runs, output / "seed_scores_per_section.png")
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", dest="seed_set", choices=sorted(LOCATORS), required=True)
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="code/msi root that holds the saved runs (tests pass a temp root)")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-figure", action="store_true")
    args = parser.parse_args(argv)
    output = args.output or args.root / DEFAULT_OUTPUT[args.seed_set]
    return run(args.root, output, args.seed_set, figure=not args.no_figure)


if __name__ == "__main__":
    sys.exit(main())
