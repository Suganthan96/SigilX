"""
services/extractor/entropy.py

Pure chaos / entropy math functions.
All functions are stateless — same input always produces same output.

Algorithms used:
  - Sample Entropy (SampEn)      — predictability of a time series
  - Correlation Dimension         — Grassberger-Procaccia fractal complexity estimate
  - Burstiness Parameter          — Goh & Barabási (2008)
  - Hurst Exponent (R/S analysis) — long-range dependency / persistence
"""

from __future__ import annotations

import math
from typing import Sequence


# ---------------------------------------------------------------------------
# Sample Entropy
# ---------------------------------------------------------------------------

def sample_entropy(
    time_series: Sequence[float],
    m: int = 2,
    r_factor: float = 0.2,
) -> float:
    """
    Compute Sample Entropy (SampEn) of a time series.

    SampEn measures the likelihood that patterns of length `m` that are
    similar will remain similar at length `m+1`. High SampEn = more
    complex / unpredictable; low SampEn = regular / predictable.

    Args:
        time_series: Input sequence of floats.
        m:           Template length (typically 2).
        r_factor:    Tolerance as fraction of std dev (typically 0.1–0.25).

    Returns:
        Raw SampEn value, or 0.0 if the series is too short / degenerate.
        Normalised to [0, 1] via `normalize_sampen()`.
    """
    ts = list(time_series)
    n = len(ts)
    if n < 4:
        return 0.0

    std = _std(ts)
    if std == 0.0:
        return 0.0
    r = r_factor * std

    def _count_templates(template_len: int) -> int:
        count = 0
        for i in range(n - template_len):
            for j in range(i + 1, n - template_len):
                if _chebyshev_distance(ts, i, j, template_len) < r:
                    count += 1
        return count

    A = _count_templates(m + 1)
    B = _count_templates(m)

    if B == 0:
        return 0.0

    ratio = A / B
    if ratio == 0.0:
        return 2.5   # practical ceiling — extremely complex

    raw = -math.log(ratio)
    return _clamp(raw, 0.0, 2.5)


def normalize_sampen(raw: float, ceiling: float = 2.5) -> float:
    """Normalize raw SampEn to [0, 1]."""
    return _clamp(raw / ceiling, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Correlation Dimension
# ---------------------------------------------------------------------------

def correlation_dimension(
    time_series: Sequence[float],
    max_m: int = 5,
    r_steps: int = 20,
) -> float:
    """
    Estimate the Correlation Dimension via Grassberger-Procaccia algorithm.

    Embeds the series in phase space up to dimension `max_m`, computes the
    correlation integral C(r) across a log-spaced range of r, and fits a
    slope to log(C(r)) vs log(r). Returns the estimated dimension.

    Args:
        time_series: Input sequence.
        max_m:       Max embedding dimension to test (typically 4–6).
        r_steps:     Number of radius steps for slope estimation.

    Returns:
        Estimated dimension in [0, max_m]. Normalised to [0, 1] by caller.
    """
    ts = list(time_series)
    n = len(ts)
    if n < 20:
        return 0.0

    std = _std(ts)
    if std == 0.0:
        return 0.0

    # Use embedding dimension 2 for speed; sufficient for a proxy estimate
    m = min(2, max_m)
    embedded = [ts[i : i + m] for i in range(n - m + 1)]
    N = len(embedded)
    if N < 4:
        return 0.0

    r_min = std * 0.05
    r_max = std * 2.0
    radii = [r_min * math.exp(math.log(r_max / r_min) * k / r_steps) for k in range(r_steps + 1)]

    log_r_vals = []
    log_c_vals = []

    for r in radii:
        count = sum(
            1
            for i in range(N)
            for j in range(i + 1, N)
            if _euclidean_distance(embedded[i], embedded[j]) < r
        )
        c = 2.0 * count / (N * (N - 1)) if N > 1 else 0.0
        if c > 0.0:
            log_r_vals.append(math.log(r))
            log_c_vals.append(math.log(c))

    if len(log_r_vals) < 4:
        return 0.0

    # Linear regression slope = estimated dimension
    slope = _linear_slope(log_r_vals, log_c_vals)
    return _clamp(slope, 0.0, float(max_m))


def normalize_corr_dim(raw: float, max_m: float = 5.0) -> float:
    """Normalize raw correlation dimension to [0, 1]."""
    return _clamp(raw / max_m, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Burstiness Parameter (Goh & Barabási 2008)
# ---------------------------------------------------------------------------

def burstiness(inter_event_times: Sequence[float]) -> float:
    """
    Compute the burstiness parameter B = (σ - μ) / (σ + μ).

    B in [-1, 1]:
       B ≈ +1  → maximally bursty (heavy tail, clustered events)
       B ≈  0  → Poisson (random)
       B ≈ -1  → periodic / regular

    Args:
        inter_event_times: Sequence of gaps between events (seconds, etc.).

    Returns:
        B in [-1, 1].
    """
    iet = [t for t in inter_event_times if t > 0]
    if len(iet) < 2:
        return 0.0

    mu = _mean(iet)
    if mu == 0.0:
        return 0.0
    sigma = _std(iet)

    denom = sigma + mu
    if denom == 0.0:
        return 0.0

    return (sigma - mu) / denom


def normalize_burstiness(b: float) -> float:
    """Shift B from [-1, 1] to [0, 1]."""
    return _clamp((b + 1.0) / 2.0, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Hurst Exponent (R/S Analysis)
# ---------------------------------------------------------------------------

def hurst_exponent(time_series: Sequence[float]) -> float:
    """
    Estimate the Hurst exponent via Rescaled Range (R/S) analysis.

    H < 0.5 → anti-persistent (mean-reverting)
    H = 0.5 → random walk (Brownian motion)
    H > 0.5 → persistent (trending)

    Args:
        time_series: Input sequence.

    Returns:
        H in [0, 1] (already in valid range).
    """
    ts = list(time_series)
    n = len(ts)
    if n < 20:
        return 0.5  # default to random walk

    # Compute R/S for multiple sub-series lengths
    log_n_vals = []
    log_rs_vals = []

    for sub_n in _subdivision_sizes(n, min_size=10):
        rs = _rs_for_length(ts, sub_n)
        if rs > 0:
            log_n_vals.append(math.log(sub_n))
            log_rs_vals.append(math.log(rs))

    if len(log_n_vals) < 2:
        return 0.5

    h = _linear_slope(log_n_vals, log_rs_vals)
    return _clamp(h, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mu = _mean(xs)
    variance = sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(variance)


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _chebyshev_distance(ts: list[float], i: int, j: int, m: int) -> float:
    return max(abs(ts[i + k] - ts[j + k]) for k in range(m))


def _euclidean_distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _linear_slope(xs: list[float], ys: list[float]) -> float:
    """Ordinary least-squares slope of ys ~ xs."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx = _mean(xs)
    my = _mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0.0:
        return 0.0
    return num / den


def _rs_for_length(ts: list[float], sub_n: int) -> float:
    """Mean R/S statistic for sub-series of length sub_n."""
    n = len(ts)
    rs_vals = []
    for start in range(0, n - sub_n + 1, sub_n):
        sub = ts[start : start + sub_n]
        mu = _mean(sub)
        deviations = [x - mu for x in sub]
        cumdev = [sum(deviations[: i + 1]) for i in range(len(deviations))]
        R = max(cumdev) - min(cumdev)
        S = _std(sub)
        if S > 0:
            rs_vals.append(R / S)
    return _mean(rs_vals) if rs_vals else 0.0


def _subdivision_sizes(n: int, min_size: int = 10) -> list[int]:
    """Return a range of sub-series lengths spanning [min_size, n//2]."""
    sizes = []
    s = min_size
    while s <= n // 2:
        sizes.append(s)
        s = int(s * 1.5) + 1
    return sizes
