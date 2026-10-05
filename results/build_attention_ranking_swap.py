"""Build local figures from the completed frozen-attention ranking-swap outputs.

Run from the repository root with a Python environment containing NumPy and
Pillow. This reads cluster-synced evidence but writes only to the local gallery.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "code/msi/results/diagnostics/spatial_attention_frozen_ranking_swap"
DESTINATION = ROOT / "results/model-comparisons"
SECTIONS = (
    "40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL",
    "400TopL", "520TopL", "GBM108_positive", "GBM108_negative",
    "GBM12_1", "GBM12_2", "GBM22_1", "GBM22_2", "GBM39_1", "GBM39_2",
)

INK = "#24313D"
MUTED = "#687480"
GRID = "#DCE2E7"
REAL = "#31688E"
SHUFFLED = "#C47032"
TURNOVER = "#6D7181"
BACKGROUND = "#FFFFFF"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "arialbd.ttf" if bold else "arial.ttf"
    path = Path("C:/Windows/Fonts") / name
    if not path.is_file():
        raise FileNotFoundError(f"Required figure font is unavailable: {path}")
    return ImageFont.truetype(str(path), size)


TITLE = font(43, True)
SUBTITLE = font(25)
LABEL = font(27)
SMALL = font(22)
SMALL_BOLD = font(22, True)
TICK = font(20)


def load_rows() -> tuple[list[dict], list[dict]]:
    summary_rows: list[dict] = []
    changed_rows: list[dict] = []
    for section in SECTIONS:
        directory = SOURCE / section
        summary_path = directory / "summary.json"
        rankings_path = directory / "rankings.npz"
        if not summary_path.is_file() or not rankings_path.is_file():
            raise FileNotFoundError(f"Incomplete synced result for {section}")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("status") != "valid" or summary.get("section") != section:
            raise ValueError(f"Ranking swap is not valid for {section}")
        count = int(summary["matched_count"])
        with np.load(rankings_path) as rankings:
            mz = rankings["mz"].copy()
            real = rankings["real_indices"].astype(int).copy()
            shuffled = rankings["shuffled_indices"].astype(int).copy()
        if any(len(values) != count or len(set(values.tolist())) != count
               for values in (real, shuffled)):
            raise ValueError(f"Selected-bin budget or uniqueness failed for {section}")
        if any(np.any(values < 0) or np.any(values >= len(mz))
               for values in (real, shuffled)):
            raise ValueError(f"Selected-bin index outside the m/z axis for {section}")
        real_set, shuffled_set = set(real.tolist()), set(shuffled.tolist())
        shared = len(real_set & shuffled_set)
        if shared != int(summary["matched_peak_overlap"]):
            raise ValueError(f"Saved overlap disagrees with rankings for {section}")
        real_score = float(summary["real"]["mSCF1"])
        shuffled_score = float(summary["shuffled"]["mSCF1"])
        delta = shuffled_score - real_score
        if not math.isclose(delta, float(summary["shuffled_minus_real_mSCF1"]), abs_tol=1e-10):
            raise ValueError(f"Saved score difference disagrees for {section}")
        changed_each = count - shared
        summary_rows.append({
            "collection": "CAC" if section.endswith("TopL") else "GBM",
            "section": section,
            "matched_peaks": count,
            "real_mSCF1": real_score,
            "shuffled_mSCF1": shuffled_score,
            "shuffled_minus_real_mSCF1": delta,
            "shared_bins": shared,
            "changed_bins_each_ranking": changed_each,
            "fraction_replaced": changed_each / count,
        })
        for condition, ranked, exclusive in (
            ("real_only", real, real_set - shuffled_set),
            ("shuffled_only", shuffled, shuffled_set - real_set),
        ):
            for rank, index in enumerate(ranked, start=1):
                if int(index) in exclusive:
                    changed_rows.append({
                        "collection": summary_rows[-1]["collection"],
                        "section": section,
                        "condition": condition,
                        "rank_in_selected_list": rank,
                        "bin_index": int(index),
                        "mz": float(mz[index]),
                    })
    return summary_rows, changed_rows


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def row_positions() -> list[int]:
    return [270 + index * 58 for index in range(len(SECTIONS))]


def draw_cohort_divider(draw: ImageDraw.ImageDraw, positions: list[int]) -> None:
    boundary = (positions[7] + positions[8]) // 2
    draw.line((58, boundary, 1970, boundary), fill=GRID, width=2)


def draw_overview(rows: list[dict], path: Path) -> None:
    image = Image.new("RGB", (2040, 1360), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text((58, 44), "Frozen attention: what changes when neighbours are shuffled?",
              fill=INK, font=TITLE)
    draw.text((58, 106), "Same checkpoint, GMM, attribution pixels and matched peak budget",
              fill=MUTED, font=SUBTITLE)
    draw.text((447, 177), "mSCF1 change (shuffled minus real)", fill=INK, font=SMALL_BOLD)
    draw.text((1390, 177), "Selected bins replaced", fill=INK, font=SMALL_BOLD)
    positions = row_positions()
    draw_cohort_divider(draw, positions)
    zero = 800
    score_half_width = 333
    for tick in (-0.06, -0.04, -0.02, 0, 0.02, 0.04, 0.06):
        x = round(zero + tick / 0.06 * score_half_width)
        draw.line((x, 229, x, positions[-1] + 28), fill=GRID if tick else INK,
                  width=2 if tick else 3)
        draw.text((x, 220), f"{tick:+.2f}" if tick else "0", fill=MUTED,
                  font=TICK, anchor="ms")
    turnover_left, turnover_width = 1400, 355
    for tick in (0, 5, 10, 15, 20, 25):
        x = turnover_left + round(tick / 25 * turnover_width)
        draw.line((x, 229, x, positions[-1] + 28), fill=GRID, width=2)
        draw.text((x, 220), f"{tick}%", fill=MUTED, font=TICK, anchor="ms")
    for row, y in zip(rows, positions):
        draw.text((58, y), row["section"], fill=INK, font=LABEL, anchor="lm")
        delta = row["shuffled_minus_real_mSCF1"]
        target = round(zero + delta / 0.06 * score_half_width)
        colour = SHUFFLED if delta >= 0 else REAL
        draw.rectangle((min(zero, target), y - 11, max(zero, target), y + 11),
                       fill=colour)
        draw.text((1173, y), f"{delta:+.3f}", fill=INK, font=SMALL,
                  anchor="lm")
        fraction = row["fraction_replaced"]
        bar_end = turnover_left + round(fraction / 0.25 * turnover_width)
        draw.rectangle((turnover_left, y - 9, bar_end, y + 9), fill=TURNOVER)
        draw.text((1792, y), f"{fraction:.1%}", fill=INK, font=SMALL,
                  anchor="lm")
    draw.rectangle((58, 1215, 82, 1239), fill=REAL)
    draw.text((94, 1227), "Real neighbours score higher", fill=INK,
              font=SMALL, anchor="lm")
    draw.rectangle((455, 1215, 479, 1239), fill=SHUFFLED)
    draw.text((491, 1227), "Shuffled neighbours score higher", fill=INK,
              font=SMALL, anchor="lm")
    draw.text((58, 1278), "The shuffle is an input intervention, not a retrained model; expert masks are used only for scoring.",
              fill=MUTED, font=SMALL)
    image.save(path, optimize=True)


def draw_changed_mz(rows: list[dict], changed: list[dict], path: Path) -> None:
    image = Image.new("RGB", (2040, 1360), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text((58, 44), "Where did the selected peaks change?", fill=INK, font=TITLE)
    draw.text((58, 106), "m/z locations of bins selected by only one ranking; shared bins are omitted",
              fill=MUTED, font=SUBTITLE)
    positions = row_positions()
    draw_cohort_divider(draw, positions)
    x_left, x_right = 435, 1830
    mz_min, mz_max = 100, 1080
    def x_coord(mz: float) -> int:
        return round(x_left + (mz - mz_min) / (mz_max - mz_min) * (x_right - x_left))
    for tick in (100, 300, 500, 700, 900, 1080):
        x = x_coord(tick)
        draw.line((x, 235, x, positions[-1] + 26), fill=GRID, width=2)
        draw.text((x, 220), str(tick), fill=MUTED, font=TICK, anchor="ms")
    draw.text(((x_left + x_right) // 2, 1218), "Mass-to-charge ratio (m/z)",
              fill=INK, font=SMALL_BOLD, anchor="mm")
    by_section: dict[str, list[dict]] = {row["section"]: [] for row in rows}
    for item in changed:
        by_section[item["section"]].append(item)
    for row, y in zip(rows, positions):
        draw.text((58, y), row["section"], fill=INK, font=LABEL, anchor="lm")
        draw.line((x_left, y, x_right, y), fill=GRID, width=1)
        for item in by_section[row["section"]]:
            colour, offset = (REAL, -7) if item["condition"] == "real_only" else (SHUFFLED, 7)
            x = x_coord(item["mz"])
            draw.ellipse((x - 4, y + offset - 4, x + 4, y + offset + 4), fill=colour)
        draw.text((1852, y), f"{row['changed_bins_each_ranking']} each",
                  fill=MUTED, font=SMALL, anchor="lm")
    draw.ellipse((58, 1260, 76, 1278), fill=REAL)
    draw.text((90, 1269), "Real-only", fill=INK, font=SMALL, anchor="lm")
    draw.ellipse((290, 1260, 308, 1278), fill=SHUFFLED)
    draw.text((322, 1269), "Shuffled-only", fill=INK, font=SMALL, anchor="lm")
    draw.text((595, 1269), "Exact bin indices, m/z values and ranks are in the accompanying CSV.",
              fill=MUTED, font=SMALL, anchor="lm")
    image.save(path, optimize=True)


def main() -> None:
    rows, changed = load_rows()
    DESTINATION.mkdir(parents=True, exist_ok=True)
    write_csv(DESTINATION / "attention_frozen_ranking_swap_sections.csv", rows)
    write_csv(DESTINATION / "attention_frozen_ranking_changed_bins.csv", changed)
    draw_overview(rows, DESTINATION / "attention_frozen_ranking_swap_overview.png")
    draw_changed_mz(rows, changed, DESTINATION / "attention_frozen_ranking_changed_mz.png")
    print(f"Validated {len(rows)}/16 sections; saved {len(changed)} exclusive-bin records in {DESTINATION}")


if __name__ == "__main__":
    main()
