"""Design-based estimates for review samples (CPD-0044): weighted proportions and ratios with stratified, clustered
Taylor-linearisation variances. Pure Python; no dependency.

A sample unit ``i`` carries a weight ``w_i = 1 / pi_i`` (its inclusion probability), a stratum ``h`` and a cluster ``c`` (the
primary sampling unit; the unit itself when there is no cluster stage). For a ratio ``R = sum(w y) / sum(w x)`` the linearised
value is ``z_i = w_i (y_i - R x_i) / sum(w x)``; with ``z_hc`` summed over a cluster,

    var(R) = sum_h (1 - f_h) * n_h / (n_h - 1) * sum_c (z_hc - mean_h(z))**2

(``n_h`` clusters in stratum ``h``; ``f_h`` the first-stage sampling fraction, 0 when unknown -- conservative). A stratum with a
single cluster contributes no variance and is **reported** (``singleton_strata``): its variance is not estimable from the sample.

Intervals:

* a proportion: Wilson's interval on the **effective sample size** ``n_eff = p (1 - p) / var`` (Korn & Graubard's approach),
  ``n_eff`` capped at ``n``; for ``p`` = 0 or 1 the variance is 0 and ``n_eff = n`` (the design effect unknown -- flagged);
* a ratio (e.g. words): ``R +/- t(df) * se``, clipped to [0, 1] when ``bounded``; ``df = clusters - strata``. With few clusters the
  t quantile widens the interval; with ``df < 1`` no interval is given.

These are approximations stated as such; they describe the sampled population only (a targeted, non-probability component has
no design weights and is never passed here).
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

Z95 = 1.959964
# Student t, 97.5 % quantile, df 1..30 (beyond: the normal quantile is within 2 %)
_T975 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110,
         2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]


def t975(df: int) -> float | None:
    if df < 1:
        return None
    return _T975[df - 1] if df <= 30 else Z95


def _wilson(p: float, n: float, z: float = Z95) -> list[float] | None:
    if n <= 0:
        return None
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(max(0.0, p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def ratio(y: Sequence[float], x: Sequence[float], *, weights: Sequence[float], strata: Sequence[Any] | None = None,
          clusters: Sequence[Any] | None = None, fpc: Mapping[Any, float] | None = None, bounded: bool = True) -> dict[str, Any]:
    """The weighted ratio ``sum(w y) / sum(w x)`` with its linearised standard error and interval."""
    n = len(y)
    if not (len(x) == len(weights) == n) or n == 0:
        raise ValueError("y, x and weights must be non-empty and of one length")
    strata = list(strata) if strata is not None else ["all"] * n
    clusters = list(clusters) if clusters is not None else list(range(n))
    wx = sum(w * xi for w, xi in zip(weights, x))
    if wx == 0:
        return {"estimate": None, "se": None, "interval": None, "n": n, "note": "denominator is zero"}
    r = sum(w * yi for w, yi in zip(weights, y)) / wx
    z = defaultdict(float)
    for w, yi, xi, h, c in zip(weights, y, x, strata, clusters):
        z[(h, c)] += w * (yi - r * xi) / wx
    by_stratum: dict[Any, list[float]] = defaultdict(list)
    for (h, _), v in z.items():
        by_stratum[h].append(v)
    var, singletons = 0.0, []
    for h, values in by_stratum.items():
        k = len(values)
        if k < 2:
            singletons.append(h)
            continue
        mean = sum(values) / k
        var += (1 - (fpc or {}).get(h, 0.0)) * k / (k - 1) * sum((v - mean) ** 2 for v in values)
    se = math.sqrt(var)
    df = len(z) - len(by_stratum)
    t = t975(df)
    interval = None
    if t is not None:
        low, high = r - t * se, r + t * se
        if bounded:
            low, high = max(0.0, low), min(1.0, high)
        interval = [round(low, 4), round(high, 4)]
    return {"estimate": round(r, 6), "se": round(se, 6), "interval": interval, "n": n, "clusters": len(z),
            "strata": len(by_stratum), "df": df, "singleton_strata": sorted(map(str, singletons))}


def ratio_difference(y1: Sequence[float], x1: Sequence[float], y2: Sequence[float], x2: Sequence[float], *,
                     weights: Sequence[float], strata: Sequence[Any] | None = None, clusters: Sequence[Any] | None = None,
                     fpc: Mapping[Any, float] | None = None) -> dict[str, Any]:
    """``R1 - R2`` for two ratios measured on the **same** units (a candidate and a baseline on one sample): the paired
    linearised values ``z1 - z2`` give its variance, so the shared sampling noise cancels."""
    n = len(y1)
    strata = list(strata) if strata is not None else ["all"] * n
    clusters = list(clusters) if clusters is not None else list(range(n))
    d1 = sum(w * x for w, x in zip(weights, x1))
    d2 = sum(w * x for w, x in zip(weights, x2))
    if not d1 or not d2:
        return {"estimate": None, "note": "a denominator is zero"}
    r1 = sum(w * y for w, y in zip(weights, y1)) / d1
    r2 = sum(w * y for w, y in zip(weights, y2)) / d2
    z = defaultdict(float)
    for i in range(n):
        z[(strata[i], clusters[i])] += weights[i] * ((y1[i] - r1 * x1[i]) / d1 - (y2[i] - r2 * x2[i]) / d2)
    by_stratum: dict[Any, list[float]] = defaultdict(list)
    for (h, _), v in z.items():
        by_stratum[h].append(v)
    var = 0.0
    for h, values in by_stratum.items():
        k = len(values)
        if k >= 2:
            mean = sum(values) / k
            var += (1 - (fpc or {}).get(h, 0.0)) * k / (k - 1) * sum((v - mean) ** 2 for v in values)
    se = math.sqrt(var)
    df = len(z) - len(by_stratum)
    t = t975(df)
    d = r1 - r2
    return {"estimate": round(d, 6), "first": round(r1, 6), "second": round(r2, 6), "se": round(se, 6),
            "interval": [round(d - t * se, 4), round(d + t * se, 4)] if t is not None else None, "df": df, "n": n}


def proportion(y: Sequence[float], *, weights: Sequence[float], strata: Sequence[Any] | None = None,
               clusters: Sequence[Any] | None = None, fpc: Mapping[Any, float] | None = None) -> dict[str, Any]:
    """A weighted proportion of 0/1 outcomes with a Korn-Graubard-style Wilson interval on the effective sample size."""
    out = ratio(y, [1.0] * len(y), weights=weights, strata=strata, clusters=clusters, fpc=fpc)
    p, se, n = out["estimate"], out["se"], out["n"]
    if p is None:
        return out
    k = sum(1 for v in y if v)
    if 0 < p < 1 and se and se > 0:
        n_eff = min(n, p * (1 - p) / se ** 2)
        flag = None
    else:
        n_eff, flag = n, "p is 0 or 1: the variance is 0 and the design effect cannot be estimated; n_eff = n"
    out.update({"k": k, "n_eff": round(n_eff, 1), "interval": _wilson(p, n_eff), "interval_method": "Wilson on n_eff"})
    if flag:
        out["note"] = flag
    return out


def design_from_cases(cases: Iterable[Mapping[str, Any]]) -> tuple[list[float], list[Any], list[Any]]:
    """Weights, strata and clusters of cases that carry ``inclusion_probability``, ``stratum`` and ``cluster``."""
    w, s, c = [], [], []
    for case in cases:
        pi = case.get("inclusion_probability")
        if not pi or pi <= 0:
            raise ValueError(f"{case.get('case_id')}: no inclusion probability -- not a probability sample unit")
        w.append(1.0 / pi)
        s.append(case.get("stratum", "all"))
        c.append(case.get("cluster", case.get("case_id")))
    return w, s, c


__all__ = ["ratio", "ratio_difference", "proportion", "design_from_cases", "t975", "Z95"]
