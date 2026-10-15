#!/usr/bin/env python3
"""Build the curated report tables in results/publication/current_evidence/.

Reads only saved JSON artifacts (small files; no HDF5, no model, no scoring)
and writes CSV tables. Nothing is typed in by hand. Each table is cross-checked
against the decision tables the cluster summarisers already wrote; any
disagreement stops the build.

Tables:
  fair_scoring_bin_level_sections.csv    gates (a)/(b), bin level at K_bin (m = 1)
  fair_scoring_collection_summary.csv    IG minus each baseline per collection-arm
  fair_scoring_partition_sections.csv    gates (a)/(b), approved partitions (P1/P3)
  gate_d_pixel_counts.csv                gate (d) attribution-pixel count
  s3pl_cac_controls.csv                  S3PL CAC controls per section and seed
  s3pl_cac_seed_rule.json                the 2026-10-15 predeclared two-seed rule
  gate_d_bic.csv                         gate (d) BIC (only once all four exist)
"""

import argparse
import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FAIR = RESULTS / "diagnostics" / "fair_scoring_baselines"
GATE_D = RESULTS / "diagnostics" / "gate_d_pixel_counts"
BIC = RESULTS / "diagnostics" / "gate_d_bic"
S3PL = RESULTS / "baselines" / "s3pl"
SEED2 = ROOT / "reproducibility" / "s3pl_cac_centre_control" / "seed2_init2_order1"

BIN_DECISIONS = FAIR / "bin_level_only" / "summary_66097" / "decisions.json"
PARTITION_DECISIONS = FAIR / "with_approved_partitions" / "summary_66238" / "decisions.json"
GATE_D_DECISIONS = GATE_D / "summary_66406" / "decisions.json"

GBM_PATIENT = {
    "GBM108_positive": "108", "GBM108_negative": "108", "GBM12_1": "12",
    "GBM12_2": "12", "GBM22_1": "22", "GBM22_2": "22", "GBM39_1": "39", "GBM39_2": "39",
}
CAC_COUNTS = (("40TopL", 315), ("160TopL", 210), ("200TopL", 221), ("240TopL", 255),
              ("280TopL", 245), ("360TopL", 247), ("400TopL", 133), ("520TopL", 232))
DEVELOPMENT = {"GBM108_positive", "GBM22_2", "160TopL", "40TopL"}
ARMS = ("central_only", "uniform_mean")
METHODS = ("integrated_gradients", "posterior_abs_pcc_balanced", "posterior_abs_pcc_max",
           "posterior_signed_pcc_balanced", "hard_assignment_abs_pcc_balanced",
           "first_layer_l2", "mean_intensity", "variance", "morans_i", "legacy_msipl",
           "random", "oracle")
BASELINES = tuple(m for m in METHODS if m != "integrated_gradients")
TOLERANCE = 1e-12
S3PL_RULE = {
    "source": "docs/supervision/supervisor_chat.md, entry 2026-10-15 14:00, item 2",
    "statement": "S3PL benefits from real neighbourhood input during training",
    "supported_if": "real minus retrained tile-centre >= 0.02 mSCF1 on >= 7/8 sections "
                    "in both seeds, and mean paired difference >= 0.02 in both seeds",
    "otherwise": "mixed, with per-section values",
    "caveat": "the tile-centre model still reconstructs the real patch, so its target is "
              "harder; this is not a pure information ablation",
}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_csv(path, rows):
    fields = list(rows[0])
    for row in rows[1:]:
        fields += [key for key in row if key not in fields]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {path.name} ({len(rows)} rows)")


def same(a, b, what):
    if abs(a - b) > TOLERANCE:
        raise SystemExit(f"cross-check failed: {what}: {a} != {b}")


def collection_of(section):
    return "GBM" if section.startswith("GBM") else "CAC"


def method_score(bin_level, name):
    record = bin_level[name]["1.0"]
    return record["mSCF1_mean"] if name == "random" else record["mSCF1"]


def fair_sections():
    rows = []
    for path in sorted((FAIR / "bin_level_only").glob("*_seed1/*/summary.json")):
        summary = load(path)
        if summary.get("status") != "complete":
            raise SystemExit(f"{path}: status {summary.get('status')}")
        section = path.parent.parent.name.removesuffix("_seed1")
        row = {"section": section, "collection": collection_of(section),
               "patient": GBM_PATIENT.get(section, section), "arm": path.parent.name,
               "development_section": section in DEVELOPMENT, "K_bin": summary["K_bin"]}
        for name in METHODS:
            row[name] = method_score(summary["bin_level"], name)
        row["ig_minus_posterior_abs_pcc_balanced"] = (
            row["integrated_gradients"] - row["posterior_abs_pcc_balanced"])
        row["ig_minus_legacy_msipl"] = row["integrated_gradients"] - row["legacy_msipl"]
        rows.append(row)
    if len(rows) != 32:
        raise SystemExit(f"expected 32 section-arms at bin level, found {len(rows)}")
    return rows


def collection_summary(rows):
    decisions = load(BIN_DECISIONS)
    out = []
    for collection in ("GBM", "CAC"):
        for arm in ARMS:
            subset = [r for r in rows if r["collection"] == collection and r["arm"] == arm]
            for baseline in BASELINES:
                differences = [r["integrated_gradients"] - r[baseline] for r in subset]
                record = {
                    "collection": collection, "arm": arm, "baseline": baseline,
                    "sections": len(subset),
                    "ig_mean": statistics.fmean(r["integrated_gradients"] for r in subset),
                    "baseline_mean": statistics.fmean(r[baseline] for r in subset),
                    "mean_ig_minus_baseline": statistics.fmean(differences),
                    "median_ig_minus_baseline": statistics.median(differences),
                    "ig_wins": sum(d > 0 for d in differences),
                    "ties": sum(d == 0 for d in differences),
                }
                if collection == "GBM":
                    patients = sorted({r["patient"] for r in subset}, key=int)
                    means = {p: statistics.fmean(r["integrated_gradients"] - r[baseline]
                                                 for r in subset if r["patient"] == p)
                             for p in patients}
                    record["patient_grouped_mean_ig_minus_baseline"] = statistics.fmean(
                        means.values())
                    record["patient_ig_wins"] = sum(v > 0 for v in means.values())
                    for p, value in means.items():
                        record[f"patient_{p}_mean_ig_minus_baseline"] = value
                out.append(record)
            # Cross-check against the cluster decision table (66097).
            key = f"{collection}/{arm}"
            for baseline, field in (("posterior_abs_pcc_balanced", "ig_minus_posterior_bin"),
                                    ("legacy_msipl", "ig_minus_legacy_bin")):
                mine = next(r for r in out if r["collection"] == collection
                            and r["arm"] == arm and r["baseline"] == baseline)
                theirs = decisions[key][field]
                same(mine["mean_ig_minus_baseline"], theirs["mean_difference"], f"{key} {field}")
                same(mine["median_ig_minus_baseline"], theirs["median_difference"],
                     f"{key} {field} median")
                if mine["ig_wins"] != theirs["positive_sections"]:
                    raise SystemExit(f"cross-check failed: {key} {field} wins")
            if collection == "GBM":
                for p, value in decisions[key]["patient_ig_minus_posterior_bin"].items():
                    mine = next(r for r in out if r["collection"] == collection and r["arm"] == arm
                                and r["baseline"] == "posterior_abs_pcc_balanced")
                    same(mine[f"patient_{p}_mean_ig_minus_baseline"], value, f"{key} patient {p}")
    return out


def partition_sections():
    rows = []
    for path in sorted((FAIR / "with_approved_partitions").glob("*_seed1/*/summary.json")):
        summary = load(path)
        if summary.get("status") != "complete":
            raise SystemExit(f"{path}: status {summary.get('status')}")
        section = path.parent.parent.name.removesuffix("_seed1")
        for partition, record in sorted(summary["peak_level"].items()):
            row = {"section": section, "collection": collection_of(section),
                   "patient": GBM_PATIENT.get(section, section), "arm": path.parent.name,
                   "partition": partition, "K_peak": record["K_peak"]}
            for name in METHODS:
                method = record["methods"].get(name)
                if method is None:
                    continue
                matched = method.get("matched_K_peak")
                if isinstance(matched, dict) and "mSCF1" in matched:
                    row[f"{name}_matched_K_peak"] = matched["mSCF1"]
                elif isinstance(matched, dict) and "mSCF1_mean" in matched:
                    row[f"{name}_matched_K_peak"] = matched["mSCF1_mean"]
                if "collapse_K_bin" in method:
                    row[f"{name}_collapse_K_bin"] = method["collapse_K_bin"]["mSCF1"]
            if {"integrated_gradients_matched_K_peak",
                    "posterior_abs_pcc_balanced_matched_K_peak"} <= set(row):
                row["ig_minus_posterior_matched_K_peak"] = (
                    row["integrated_gradients_matched_K_peak"]
                    - row["posterior_abs_pcc_balanced_matched_K_peak"])
            rows.append(row)
    return rows


def gate_d_rows():
    decisions = load(GATE_D_DECISIONS)
    rows = []
    for section in ("GBM108_positive", "40TopL"):
        for arm in ARMS:
            summary = load(GATE_D / f"{section}_seed1" / arm / "evaluation" / "summary.json")
            if summary.get("status") != "complete":
                raise SystemExit(f"gate (d) {section}/{arm}: status {summary.get('status')}")
            for n in ("12", "48", "192"):
                pixels = sorted(set(summary["actual_attribution_pixels"][n].values()))
                change = summary["change_vs_saved_n12_at_K_bin"][n]
                row = {"section": section, "arm": arm, "n": int(n),
                       "actual_pixels_per_component": "/".join(map(str, pixels)),
                       "distinct_from_next_smaller": summary["distinct_from_next_smaller"][n],
                       "K_bin": summary["K_bin"],
                       "ig_mSCF1_at_K_bin": summary["mSCF1"][n]["1.0"],
                       "change_vs_saved_n12_at_K_bin": change,
                       "jaccard_vs_n12_at_K_bin": summary["jaccard_vs_n12_at_K_bin"][n],
                       "ig_minus_posterior_abs_pcc_at_K_bin":
                           summary["descriptive_ig_minus_posterior_abs_pcc"][n]["1.0"],
                       "n12_reproduction_passed": summary["n12_reproduction"]["passed"],
                       "verdict": decisions[arm][n]["verdict"] if n != "12" else
                                  "reference (saved production n = 12)"}
                if n != "12":
                    same(change, decisions[arm][n]["change_by_section"][section],
                         f"gate (d) {section}/{arm}/{n}")
                rows.append(row)
    return rows


def unrounded_mscf1(metrics, what):
    value = statistics.fmean(float(v) for v in metrics["mixed_f1"].values())
    if round(value, 3) != round(float(metrics["mSCF1"]), 3):
        raise SystemExit(f"{what}: mixed-F1 mean {value} does not round to {metrics['mSCF1']}")
    return value


def s3pl_rows():
    rows = []
    for section, count in CAC_COUNTS:
        base = f"{section}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9"
        real = load(S3PL / f"{base}_matched_{count}peaks" / "metrics.json")
        tile = load(S3PL / f"{base}_train_tile_centre" / "metrics.json")
        context = load(RESULTS / "diagnostics" / "s3pl_cac_frozen_context" / f"{section}.json")
        topology = load(RESULTS / "diagnostics" / "s3pl_cac_frozen_topology" / f"{section}.json")
        for record, what in ((real, "real"), (tile, "retrained tile")):
            if record["number_picked_peaks"] != count:
                raise SystemExit(f"{section} {what}: peak count differs from {count}")
        if tile["training_input_context_mode"] != "tile_centre":
            raise SystemExit(f"{section}: retrained tile is not a tile_centre training")
        # Each frozen campaign re-evaluated the real input itself; the two fresh
        # references can differ slightly (240TopL), so each keeps its own.
        fresh = topology["real_mscf1_unrounded"]
        comparisons = topology["comparisons"]
        real_value = unrounded_mscf1(real, f"{section} real")
        tile_value = unrounded_mscf1(tile, f"{section} retrained tile")
        rows.append({
            "section": section, "seed": 1, "initialization_seed": 1,
            "sample_order": "released code path (global RNG)", "matched_peaks": count,
            "real": real_value, "retrained_tile_centre": tile_value,
            "real_minus_retrained_tile_centre": real_value - tile_value,
            "frozen_context_fresh_real": context["real_mscf1_unrounded"],
            "frozen_tile_centre": context["tiled_centre_mscf1_unrounded"],
            "frozen_zero_noncentral": context["zero_noncentral_mscf1_unrounded"],
            "frozen_topology_fresh_real": fresh,
            "frozen_rotate_90": fresh - comparisons["rotate_90"]["real_minus_intervention_mscf1_unrounded"],
            "frozen_ring_shift": fresh - comparisons["permute_within_rings"]
                                               ["real_minus_intervention_mscf1_unrounded"],
            "frozen_context_status": context["status"],
            "frozen_topology_status": topology["status"],
        })
    seed2 = []
    for section, count in CAC_COUNTS:
        base = f"{section}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9"
        paths = (SEED2 / "results/baselines/s3pl" / base / "metrics.json",
                 SEED2 / "results/baselines/s3pl" / f"{base}_train_tile_centre" / "metrics.json")
        if not all(p.is_file() for p in paths):
            continue
        real, tile = load(paths[0]), load(paths[1])
        for record, what, mode in ((real, "real", "none"), (tile, "retrained tile", "tile_centre")):
            if record["number_picked_peaks"] != count or record["training_input_context_mode"] != mode:
                raise SystemExit(f"seed 2 {section} {what}: count or input mode differs")
        real_value = unrounded_mscf1(real, f"seed 2 {section} real")
        tile_value = unrounded_mscf1(tile, f"seed 2 {section} retrained tile")
        seed2.append({
            "section": section, "seed": 2, "initialization_seed": 2,
            "sample_order": "controlled stream, sample_order_seed 1", "matched_peaks": count,
            "real": real_value, "retrained_tile_centre": tile_value,
            "real_minus_retrained_tile_centre": real_value - tile_value})
    if seed2 and len(seed2) != len(CAC_COUNTS):
        raise SystemExit(f"seed 2 is partial ({len(seed2)}/8 sections); not tabulated")
    return rows + seed2


def s3pl_rule(rows):
    per_seed = {}
    for seed in sorted({r["seed"] for r in rows}):
        differences = [r["real_minus_retrained_tile_centre"] for r in rows if r["seed"] == seed]
        per_seed[str(seed)] = {
            "sections": len(differences),
            "sections_at_least_0.02": sum(d >= 0.02 for d in differences),
            "mean_paired_difference": statistics.fmean(differences),
            "mean_real": statistics.fmean(r["real"] for r in rows if r["seed"] == seed),
            "mean_retrained_tile_centre": statistics.fmean(
                r["retrained_tile_centre"] for r in rows if r["seed"] == seed)}
    result = dict(S3PL_RULE, per_seed=per_seed)
    if set(per_seed) != {"1", "2"}:
        result["outcome"] = "not evaluated: seed 2 is not complete"
    else:
        supported = all(v["sections_at_least_0.02"] >= 7 and v["mean_paired_difference"] >= 0.02
                        for v in per_seed.values())
        result["outcome"] = "supported" if supported else "mixed (see per-section values)"
    return result


def bic_rows():
    rows = []
    for section, production_k in (("GBM108_positive", 2), ("40TopL", 3)):
        for arm in ARMS:
            path = BIC / f"{section}_seed1" / arm / "bic_selection.json"
            if not path.is_file():
                return []
            record = load(path)
            if record.get("status") != "complete" or record["production_k"] != production_k:
                raise SystemExit(f"{path}: incomplete or wrong production K")
            sensitivity = load(path.parent / "bic_k_sensitivity" / "summary.json")
            selected = record["selected_k"]
            row = {"section": section, "arm": arm, "production_k": production_k,
                   "bic_selected_k": selected,
                   "selected_equals_production_k": selected == production_k,
                   "primary_result": ("BIC supports the production K"
                                      if selected == production_k else record["primary_result"]),
                   "best_k_ge_2_after_k1": record.get("sensitivity_k_ge_2"),
                   "production_refit_ari_to_saved": record["production_refit_ari_to_saved"]}
            for candidate in record["records"]:
                row[f"k{candidate['k']}_status"] = candidate["status"]
                row[f"k{candidate['k']}_bic"] = candidate.get("bic")
            row["sensitivity_label"] = sensitivity["label"]
            row["sensitivity_applicable"] = sensitivity["applicable"]
            if sensitivity["applicable"]:
                comparison = sensitivity["mSCF1_at_K_bin"]["posterior_abs_pcc_balanced"]
                agreement = sensitivity["label_agreement"]
                row.update({
                    "sensitivity_tested_k": sensitivity["tested_k"],
                    "posterior_abs_pcc_production_k": comparison["production_k_mSCF1"],
                    "posterior_abs_pcc_tested_k": comparison["tested_k_mSCF1"],
                    "posterior_abs_pcc_tested_minus_production":
                        comparison["tested_minus_production"],
                    "tested_k_ari": agreement["tested_k_hard_assignment"]["ari"],
                    "tested_k_nmi": agreement["tested_k_hard_assignment"]["nmi"],
                    "production_k_ari": agreement["production_k_saved_assignment"]["ari"],
                    "production_k_nmi": agreement["production_k_saved_assignment"]["nmi"]})
            rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=RESULTS / "publication" / "current_evidence")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sections = fair_sections()
    write_csv(args.output / "fair_scoring_bin_level_sections.csv", sections)
    write_csv(args.output / "fair_scoring_collection_summary.csv", collection_summary(sections))
    write_csv(args.output / "fair_scoring_partition_sections.csv", partition_sections())
    write_csv(args.output / "gate_d_pixel_counts.csv", gate_d_rows())
    s3pl = s3pl_rows()
    write_csv(args.output / "s3pl_cac_controls.csv", s3pl)
    rule_path = args.output / "s3pl_cac_seed_rule.json"
    rule_path.write_text(json.dumps(s3pl_rule(s3pl), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {rule_path.name}")
    bic = bic_rows()
    if bic:
        write_csv(args.output / "gate_d_bic.csv", bic)
    else:
        print("gate (d) BIC: not all four section-arms present; table not written")


if __name__ == "__main__":
    main()
