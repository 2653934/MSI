"""Paired-comparison statistics for protocol 18 Section 6.6 ("Stats").

Exact Wilcoxon signed-rank p (scipy), the Hodges-Lehmann estimate with its exact
distribution-free CI from the Walsh averages, the matched-pairs rank-biserial r,
sign counts and the Holm adjustment. Pure functions on 1-D arrays of paired
differences; no file access.
"""

import numpy as np
from scipy import stats


def signed_rank_null_counts(n):
    """Number of sign assignments giving each T+ = 0..n(n+1)/2 for untied ranks 1..n."""
    counts = np.zeros(n * (n + 1) // 2 + 1, dtype=object)
    counts[0] = 1
    for rank in range(1, n + 1):
        shifted = np.zeros_like(counts)
        shifted[rank:] = counts[:-rank]
        counts = counts + shifted
    return counts


def sign_counts(differences):
    d = np.asarray(differences, dtype=float)
    return {"n_positive": int(np.sum(d > 0)), "n_negative": int(np.sum(d < 0)),
            "n_zero": int(np.sum(d == 0))}


def wilcoxon_exact(differences):
    """Two-sided exact Wilcoxon signed-rank test, zero_method="wilcox".

    scipy drops zero differences and applies the exact null distribution to the
    remaining n. With tied |differences| it still uses that distribution (which
    assumes untied ranks), so the tie count is returned beside the p-value.
    """
    d = np.asarray(differences, dtype=float)
    nonzero = d[d != 0]
    tied = int(len(nonzero) - len(np.unique(np.abs(nonzero))))
    if len(nonzero) == 0:
        return {"statistic": None, "p_exact": None, "n_nonzero": 0,
                "n_tied_abs": 0, "min_attainable_p": None,
                "note": "all differences are zero; no test"}
    result = stats.wilcoxon(d, zero_method="wilcox", method="exact")
    return {"statistic": float(result.statistic), "p_exact": float(result.pvalue),
            "n_nonzero": int(len(nonzero)), "n_tied_abs": tied,
            "min_attainable_p": min(1.0, 2.0 / 2 ** len(nonzero)), "note": ""}


def walsh_averages(differences):
    d = np.asarray(differences, dtype=float)
    i, j = np.triu_indices(len(d))
    return np.sort((d[i] + d[j]) / 2.0)


def hodges_lehmann(differences, alpha=0.05):
    """HL estimate (median Walsh average) and the exact distribution-free CI.

    With T+ the signed-rank statistic on all n differences, c is the largest t with
    P(T+ <= t) <= alpha/2 and the CI is [W_(c+1), W_(N-c)] over the N = n(n+1)/2
    sorted Walsh averages, with coverage 1 - 2 P(T+ <= c). If no such c exists
    (n <= 5 at alpha 0.05), the 95% CI is not attainable: [min, max] Walsh average
    is returned with its achieved coverage and `ci_attainable` False.
    """
    d = np.asarray(differences, dtype=float)
    n = len(d)
    walsh = walsh_averages(d)
    total = 2 ** n
    cumulative = np.cumsum(signed_rank_null_counts(n))
    below = [t for t in range(len(cumulative)) if cumulative[t] / total <= alpha / 2]
    if below:
        c = below[-1]
        low, high = walsh[c], walsh[len(walsh) - 1 - c]
        coverage = 1.0 - 2.0 * float(cumulative[c]) / total
        attainable = True
    else:
        low, high = walsh[0], walsh[-1]
        coverage = 1.0 - 2.0 / total
        attainable = False
    return {"hl_estimate": float(np.median(walsh)), "hl_ci_low": float(low),
            "hl_ci_high": float(high), "hl_ci_coverage": coverage,
            "ci_95_attainable": attainable}


def rank_biserial(differences):
    """Matched-pairs rank-biserial r = (T+ - T-) / (T+ + T-), zeros dropped, mid-ranks."""
    d = np.asarray(differences, dtype=float)
    d = d[d != 0]
    if len(d) == 0:
        return None
    ranks = stats.rankdata(np.abs(d))
    plus, minus = ranks[d > 0].sum(), ranks[d < 0].sum()
    return float((plus - minus) / (plus + minus))


def holm(p_values):
    """Holm step-down adjusted p-values, in input order; None entries are skipped."""
    indexed = [(p, i) for i, p in enumerate(p_values) if p is not None]
    m = len(indexed)
    adjusted = [None] * len(p_values)
    running = 0.0
    for step, (p, i) in enumerate(sorted(indexed)):
        running = max(running, min(1.0, (m - step) * p))
        adjusted[i] = running
    return adjusted


def paired_summary(differences):
    d = np.asarray(differences, dtype=float)
    return {"n": int(len(d)), "mean_difference": float(np.mean(d)),
            **sign_counts(d), **wilcoxon_exact(d), **hodges_lehmann(d),
            "rank_biserial": rank_biserial(d)}
