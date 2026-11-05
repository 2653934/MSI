"""Build the report's runtime figure from committed timing data only.

Source: code/msi/results/comparisons/s3pl_gbm_stability_runtime/runtime_repeats.csv,
the complete CAC 160TopL workflow (three repeats). S3PL is shown as one bar;
the VAE workflow is split into training, GMM fit + IG ranking and peak scoring.
Ranking-stage times per collection are reported in the text of the Results.

Run from anywhere: python report/draft/figures/runtime_figure.py
The script writes the source TeX and compiles images/runtime_figure.pdf.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIGURES = ROOT / "report" / "draft" / "figures"
WORKFLOW = ROOT / "code" / "msi" / "results" / "comparisons" / "s3pl_gbm_stability_runtime" / "runtime_repeats.csv"

STAGES = (
    ("vae_train", "train", "VAE training"),
    ("vae_attribution", "rank", "GMM fit + IG ranking"),
    ("vae_peak_evaluation", "score", "Peak scoring"),
)


def workflow_data() -> list[dict[str, float]]:
    subprocess.run(["git", "ls-files", "--error-unmatch", "--",
                    str(WORKFLOW.relative_to(ROOT)).replace("\\", "/")],
                   cwd=ROOT, check=True, capture_output=True, text=True)
    with WORKFLOW.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    runs = []
    for job in sorted({r["job_id"] for r in rows}):
        runs.append({r["stage"]: float(r["wall_seconds"]) for r in rows if r["job_id"] == job})
    if len(runs) != 3:
        raise ValueError("Expected three workflow repeats")
    totals = sorted(round(sum(r[s] for s, _, _ in STAGES)) for r in runs)
    s3pl = sorted(round(r["s3pl_full"]) for r in runs)
    if totals[0] != 122 or totals[-1] != 135 or s3pl[0] != 151 or s3pl[-1] != 174:
        raise ValueError(f"Workflow totals changed: {totals} {s3pl}")
    return runs


def make_tex(runs: list[dict[str, float]]) -> str:
    x0, width, smax = 1.25, 6.3, 200.0
    sc = width / smax
    bar = 0.26
    lines = [
        r"\documentclass[tikz,border=1mm]{standalone}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage{lmodern}",
        r"\definecolor{s3pl}{HTML}{9A9A9A}",
        r"\definecolor{train}{HTML}{1F4E79}",
        r"\definecolor{rank}{HTML}{4A86C5}",
        r"\definecolor{score}{HTML}{A9CBEA}",
        r"\begin{document}",
        r"\begin{tikzpicture}[x=1cm,y=1cm,font=\sffamily\footnotesize]",
    ]
    legend = (("s3pl", r"S\textsuperscript{3}PL, whole workflow", 0.0, 0.0),
              ("train", STAGES[0][2], 0.0, -0.38),
              ("rank", STAGES[1][2], 4.05, 0.0),
              ("score", STAGES[2][2], 4.05, -0.38))
    top = 3.55
    for colour, label, dx, dy in legend:
        x, y = x0 - 1.2 + dx, top + dy
        lines.append(f"\\fill[{colour}] ({x:.2f},{y-.09:.2f}) rectangle ({x+.22:.2f},{y+.09:.2f});")
        lines.append(f"\\node[anchor=west] at ({x+.26:.2f},{y:.2f}) {{{label}}};")
    for tick in range(0, 201, 50):
        x = x0 + tick * sc
        lines.append(f"\\draw[black!10] ({x:.3f},0.15) -- ({x:.3f},2.95);")
        lines.append(f"\\draw[black!60] ({x:.3f},0.15) -- ({x:.3f},0.08);")
        lines.append(f"\\node[anchor=north,font=\\sffamily\\scriptsize] at ({x:.3f},0.06) {{{tick}}};")
    lines.append(f"\\draw[black!60] ({x0},0.15) -- ({x0+width},0.15);")
    for i, run in enumerate(runs):
        y = 2.55 - i * 0.85
        lines.append(f"\\node[anchor=east] at ({x0-.12:.2f},{y-bar/2-.02:.3f}) {{Run {i+1}}};")
        w = run["s3pl_full"] * sc
        lines.append(f"\\fill[s3pl] ({x0},{y:.3f}) rectangle ({x0+w:.3f},{y+bar:.3f});")
        lines.append(f"\\node[anchor=west,font=\\sffamily\\scriptsize] at ({x0+w+.05:.3f},{y+bar/2:.3f}) {{{run['s3pl_full']:.0f}\\,s}};")
        x = x0
        yb = y - bar - 0.06
        for stage, colour, _ in STAGES:
            w = run[stage] * sc
            lines.append(f"\\fill[{colour}] ({x:.3f},{yb:.3f}) rectangle ({x+w:.3f},{yb+bar:.3f});")
            lines.append(f"\\draw[white,line width=0.6pt] ({x+w:.3f},{yb:.3f}) -- ({x+w:.3f},{yb+bar:.3f});")
            x += w
        total = sum(run[s] for s, _, _ in STAGES)
        lines.append(f"\\node[anchor=west,font=\\sffamily\\scriptsize] at ({x+.05:.3f},{yb+bar/2:.3f}) {{{total:.0f}\\,s}};")
    lines += [
        f"\\node[anchor=north] at ({x0+width/2:.2f},-0.32) {{Wall time (s)}};",
        r"\end{tikzpicture}",
        r"\end{document}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    runs = workflow_data()
    destination = FIGURES / "runtime_figure.tex"
    destination.write_text(make_tex(runs), encoding="utf-8")
    try:
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", destination.name],
                       cwd=FIGURES, check=True, capture_output=True, text=True)
        shutil.copyfile(FIGURES / "runtime_figure.pdf", ROOT / "report" / "draft" / "images" / "runtime_figure.pdf")
    finally:
        for suffix in ("aux", "log", "pdf"):
            (FIGURES / f"runtime_figure.{suffix}").unlink(missing_ok=True)
    print("Workflow repeats:", runs)


if __name__ == "__main__":
    main()
