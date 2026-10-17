#!/usr/bin/env python3
"""Local descriptive table for the Test V PCA reconstruction addendum."""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PCA_ROOT = ROOT / "results" / "diagnostics" / "pca_reconstruction_V"
VAE_ROOTS = {
    "GBM": ROOT / "results" / "experiments" / "spatial_msipl_reconstruction",
    "CAC": ROOT / "results" / "experiments" / "spatial_msipl_cac_reconstruction",
}
SECTIONS = {
    "GBM": ("GBM108_negative", "GBM108_positive", "GBM12_1", "GBM12_2",
            "GBM22_1", "GBM22_2", "GBM39_1", "GBM39_2"),
    "CAC": ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL",
            "400TopL", "520TopL"),
    "RCC": ("RCC_MH0204_33", "RCC_UH0505_12", "RCC_UH0710_33", "RCC_UH9610_15",
            "RCC_UH9812_03", "RCC_UH9905_18", "RCC_UH9911_05", "RCC_UH9912_01"),
}
CONVENTIONS = ("primary_raw_inverse_transform", "secondary_clip_zero_then_tic")
VAE_MODELS = ("central_only", "uniform_mean")
METRICS = ("mean_squared_error", "mean_absolute_error", "cosine_similarity")
# The predeclared wording rule (protocol 18 Section 6.4 addendum) covers GBM and CAC
# only; RCC has no saved VAE reconstruction and is reported alone.
WORDING_COLLECTIONS = ("GBM", "CAC")
NOTES = (
    "Cosine similarity floors each row norm at 1e-8 separately (the older torch "
    "form); the difference from the product-floor form is negligible at these norms. "
    "Descriptive only (supervisor chat 2026-10-17 21:53, item f).",
)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def collect(pca_root=PCA_ROOT, vae_roots=VAE_ROOTS, sections=SECTIONS):
    rows, keys = [], set()
    for collection, names in sections.items():
        for section in names:
            pca_path = Path(pca_root) / collection / f"{section}_seed1" / "summary.json"
            row = {"collection": collection, "section": section, "status": "missing",
                   "source": pca_path.as_posix()}
            if not pca_path.exists():
                rows.append(row)
                continue
            pca = load_json(pca_path)
            provenance = pca.get("provenance", {})
            keys.add(json.dumps({key: provenance.get(key) for key in
                                 ("version", "protocol", "parameters", "code")},
                                sort_keys=True))
            row["status"] = pca.get("status")
            if row["status"] != "complete":
                row["not_done_reason"] = pca.get("not_done_reason")
                rows.append(row)
                continue
            row["pixels"] = pca["pixels"]
            for component in (5, 20):
                for convention in CONVENTIONS:
                    for metric in METRICS:
                        row[f"pca{component}_{convention}_{metric}"] = pca["metrics"][
                            f"pca{component}"][convention][metric]
            if collection in vae_roots:
                vae_path = (Path(vae_roots[collection]) / f"{section}_seed1" /
                            "evaluation" / "comparison.json")
                vae = load_json(vae_path)
                if vae.get("status") != "complete" or vae.get("dataset") != section:
                    raise ValueError(f"invalid VAE comparison: {vae_path}")
                for model in VAE_MODELS:
                    if int(vae["models"][model]["pixels"]) != int(row["pixels"]):
                        raise ValueError(f"pixel count differs in {vae_path}")
                    for metric in METRICS:
                        row[f"vae_{model}_{metric}"] = vae["models"][model][metric]
                row["vae_source"] = vae_path.as_posix()
            rows.append(row)
    if len(keys) > 1:
        raise ValueError("PCA reconstruction results come from different code or settings; "
                         "refusing to mix them in one table")
    return rows


def aggregate(rows, sections=SECTIONS, vae_collections=("GBM", "CAC")):
    summary = {}
    for collection in sections:
        selected = [row for row in rows if row["collection"] == collection]
        complete = [row for row in selected if row["status"] == "complete"]
        record = {"sections_complete": len(complete), "sections_expected": len(selected)}
        if collection not in vae_collections:
            record["comparison"] = "none; no saved VAE reconstruction, reported alone"
        if collection in vae_collections and len(complete) == len(selected):
            comparisons = {}
            for convention in CONVENTIONS:
                comparisons[convention] = {}
                pca_key = f"pca5_{convention}_mean_squared_error"
                for model in VAE_MODELS:
                    vae_key = f"vae_{model}_mean_squared_error"
                    ratios = [row[pca_key] / row[vae_key] for row in complete]
                    comparisons[convention][model] = {
                        "pca5_mse_exceeds_vae_count": int(sum(r > 1.0 for r in ratios)),
                        "sections": len(ratios), "median_pca5_to_vae_mse_ratio": float(np.median(ratios)),
                    }
            record["mse_comparisons"] = comparisons
        summary[collection] = record
    required = [c for c in WORDING_COLLECTIONS if c in sections]
    ready = all(summary[c]["sections_complete"] == summary[c]["sections_expected"]
                for c in required)
    if ready:
        worse = all(summary[c]["mse_comparisons"][convention]["central_only"]
                    ["pca5_mse_exceeds_vae_count"] >= 6
                    for c in required for convention in CONVENTIONS)
        summary["fixed_wording"] = (
            "PCA-5 reconstructs worse than the VAE yet gives equivalent peak ranking."
            if worse else
            "Reconstruction error does not separate PCA-5 from the VAE.")
    else:
        summary["fixed_wording"] = ("not done; one or more GBM or CAC sections are missing "
                                    "or invalid")
    summary["notes"] = list(NOTES)
    return summary


def write_outputs(rows, summary, output):
    output.mkdir(parents=True, exist_ok=True)
    fields = []
    for row in rows:
        fields.extend(key for key in row if key not in fields)
    with (output / "section_table.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    aggregate_rows = []
    for collection in ("GBM", "CAC"):
        comparisons = summary[collection].get("mse_comparisons", {})
        for convention, models in comparisons.items():
            for model, values in models.items():
                aggregate_rows.append({"collection": collection, "pca_metric": convention,
                                       "vae_model": model, **values})
    with (output / "collection_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["collection", "pca_metric", "vae_model", "pca5_mse_exceeds_vae_count",
                  "sections", "median_pca5_to_vae_mse_ratio"]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(aggregate_rows)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PCA_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = collect(args.root)
    summary = aggregate(rows)
    write_outputs(rows, summary, args.output or args.root / "summary_local")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
