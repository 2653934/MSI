"""Method-independent m/z peak-group partitions and peak-level scoring.

The partitions here are built only from the m/z axis and the section mean
TIC-normalised spectrum. They never read masks, labels or method outputs.
See docs/research/18 Fair Scoring and Simple Baselines Protocol.md, Section 3.
"""

import hashlib

import numpy as np

THRESHOLDS = (0.3, 0.4, 0.5, 0.6)
ISOTOPE_SPACING_DA = 1.00335

P1_DEFAULTS = {
    "gap_break_ppm": 50.0,
    "smoothing_bins": 3,
    "min_relative_depth": 0.05,
    "max_merge_width_ppm": 100.0,
}
P3_DEFAULTS = {"tolerance_ppm": 20.0}
# S1 is the only hard rejection rule. Group bin counts and proportions (S2) are
# descriptive: bin count depends on axis resolution, not only on physical width.
SANITY_DEFAULTS = {"max_width_da": 0.5, "near_bin_level_singleton_fraction": 0.95}


def validate_axis(mz):
    mz = np.asarray(mz, dtype=np.float64).reshape(-1)
    if len(mz) < 1:
        raise ValueError("m/z axis is empty")
    if not np.all(np.isfinite(mz)) or np.any(mz <= 0):
        raise ValueError("m/z values must be finite and positive")
    if np.any(np.diff(mz) <= 0):
        raise ValueError("m/z axis must be strictly increasing")
    return mz


def adjacent_gap_ppm(mz):
    """Gap from each bin to its left neighbour in ppm of the left value."""
    mz = validate_axis(mz)
    return np.diff(mz) / mz[:-1] * 1e6


def width_ppm(mz, first, last):
    return float((mz[last] - mz[first]) / mz[first] * 1e6)


def group_apexes(group_of_bin, intensity):
    """Apex bin per group: maximum intensity, ties to the lowest index."""
    group_of_bin = np.asarray(group_of_bin, dtype=np.int64)
    intensity = np.asarray(intensity, dtype=np.float64)
    n_groups = int(group_of_bin.max()) + 1
    apex = np.full(n_groups, -1, dtype=np.int64)
    best = np.full(n_groups, -np.inf)
    for index in range(len(group_of_bin)):
        group = group_of_bin[index]
        if intensity[index] > best[group]:
            best[group] = intensity[index]
            apex[group] = index
    if np.any(apex < 0):
        raise RuntimeError("a group has no bins")
    return apex


def _check_contiguous_labels(group_of_bin):
    steps = np.diff(group_of_bin)
    if group_of_bin[0] != 0 or np.any((steps != 0) & (steps != 1)):
        raise RuntimeError("groups must be contiguous and numbered from zero")


def _moving_average_edge(values, window):
    if window < 1 or window % 2 == 0:
        raise ValueError("smoothing window must be a positive odd integer")
    if window == 1 or len(values) == 1:
        return values.astype(np.float64).copy()
    half = window // 2
    padded = np.concatenate(
        (np.full(half, values[0]), values, np.full(half, values[-1]))
    ).astype(np.float64)
    kernel = np.full(window, 1.0 / window)
    return np.convolve(padded, kernel, mode="valid")


def partition_p1_basins(mean_spectrum, mz, gap_break_ppm=50.0, smoothing_bins=3,
                        min_relative_depth=0.05, max_merge_width_ppm=100.0):
    """P1: smoothed mean-spectrum basins with hard m/z-gap breaks.

    Returns ``(group_of_bin, apex)``. Steps follow protocol Section 3.1 exactly.
    """
    mz = validate_axis(mz)
    mean_spectrum = np.asarray(mean_spectrum, dtype=np.float64).reshape(-1)
    if mean_spectrum.shape != mz.shape:
        raise ValueError("mean spectrum and m/z axis lengths differ")
    if not np.all(np.isfinite(mean_spectrum)):
        raise ValueError("mean spectrum must be finite")

    breaks = np.flatnonzero(adjacent_gap_ppm(mz) > gap_break_ppm) + 1
    segment_starts = np.concatenate(([0], breaks))
    segment_stops = np.concatenate((breaks, [len(mz)]))

    group_of_bin = np.empty(len(mz), dtype=np.int64)
    next_group = 0
    for start, stop in zip(segment_starts, segment_stops):
        smoothed = _moving_average_edge(mean_spectrum[start:stop], smoothing_bins)
        n = stop - start
        # Raw basins: boundary bins start new groups (local index).
        boundaries = [
            i for i in range(1, n - 1)
            if smoothed[i] < smoothed[i - 1] and smoothed[i] <= smoothed[i + 1]
        ]
        raw_starts = [0] + boundaries
        raw_stops = boundaries + [n]

        # Single left-to-right prominence merge pass.
        current_start = raw_starts[0]
        current_stop = raw_stops[0]
        current_peak = float(smoothed[current_start:current_stop].max())
        merged = []
        for next_start, next_stop in zip(raw_starts[1:], raw_stops[1:]):
            next_peak = float(smoothed[next_start:next_stop].max())
            lower_peak = min(current_peak, next_peak)
            depth = lower_peak - float(smoothed[next_start])
            relative = depth / lower_peak if lower_peak > 0 else 0.0
            merged_width = width_ppm(mz, start + current_start, start + next_stop - 1)
            if relative < min_relative_depth and merged_width <= max_merge_width_ppm:
                current_stop = next_stop
                current_peak = max(current_peak, next_peak)
            else:
                merged.append((current_start, current_stop))
                current_start, current_stop, current_peak = (
                    next_start, next_stop, next_peak
                )
        merged.append((current_start, current_stop))
        for local_start, local_stop in merged:
            group_of_bin[start + local_start:start + local_stop] = next_group
            next_group += 1

    _check_contiguous_labels(group_of_bin)
    return group_of_bin, group_apexes(group_of_bin, mean_spectrum)


def partition_p3_ppm(mean_spectrum, mz, tolerance_ppm=20.0):
    """P3: connected chains of adjacent gaps <= tolerance_ppm."""
    mz = validate_axis(mz)
    mean_spectrum = np.asarray(mean_spectrum, dtype=np.float64).reshape(-1)
    if mean_spectrum.shape != mz.shape:
        raise ValueError("mean spectrum and m/z axis lengths differ")
    if tolerance_ppm <= 0:
        raise ValueError("tolerance must be positive")
    new_group = np.concatenate(([0], (adjacent_gap_ppm(mz) > tolerance_ppm).astype(np.int64)))
    group_of_bin = np.cumsum(new_group).astype(np.int64)
    _check_contiguous_labels(group_of_bin)
    return group_of_bin, group_apexes(group_of_bin, mean_spectrum)


def partition_hash(group_of_bin):
    array = np.ascontiguousarray(np.asarray(group_of_bin, dtype=np.int64))
    return hashlib.sha256(array.tobytes()).hexdigest()


def partition_structure(group_of_bin, mz, extremes=10):
    """Structural summary used by the sanity audit. Reads no labels or scores."""
    mz = validate_axis(mz)
    group_of_bin = np.asarray(group_of_bin, dtype=np.int64)
    _check_contiguous_labels(group_of_bin)
    n_groups = int(group_of_bin[-1]) + 1
    sizes = np.bincount(group_of_bin, minlength=n_groups)
    firsts = np.concatenate(([0], np.cumsum(sizes)[:-1]))
    lasts = firsts + sizes - 1
    widths_da = mz[lasts] - mz[firsts]
    widths_ppm = widths_da / mz[firsts] * 1e6

    def describe(values):
        return {
            "median": float(np.median(values)),
            "p99": float(np.percentile(values, 99)),
            "max": float(np.max(values)),
        }

    def rows(order):
        return [
            {
                "group": int(g),
                "first_mz": float(mz[firsts[g]]),
                "last_mz": float(mz[lasts[g]]),
                "bins": int(sizes[g]),
                "width_da": float(widths_da[g]),
                "width_ppm": float(widths_ppm[g]),
            }
            for g in order[:extremes]
        ]

    return {
        "bins": int(len(mz)),
        "groups": n_groups,
        "groups_per_bin": float(n_groups / len(mz)),
        "singleton_fraction": float(np.mean(sizes == 1)),
        "group_size_bins": describe(sizes),
        "width_da": describe(widths_da),
        "width_ppm": describe(widths_ppm),
        "max_group_fraction_of_bins": float(sizes.max() / len(mz)),
        "widest_groups": rows(np.argsort(-widths_da, kind="stable")),
        "largest_groups": rows(np.argsort(-sizes, kind="stable")),
        "sha256": partition_hash(group_of_bin),
    }


def check_partition_sanity(structure, max_width_da=0.5,
                           near_bin_level_singleton_fraction=0.95):
    """Apply the predeclared structural rules (protocol Section 3.2).

    S1 (hard): maximum group width must be below ``max_width_da``.
    S2 (descriptive): largest group's bin count and share of the axis, reported
    for review but never used to reject a partition.
    S3 (informational): near bin-level partition.
    """
    failures = []
    if not structure["width_da"]["max"] < max_width_da:
        failures.append(
            f"S1: maximum group width {structure['width_da']['max']:.4f} Da "
            f">= {max_width_da} Da"
        )
    diagnostics = {
        "S2_largest_group_bins": int(structure["group_size_bins"]["max"]),
        "S2_largest_group_fraction_of_bins": float(structure["max_group_fraction_of_bins"]),
        "S2_group_size_bins_p99": float(structure["group_size_bins"]["p99"]),
        "S2_note": "descriptive only; not a rejection rule",
    }
    notes = []
    if structure["singleton_fraction"] > near_bin_level_singleton_fraction:
        notes.append("S3: near bin-level partition (informational)")
    return {"passed": not failures, "failures": failures,
            "diagnostics": diagnostics, "notes": notes}


def contiguous_runs(bin_indices):
    """Rule A: runs of consecutive bin indices in a selection (partition-free)."""
    indices = np.unique(np.asarray(bin_indices, dtype=np.int64))
    if len(indices) == 0:
        return indices, np.zeros(0, dtype=np.int64)
    run_id = np.concatenate(([0], np.cumsum(np.diff(indices) > 1))).astype(np.int64)
    return indices, run_id


def groups_of_selection(bin_indices, group_of_bin):
    return set(np.asarray(group_of_bin)[np.asarray(bin_indices, dtype=np.int64)].tolist())


def first_k_distinct_groups(ranking, group_of_bin, k):
    """Walk a ranking until it covers k distinct groups.

    Returns ``(groups_in_order, bins_consumed)``.
    """
    if k < 1:
        raise ValueError("k must be positive")
    group_of_bin = np.asarray(group_of_bin, dtype=np.int64)
    seen = set()
    order = []
    consumed = 0
    for index in np.asarray(ranking, dtype=np.int64):
        consumed += 1
        group = int(group_of_bin[index])
        if group not in seen:
            seen.add(group)
            order.append(group)
            if len(order) == k:
                return np.asarray(order, dtype=np.int64), consumed
    raise ValueError(f"ranking covers only {len(order)} groups; {k} required")


def group_reference_sets(bin_reference_by_threshold, apex):
    """A group is reference-positive at t iff its apex bin is bin-level positive."""
    apex = np.asarray(apex, dtype=np.int64)
    return {
        threshold: set(np.flatnonzero(np.isin(apex, list(bins))).tolist())
        for threshold, bins in bin_reference_by_threshold.items()
    }


def set_metrics(selected, positive, universe):
    selected = set(selected)
    positive = set(positive)
    tp = len(selected & positive)
    fp = len(selected - positive)
    fn = len(positive - selected)
    denominator = 2 * tp + fp + fn
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": universe - tp - fp - fn,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "F1": 2 * tp / denominator if denominator else 0.0,
    }


def score_groups(selected_groups, reference_groups_by_threshold, n_groups):
    results = {}
    f1 = []
    for threshold in THRESHOLDS:
        metrics = set_metrics(
            selected_groups, reference_groups_by_threshold[threshold], n_groups
        )
        metrics["reference_groups"] = len(reference_groups_by_threshold[threshold])
        results[str(threshold)] = metrics
        f1.append(metrics["F1"])
    return {
        "selected_groups": len(set(selected_groups)),
        "threshold_results": results,
        "mSCF1": float(np.mean(f1)),
    }


def max_attainable_f1(budget, reference_size):
    """Best possible F1 when selecting ``budget`` items against ``reference_size``."""
    if budget < 0 or reference_size < 0:
        raise ValueError("sizes must be non-negative")
    if budget + reference_size == 0:
        return 0.0
    return 2.0 * min(budget, reference_size) / (budget + reference_size)
