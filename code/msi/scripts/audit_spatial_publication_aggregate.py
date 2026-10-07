#!/usr/bin/env python3
"""Independently trace primary publication tables to section evaluations."""

import csv
import json
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLICATION = ROOT / "results/publication/current_evidence"
GBM = ("GBM108_positive", "GBM108_negative", "GBM12_1", "GBM12_2",
       "GBM22_1", "GBM22_2", "GBM39_1", "GBM39_2")
CAC = ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL",
       "360TopL", "400TopL", "520TopL")
METHODS = {"legacy_msipl": "Tuned legacy msiPL", "central_ig": "Centre-only IG",
           "spatial_ig": "Uniform-context IG"}


def read_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def source_row(collection, section):
    if collection == "GBM":
        base = ROOT / "results/experiments/spatial_msipl_gbm_tuned_count_evaluation"
    else:
        base = ROOT / "results/experiments/spatial_msipl_cac_attributed_peak_evaluation"
    parent = base / f"{section}_seed1"
    central = read_json(parent / "central_only/summary.json")["matched_peak_evaluation"]
    spatial = read_json(parent / "uniform_mean/summary.json")["matched_peak_evaluation"]
    if central["count"] != spatial["count"]:
        raise ValueError(f"different centre and spatial budgets: {section}")
    def metric(evaluation, method):
        values = evaluation["methods"][method]
        f1_scores = []
        for threshold in ("0.3", "0.4", "0.5", "0.6"):
            mixed = values["threshold_results"][threshold]["mixed_classes"]
            true_positive = int(mixed["true_positive"])
            false_positive = int(mixed["false_positive"])
            false_negative = int(mixed["false_negative"])
            denominator = 2 * true_positive + false_positive + false_negative
            f1 = 2 * true_positive / denominator if denominator else 0.0
            if abs(f1 - float(mixed["F1"])) > 1e-10:
                raise ValueError(f"F1 mismatch: {collection}/{section}/{method}/{threshold}")
            f1_scores.append(f1)
        mscf1 = statistics.mean(f1_scores)
        if abs(mscf1 - float(values["mSCF1"])) > 1e-10:
            raise ValueError(f"mSCF1 mismatch: {collection}/{section}/{method}")
        return mscf1
    centre = metric(central, "integrated_gradients")
    context = metric(spatial, "integrated_gradients")
    return {
        "collection": collection, "section": section,
        "matched_peaks": int(spatial["count"]),
        "legacy_msipl": metric(spatial, "legacy_msipl"),
        "central_ig": centre, "spatial_ig": context,
        "spatial_l2": metric(spatial, "first_layer_l2"),
        "context_delta": context - centre,
    }


def compare_rows(expected, published):
    differences = []
    lookup = {(row["collection"], row["section"]): row for row in published}
    if len(lookup) != len(expected):
        differences.append(f"published section count {len(lookup)} != {len(expected)}")
    for row in expected:
        key = (row["collection"], row["section"])
        if key not in lookup:
            differences.append(f"missing published section {key}")
            continue
        actual = lookup[key]
        for field in ("matched_peaks", "legacy_msipl", "central_ig", "spatial_ig",
                      "spatial_l2", "context_delta"):
            value = int(actual[field]) if field == "matched_peaks" else float(actual[field])
            if abs(value - row[field]) > 1e-10:
                differences.append({"collection": key[0], "section": key[1],
                                    "field": field, "source": row[field], "published": value})
    return differences


def expected_aggregates(rows):
    result = []
    for collection in ("GBM", "CAC"):
        subset = [row for row in rows if row["collection"] == collection]
        for key, label in METHODS.items():
            values = [row[key] for row in subset]
            result.append({
                "collection": collection, "method": label, "sections": len(values),
                "mean_mSCF1": statistics.mean(values),
                "section_sd": statistics.stdev(values),
                "median_mSCF1": statistics.median(values),
                "minimum_mSCF1": min(values), "maximum_mSCF1": max(values),
            })
    return result


def compare_aggregates(expected, published):
    differences = []
    lookup = {(row["collection"], row["method"]): row for row in published}
    if len(lookup) != len(expected):
        differences.append(f"published method count {len(lookup)} != {len(expected)}")
    for row in expected:
        key = (row["collection"], row["method"])
        if key not in lookup:
            differences.append(f"missing published method {key}")
            continue
        for field in ("sections", "mean_mSCF1", "section_sd", "median_mSCF1",
                      "minimum_mSCF1", "maximum_mSCF1"):
            value = int(lookup[key][field]) if field == "sections" else float(lookup[key][field])
            if abs(value - row[field]) > 1e-10:
                differences.append({"collection": key[0], "method": key[1],
                                    "field": field, "source": row[field], "published": value})
    return differences


def main():
    rows = [source_row("GBM", section) for section in GBM]
    rows += [source_row("CAC", section) for section in CAC]
    aggregates = expected_aggregates(rows)
    section_differences = compare_rows(rows, read_csv(PUBLICATION / "section_level_results.csv"))
    aggregate_differences = compare_aggregates(
        aggregates, read_csv(PUBLICATION / "aggregate_method_results.csv"))
    report = {
        "status": "valid" if not section_differences and not aggregate_differences else "mismatch",
        "source": "16 saved section-level matched-count evaluation summaries; F1 and mSCF1 recomputed from counts",
        "section_count": len(rows), "method_count": len(aggregates),
        "source_rows": rows, "source_aggregates": aggregates,
        "publication_section_differences": section_differences,
        "publication_aggregate_differences": aggregate_differences,
        "limits": ["The earlier raw-spectrum A3 score audit covered existing baseline lists, but not the GBM tuned-count lists used here.",
                   "This audit recalculates F1/mSCF1 from saved confusion counts; it does not recalculate tuned-count PCC references from source spectra.",
                   "This check does not rerun training, attribution, or S3PL evaluation.",
                   "It checks the primary section and aggregate CSVs, not figures or prose."],
    }
    output = ROOT / "results/diagnostics/spatial_publication_aggregate/summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "section_differences": len(section_differences),
                      "aggregate_differences": len(aggregate_differences),
                      "output": str(output)}, indent=2))
    if report["status"] != "valid":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
