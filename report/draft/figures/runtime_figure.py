"""Build the report's runtime figure from committed timing summaries only.

Panel A: code/msi/results/diagnostics/ranking_stage_runtime/*/uniform_mean/
summary.json (GBM and CAC) and ranking_stage_runtime_rcc_bigbatch_shared/
RCC_*/uniform_mean/summary.json (RCC).
Panel B: code/msi/results/publication/current_evidence/runtime_all_sections_v2.csv,
GBM108_positive uniform-context streaming and cached 100-epoch rows.

Run from anywhere: python report/draft/figures/runtime_figure.py
The script writes the source TeX and compiles images/runtime_figure.pdf.
"""

from __future__ import annotations

import csv
import json
import math
import shutil
import statistics
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIGURES = ROOT / "report" / "draft" / "figures"
RESULTS = ROOT / "code" / "msi" / "results"
RANKING = RESULTS / "diagnostics" / "ranking_stage_runtime"
RANKING_RCC = RESULTS / "diagnostics" / "ranking_stage_runtime_rcc_bigbatch_shared"
TRAINING = RESULTS / "publication" / "current_evidence" / "runtime_all_sections_v2.csv"

METHODS = (
    ("Posterior correlation", "corr", "circle"),
    ("Moran's $I$", "moran", "square"),
    ("Mean intensity", "mean", "diamond"),
    ("IG", "ig", "triangle"),
)


def tracked(paths: list[Path]) -> None:
    rel = [str(p.relative_to(ROOT)).replace("\\", "/") for p in paths]
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", *rel],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )


def ranking_data() -> tuple[dict[str, dict[str, float]], list[Path]]:
    output: dict[str, dict[str, float]] = {}
    sources: list[Path] = []
    for collection in ("GBM", "CAC", "RCC"):
        base = RANKING_RCC if collection == "RCC" else RANKING
        paths = sorted(base.glob("*/uniform_mean/summary.json"))
        if collection == "CAC":
            paths = [p for p in paths if not json.loads(p.read_text(encoding="utf-8"))["dataset"].startswith(("GBM", "RCC"))]
        else:
            paths = [p for p in paths if json.loads(p.read_text(encoding="utf-8"))["dataset"].startswith(collection)]
        if len(paths) != 8:
            raise ValueError(f"Expected eight {collection} timing records, found {len(paths)}")
        sources.extend(paths)
        records = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
        if any(r["status"] != "complete" for r in records):
            raise ValueError(f"Incomplete {collection} timing record")
        output[collection] = {
            "Posterior correlation": statistics.median(
                r["posterior_abs_pcc_including_gmm_posterior_median"] for r in records
            ),
            "Moran's $I$": statistics.median(r["stage_seconds_median"]["morans_i"] for r in records),
            "Mean intensity": statistics.median(r["stage_seconds_median"]["mean_intensity"] for r in records),
            "IG": statistics.median(r["integrated_gradients"]["seconds"] for r in records),
        }
    # The rounded values are the verified eight-section summary (C035).
    for collection, expected in {
        "GBM": (1.12, 8.4, 0.10, 770),
        "CAC": (0.028, 0.18, 0.003, 6.0),
        "RCC": (0.11, 0.75, 0.013, 372),
    }.items():
        actual = [output[collection][name] for name, _, _ in METHODS]
        if any(abs(a - e) > max(0.15 * e, 0.001) for a, e in zip(actual, expected)):
            raise ValueError(f"Timing mismatch for {collection}: {actual}")
    return output, sources


def training_data() -> tuple[float, float]:
    with TRAINING.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    selected = [
        row for row in rows
        if row["section"] == "GBM108_positive"
        and row["seed"] == "1"
        and row["method"] in ("vae_uniform_mean", "vae_uniform_mean_cached_rerun")
        and row["epochs"] == "100"
    ]
    if len(selected) != 2 or {r["gpu"] for r in selected} != {"NVIDIA GeForce RTX 3090"}:
        raise ValueError("Audited cache comparison is missing or uses different hardware")
    by_method = {row["method"]: float(row["training_seconds"]) for row in selected}
    streaming = by_method["vae_uniform_mean"]
    cached = by_method["vae_uniform_mean_cached_rerun"]
    if not (40608 < streaming < 40610 and 1355 < cached < 1356):
        raise ValueError("Audited cache times changed")
    return streaming, cached


def marker(x: float, y: float, colour: str, shape: str) -> str:
    at = f"({x:.3f},{y:.3f})"
    if shape == "circle":
        return f"\\fill[{colour}] {at} circle (2.1pt);"
    if shape == "square":
        return f"\\fill[{colour}] ({x-.045:.3f},{y-.045:.3f}) rectangle ({x+.045:.3f},{y+.045:.3f});"
    if shape == "diamond":
        return f"\\fill[{colour}] ({x:.3f},{y+.07:.3f}) -- ({x+.07:.3f},{y:.3f}) -- ({x:.3f},{y-.07:.3f}) -- ({x-.07:.3f},{y:.3f}) -- cycle;"
    return f"\\fill[{colour}] ({x:.3f},{y+.065:.3f}) -- ({x+.07:.3f},{y-.055:.3f}) -- ({x-.07:.3f},{y-.055:.3f}) -- cycle;"


def make_tex(rankings: dict[str, dict[str, float]], streaming: float, cached: float) -> str:
    lines = [
        r"\documentclass[tikz,border=1mm]{standalone}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage{lmodern}",
        r"\definecolor{corr}{HTML}{0072B2}",
        r"\definecolor{moran}{HTML}{D55E00}",
        r"\definecolor{mean}{HTML}{009E73}",
        r"\definecolor{ig}{HTML}{CC79A7}",
        r"\begin{document}",
        r"\begin{tikzpicture}[x=1cm,y=1cm,font=\sffamily\scriptsize]",
        r"\node[anchor=west,font=\sffamily\bfseries\small] at (0,7.18) {A};",
    ]
    for (name, colour, shape), x, y in zip(METHODS, (1.55, 4.48, 1.55, 4.48), (6.85, 6.85, 6.55, 6.55)):
        lines.append(marker(x, y, colour, shape))
        lines.append(f"\\node[anchor=west] at ({x+0.13:.2f},{y:.2f}) {{{name}}};")

    x0, span = 1.55, 6.75
    for i, collection in enumerate(("GBM", "CAC", "RCC")):
        y0 = 5.76 - i * 0.86
        lines.append(f"\\node[anchor=east] at (1.38,{y0:.3f}) {{{collection}}};")
        lines.append(f"\\draw[black!12] (1.48,{y0-.35:.3f}) -- (8.30,{y0-.35:.3f});")
        for j, (name, colour, shape) in enumerate(METHODS):
            value = rankings[collection][name]
            x = x0 + (math.log10(value) + 3) / 6 * span
            y = y0 + (1.5-j) * 0.14
            lines.append(marker(x, y, colour, shape))
    axis_y = 2.94
    lines.append(f"\\draw[black!60] ({x0},{axis_y}) -- ({x0+span},{axis_y});")
    for exponent in range(-3, 4):
        x = x0 + (exponent + 3) / 6 * span
        label = f"$10^{{{exponent}}}$" if exponent else "1"
        lines.append(f"\\draw[black!60] ({x:.3f},{axis_y}) -- ({x:.3f},{axis_y-.07:.3f});")
        lines.append(f"\\node[anchor=north,font=\\sffamily\\tiny] at ({x:.3f},{axis_y-.09:.3f}) {{{label}}};")
    lines.extend([
        r"\node[anchor=north] at (4.93,2.48) {Median ranking time per section (s; log scale)};",
        r"\node[anchor=west,font=\sffamily\bfseries\small] at (0,1.93) {B};",
        r"\node[anchor=east] at (1.43,1.54) {Streaming};",
        r"\node[anchor=east] at (1.43,0.95) {Cached};",
    ])
    for value, colour, y, label in (
        (streaming, "corr", 1.54, f"{streaming/3600:.1f} h"),
        (cached, "mean", 0.95, f"{cached/60:.0f} min"),
    ):
        width = value / (12 * 3600) * 6.2
        lines.append(f"\\fill[{colour}] (1.55,{y-.13:.3f}) rectangle ({1.55+width:.3f},{y+.13:.3f});")
        lines.append(f"\\node[anchor=west] at ({1.65+width:.3f},{y:.3f}) {{{label}}};")
    lines.extend([
        r"\draw[black!60] (1.55,0.60) -- (7.75,0.60);",
        r"\foreach \x/\lab in {1.55/0,4.133/5,6.717/10,7.75/12} {",
        r"  \draw[black!60] (\x,0.60) -- (\x,0.53);",
        r"  \node[anchor=north,font=\sffamily\tiny] at (\x,0.51) {\lab};",
        r"}",
        r"\node[anchor=north] at (4.65,0.18) {100-epoch GBM training time (h)};",
        r"\end{tikzpicture}",
        r"\end{document}",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    rankings, ranking_sources = ranking_data()
    tracked([*ranking_sources, TRAINING])
    streaming, cached = training_data()
    destination = FIGURES / "runtime_figure.tex"
    destination.write_text(make_tex(rankings, streaming, cached), encoding="utf-8")
    try:
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", destination.name],
            cwd=FIGURES, check=True, capture_output=True, text=True,
        )
        shutil.copyfile(FIGURES / "runtime_figure.pdf", ROOT / "report" / "draft" / "images" / "runtime_figure.pdf")
    finally:
        for suffix in ("aux", "log", "pdf"):
            (FIGURES / f"runtime_figure.{suffix}").unlink(missing_ok=True)
    for collection, values in rankings.items():
        print(collection, {name: round(value, 4) for name, value in values.items()})
    print("GBM training seconds:", round(streaming, 2), round(cached, 2))
    print(ROOT / "report" / "draft" / "images" / "runtime_figure.pdf")


if __name__ == "__main__":
    main()
