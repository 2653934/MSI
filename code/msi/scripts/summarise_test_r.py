#!/usr/bin/env python3
"""Test R decision tables (protocol 18 Section 6.3; supervisor chat 2026-10-17 09:45).

Reads the fair-scoring summaries of training seeds 1 (production roots), 2 and 3
(test_r roots) and applies the predeclared decisions per collection x arm:

1. Headline replication, IG vs posterior-|PCC|: "replicates at seed s" if IG is
   below posterior-|PCC| in >= 7/8 sections and the mean difference <= -0.02, at
   every applicable scale (GBM/CAC bin level and P1; RCC bin level). The headline
   holds overall if it replicates at both seeds 2 and 3 in every collection x arm
   with a complete seed; every failure and every incomplete seed is listed.
2. Context, IG(uniform_mean) - IG(central_only): per section, the mean over seeds
   1-3, then the Section 7 rule over the 8 seed-averaged differences ("helps":
   mean >= +0.02 and >= 6/8 positive; "equivalent": |mean| < 0.02; otherwise
   "mixed"), at every applicable scale. Each seed's own label and the per-section
   seed SD are also reported; the seed-1 label is superseded by the 3-seed label.
3. Descriptive: per-section seed SD of IG and posterior-|PCC|, GMM balanced
   accuracy per seed, and Moran's I vs posterior-|PCC| on RCC per seed.
Fewer than 8 sections at a seed (or with all three seeds, for decision 2) gives
"incomplete". Seed SDs are sample SDs (ddof = 1). Refuses mixed evaluator code or
parameters within a seed and collection, a K_bin that differs between seeds,
summaries whose attribution path is not the expected seed root, and a missing P1
on GBM/CAC (or a P1 on RCC). Local files only; no interpretation.

Opt-in --ig-steps-allow-list (protocol 18 Section 6.3, IG completeness reruns;
supervisor chat 2026-10-30 16:53): the summary.json of summarise_ig_steps.py. A
seed-2/3 arm listed there with an integer decision step N may come from the rerun
folder, and only if its recorded latent_mean.npy path equals exactly
<cluster root>/results/experiments/ig_steps_rerun_20261030/<section>_seed<S>/<arm>/
steps<N>/attribution/latent_mean.npy (trailing slash normalised; supervisor chat
2026-10-30 17:03) and gmm_gate_v2.json beside it shows a pass. Seed 1 and every other arm keep the
check above. Without the option the behaviour is unchanged.
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FAIR = ROOT / "results" / "diagnostics" / "fair_scoring_baselines"
CLUSTER_PREFIX = "/home-mscluster/zsuliman/msi/"
PRACTICAL = 0.02
REPLICATE_BELOW = 7
HELPS_POSITIVE = 6
N_SECTIONS = 8
SEEDS = (1, 2, 3)
NEW_SEEDS = (2, 3)
ARMS = ("central_only", "uniform_mean")
SECTIONS = {
    "RCC": ("RCC_MH0204_33", "RCC_UH0505_12", "RCC_UH0710_33", "RCC_UH9610_15",
            "RCC_UH9812_03", "RCC_UH9905_18", "RCC_UH9911_05", "RCC_UH9912_01"),
    "CAC": ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL", "400TopL",
            "520TopL"),
    "GBM": ("GBM108_negative", "GBM108_positive", "GBM12_1", "GBM12_2", "GBM22_1",
            "GBM22_2", "GBM39_1", "GBM39_2"),
}
SCALES = {"RCC": ("bin",), "CAC": ("bin", "P1"), "GBM": ("bin", "P1")}
IG, POSTERIOR, MORANS = "integrated_gradients", "posterior_abs_pcc_balanced", "morans_i"
NOTES = {
    "GBM": "8 sections from 4 patients; sections are not independent patients",
    "CAC": ("CAC P1 is singleton groups (1,481 for 1,481 bins), so its peak-level score is "
            "the bin-level score at the K_peak budget; requiring both is a two-budget check, "
            "not an independent partition check"),
    "RCC": ("bin level only (protocol 18 Section 6.1 amendment, 17 October); unannotated "
            "class, 45-78% of pixels; the dataset's own Cardinal workflow treats these "
            "pixels as background (rcc_nobg), but this was not independently verified; "
            "GMM K = 3 is class-informed"),
}


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fair-root", type=Path, default=FAIR)
    parser.add_argument("--project-root", type=Path, default=ROOT,
                        help="workspace root for the matched-evaluation summaries")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ig-steps-allow-list", type=Path, default=None,
                        help="summarise_ig_steps.py summary.json; see the module docstring")
    return parser.parse_args()


RERUN_ROOT = "ig_steps_rerun_20261030"


def read_allow_list(path):
    """{(section, seed, arm): N} for seed-2/3 arms with an integer decision step."""
    if path is None:
        return {}
    decisions = json.loads(Path(path).read_text(encoding="utf-8"))["decision_steps"]
    allowed = {}
    for key, steps in decisions.items():
        section, seed, arm = key.split()
        if not seed.startswith("s") or not isinstance(steps, int) or isinstance(steps, bool):
            continue
        if int(seed[1:]) in NEW_SEEDS:
            allowed[(section, int(seed[1:]), arm)] = steps
    return allowed


def rerun_attribution_allowed(attribution, section, arm, seed, allow_list, project_root):
    """True only for a listed arm at its listed step whose gate v2 passed."""
    steps = allow_list.get((section, seed, arm))
    if steps is None:
        return False
    # Exact match (supervisor chat 2026-10-30 17:03): the recorded latent_mean.npy must
    # sit directly in the single expected rerun folder; only a trailing slash is normalised.
    expected = (f"{CLUSTER_PREFIX}results/experiments/{RERUN_ROOT}/{section}_seed{seed}/"
                f"{arm}/steps{steps}/attribution")
    directory, _, name = attribution.rpartition("/")
    if name != "latent_mean.npy" or directory.rstrip("/") != expected:
        return False
    local = project_root / attribution.replace(CLUSTER_PREFIX, "")
    gate = local.parent.parent / "gmm_gate_v2.json"
    if not gate.is_file():
        return False
    return json.loads(gate.read_text(encoding="utf-8")).get("passed") is True


def summary_path(fair_root, collection, section, arm, seed):
    if seed == 1:
        scope = (fair_root / "rcc" / "bin_level_only" if collection == "RCC"
                 else fair_root / "with_approved_partitions")
    else:
        scope = fair_root / "test_r" / ("bin_level_only" if collection == "RCC"
                                        else "with_approved_partitions")
    return scope / f"{section}_seed{seed}" / arm / "summary.json"


def expected_attribution(section, arm, seed):
    """Fragment the summary's attribution path must contain."""
    if seed == 1:
        return f"/{section}_seed1/"
    return f"/test_r_training_seeds/{section}_seed{seed}/{arm}/attribution/"


def balanced_accuracy(summary, project_root):
    path = summary["provenance"]["source_artifacts"]["saved_evaluation_summary"]["path"]
    local = project_root / path.replace(CLUSTER_PREFIX, "")
    if not local.is_file():
        return None
    return json.loads(local.read_text(encoding="utf-8")).get("cluster_mapping", {}).get(
        "balanced_accuracy")


def load(fair_root, project_root, allow_list=None):
    allow_list = allow_list or {}
    records, keys, k_bins = {}, {}, {}
    for collection, sections in SECTIONS.items():
        for section in sections:
            for arm in ARMS:
                for seed in SEEDS:
                    path = summary_path(fair_root, collection, section, arm, seed)
                    if not path.is_file():
                        continue
                    summary = json.loads(path.read_text(encoding="utf-8"))
                    where = f"{path}"
                    if summary.get("status") != "complete" or summary.get("dataset") != section:
                        raise SystemExit(f"{where}: not a complete fair-scoring result")
                    if summary.get("class_subset") is not None:
                        raise SystemExit(f"{where}: class-subset analysis")
                    attribution = summary["provenance"]["source_artifacts"]["latent_mean"]["path"]
                    if (expected_attribution(section, arm, seed) not in attribution
                            and not rerun_attribution_allowed(attribution, section, arm, seed,
                                                              allow_list, project_root)):
                        raise SystemExit(f"{where}: attribution {attribution} is not the "
                                         f"seed-{seed} root")
                    has_p1 = "P1" in summary.get("peak_level", {})
                    if has_p1 != ("P1" in SCALES[collection]):
                        raise SystemExit(f"{where}: P1 {'present' if has_p1 else 'missing'} "
                                         f"for {collection}")
                    k_bins.setdefault(section, set()).add(int(summary["K_bin"]))
                    prov = summary["provenance"]
                    keys.setdefault((seed, collection), set()).add(json.dumps({
                        "evaluation_version": prov["evaluation_version"],
                        "parameters": prov["parameters"],
                        "approval": (prov["partition_approval"] or {}).get("sha256"),
                        "code": prov["code"]}, sort_keys=True))
                    row = {"bin": {name: summary["bin_level"][name]["1.0"]["mSCF1"]
                                   for name in (IG, POSTERIOR, MORANS)}}
                    if has_p1:
                        methods = summary["peak_level"]["P1"]["methods"]
                        row["P1"] = {name: methods[name]["matched_K_peak"]["mSCF1"]
                                     for name in (IG, POSTERIOR, MORANS)}
                    row["balanced_accuracy"] = balanced_accuracy(summary, project_root)
                    row["K_bin"] = int(summary["K_bin"])
                    records[(collection, section, arm, seed)] = row
    for (seed, collection), values in keys.items():
        if len(values) != 1:
            raise SystemExit(f"seed {seed} {collection}: summaries come from different "
                             "evaluator code, parameters or approvals")
    for section, values in k_bins.items():
        if len(values) != 1:
            raise SystemExit(f"{section}: K_bin differs between seeds {sorted(values)}")
    if not records:
        raise SystemExit(f"no fair-scoring summaries under {fair_root}")
    return records


def paired(differences):
    d = np.asarray(differences, dtype=np.float64)
    return {"sections": int(len(d)), "mean_difference": float(d.mean()) if len(d) else None,
            "median_difference": float(np.median(d)) if len(d) else None,
            "positive_sections": int(np.sum(d > 0)), "negative_sections": int(np.sum(d < 0)),
            "per_section": d.tolist()}


def replication(by_scale):
    """Decision 1 for one collection x arm x seed."""
    n = min(r["sections"] for r in by_scale.values())
    if n != N_SECTIONS:
        return f"incomplete ({n}/{N_SECTIONS} sections)"
    if all(r["negative_sections"] >= REPLICATE_BELOW and r["mean_difference"] <= -PRACTICAL
           for r in by_scale.values()):
        return "replicates"
    return "does not replicate"


def context_rule(by_scale):
    """Section 7 rule (decision 2) over the paired records of every applicable scale."""
    n = min(r["sections"] for r in by_scale.values())
    if n != N_SECTIONS:
        return f"incomplete ({n}/{N_SECTIONS} sections)"
    if all(r["mean_difference"] >= PRACTICAL and r["positive_sections"] >= HELPS_POSITIVE
           for r in by_scale.values()):
        return "helps"
    if all(abs(r["mean_difference"]) < PRACTICAL for r in by_scale.values()):
        return "equivalent"
    return "mixed"


def seed_sd(values):
    return float(np.std(values, ddof=1)) if len(values) >= 2 else None


def main():
    args = parse_arguments()
    allow_list = read_allow_list(args.ig_steps_allow_list)
    records = load(args.fair_root, args.project_root, allow_list)

    def value(collection, section, arm, seed, scale, name):
        row = records.get((collection, section, arm, seed))
        return None if row is None else row[scale][name]

    decision1, failures, incomplete = {}, [], []
    decision2, decision3 = {}, {}
    for collection, sections in SECTIONS.items():
        scales = SCALES[collection]
        for arm in ARMS:
            for seed in SEEDS:
                by_scale = {}
                for scale in scales:
                    present = [s for s in sections
                               if (collection, s, arm, seed) in records]
                    by_scale[scale] = paired(
                        [value(collection, s, arm, seed, scale, IG)
                         - value(collection, s, arm, seed, scale, POSTERIOR) for s in present])
                    by_scale[scale]["section_names"] = present
                label = replication(by_scale)
                decision1[f"{collection}/{arm}/seed{seed}"] = {
                    "label": label, "role": "reference" if seed == 1 else "replication",
                    "IG_minus_posterior": by_scale}
                if seed in NEW_SEEDS:
                    if label.startswith("incomplete"):
                        incomplete.append(f"{collection}/{arm}/seed{seed}: {label}")
                    elif label != "replicates":
                        failures.append(f"{collection}/{arm}/seed{seed}")

            # Decision 3, per arm: seed SDs, balanced accuracy, RCC Moran's I.
            sd = {}
            for scale in scales:
                for name in (IG, POSTERIOR):
                    per_section = {}
                    for s in sections:
                        values = [value(collection, s, arm, seed, scale, name) for seed in SEEDS
                                  if (collection, s, arm, seed) in records]
                        per_section[s] = {"seeds": len(values), "sd": seed_sd(values)}
                    finite = [v["sd"] for v in per_section.values() if v["sd"] is not None]
                    sd[f"{scale}:{name}"] = {
                        "per_section": per_section,
                        "median_sd": float(np.median(finite)) if finite else None,
                        "max_sd": float(np.max(finite)) if finite else None}
            accuracy = {}
            for seed in SEEDS:
                values = {s: records[(collection, s, arm, seed)]["balanced_accuracy"]
                          for s in sections if (collection, s, arm, seed) in records}
                known = [v for v in values.values() if v is not None]
                accuracy[f"seed{seed}"] = {"mean": float(np.mean(known)) if known else None,
                                           "sections": len(known), "per_section": values}
            record = {"seed_sd": sd, "gmm_balanced_accuracy": accuracy}
            if collection == "RCC":
                morans = {}
                for seed in SEEDS:
                    present = [s for s in sections if (collection, s, arm, seed) in records]
                    diff = [value(collection, s, arm, seed, "bin", MORANS)
                            - value(collection, s, arm, seed, "bin", POSTERIOR) for s in present]
                    morans[f"seed{seed}"] = paired(diff)
                record["morans_i_minus_posterior_bin"] = morans
            decision3[f"{collection}/{arm}"] = record

        # Decision 2, per collection: uniform_mean - central_only IG.
        per_seed, averaged, section_sd = {}, {}, {}
        for scale in scales:
            diffs = {}
            for s in sections:
                for seed in SEEDS:
                    if all((collection, s, a, seed) in records for a in ARMS):
                        diffs.setdefault(s, {})[seed] = (
                            value(collection, s, "uniform_mean", seed, scale, IG)
                            - value(collection, s, "central_only", seed, scale, IG))
            for seed in SEEDS:
                present = [s for s in sections if seed in diffs.get(s, {})]
                per_seed.setdefault(f"seed{seed}", {})[scale] = paired(
                    [diffs[s][seed] for s in present])
            complete = [s for s in sections if len(diffs.get(s, {})) == len(SEEDS)]
            averaged[scale] = paired([np.mean(list(diffs[s].values())) for s in complete])
            averaged[scale]["section_names"] = complete
            section_sd[scale] = {s: seed_sd([diffs[s][seed] for seed in SEEDS])
                                 for s in complete}
        seed_labels = {seed: context_rule(by_scale) for seed, by_scale in per_seed.items()}
        three_seed = context_rule(averaged)
        decision2[collection] = {
            "three_seed_label": three_seed, "seed1_label": seed_labels["seed1"],
            "seed1_label_superseded_by_three_seed_label": True,
            "labels_differ": seed_labels["seed1"] != three_seed,
            "per_seed_labels": seed_labels, "seed_averaged": averaged,
            "per_seed": per_seed, "per_section_seed_sd": section_sd,
            "metric": "IG mSCF1 at K_bin (bin) and P1 matched K_peak; uniform_mean - central_only"}

    complete_new = [k for k, v in decision1.items()
                    if v["role"] == "replication" and not v["label"].startswith("incomplete")]
    decisions = {
        "decision_1": {
            "headline_holds_overall": (not failures) and bool(complete_new),
            "failures": failures, "incomplete": incomplete,
            "rule": "IG below posterior-|PCC| in >= 7/8 sections and mean <= -0.02 at every "
                    "applicable scale, at seeds 2 and 3, in every collection x arm with a "
                    "complete seed",
            "per_collection_arm_seed": decision1},
        "decision_2": decision2,
        "decision_3": decision3,
        "notes": NOTES,
        "sd_definition": "sample standard deviation over the available seeds (ddof = 1)",
    }
    if args.ig_steps_allow_list is not None:
        decisions["ig_steps_allow_list"] = {
            "source": str(args.ig_steps_allow_list),
            "arms": {f"{section} s{seed} {arm}": steps
                     for (section, seed, arm), steps in sorted(allow_list.items())},
            "rule": ("protocol 18 Section 6.3 IG completeness reruns; rerun root accepted only "
                     "for these arms at these steps with a passing gmm_gate_v2.json")}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "decisions.json").write_text(json.dumps(decisions, indent=2) + "\n",
                                                encoding="utf-8")
    rows = []
    for (collection, section, arm, seed), row in sorted(records.items()):
        for scale in SCALES[collection]:
            rows.append({"collection": collection, "section": section, "arm": arm,
                         "seed": seed, "scale": scale, "K_bin": row["K_bin"],
                         "ig_mSCF1": row[scale][IG], "posterior_mSCF1": row[scale][POSTERIOR],
                         "morans_i_mSCF1": row[scale][MORANS],
                         "gmm_balanced_accuracy": row["balanced_accuracy"]})
    with open(args.output / "section_table.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("decision 1 headline holds overall:", decisions["decision_1"]["headline_holds_overall"])
    for key, record in decision1.items():
        print(f"  {key}: {record['label']}")
    for collection, record in decision2.items():
        print(f"decision 2 {collection}: three-seed {record['three_seed_label']}; "
              f"per seed {record['per_seed_labels']}")


if __name__ == "__main__":
    main()
