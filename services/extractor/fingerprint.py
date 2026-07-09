"""
services/extractor/fingerprint.py

Orchestrates the extraction pipeline:
  TxRecord list  →  normalized 8-dimension FeatureVector

The FeatureVector is the sole input to the generative renderer.
All computation is pure-function: same tx list → same vector.
"""

from __future__ import annotations

import math
import time as time_mod
from dataclasses import dataclass, asdict
from typing import Sequence

from .okx_client import TxRecord, AddressAnalysis
from .entropy import (
    sample_entropy, normalize_sampen,
    correlation_dimension, normalize_corr_dim,
    burstiness, normalize_burstiness,
    hurst_exponent,
)

MINIMUM_TX_COUNT = 10


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class FeatureVector:
    """
    Normalized 8-dimension behavioral fingerprint, all values in [0.0, 1.0].

    Dimensions:
      activity_entropy      — chaos / unpredictability of tx frequency
      timing_regularity     — how periodic/rhythmic the wallet behaves
      amount_variance       — spread of transaction values
      interaction_diversity — ratio of unique counterparties to total txs
      burst_coefficient     — clustering of activity into time bursts
      recency_decay         — how recently the wallet was active
      volume_skew           — whether a few large txs dominate the total
      chaos_dimension       — fractal complexity of the tx value series
    """
    activity_entropy: float
    timing_regularity: float
    amount_variance: float
    interaction_diversity: float
    burst_coefficient: float
    recency_decay: float
    volume_skew: float
    chaos_dimension: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    def as_list(self) -> list[float]:
        return list(asdict(self).values())


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_fingerprint(
    txs: Sequence[TxRecord],
    analysis: AddressAnalysis | None = None,
    now: int | None = None,
) -> FeatureVector:
    """
    Convert a list of TxRecord objects into a normalised FeatureVector.

    Args:
        txs:      Transaction records for the wallet (any order; sorted internally).
        analysis: Optional supplemental AddressAnalysis from OKX API.
        now:      Unix timestamp for recency calculation (default: current time).

    Returns:
        FeatureVector with all dimensions in [0.0, 1.0].

    Raises:
        ValueError: If fewer than MINIMUM_TX_COUNT transactions are provided.
    """
    valid_txs = [t for t in txs if not t.is_error and t.timestamp > 0]
    if len(valid_txs) < MINIMUM_TX_COUNT:
        raise ValueError(
            f"Insufficient transaction history: {len(valid_txs)} valid txs "
            f"(minimum required: {MINIMUM_TX_COUNT})"
        )

    # Sort chronologically
    sorted_txs = sorted(valid_txs, key=lambda t: t.timestamp)
    timestamps = [t.timestamp for t in sorted_txs]
    values = [t.value_eth for t in sorted_txs]

    # Inter-event times (seconds between consecutive txs)
    iets = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
    nonzero_iets = [t for t in iets if t > 0] or [1.0]

    # 1. activity_entropy — SampEn on inter-event time series
    raw_se = sample_entropy(nonzero_iets, m=2, r_factor=0.2)
    activity_entropy = normalize_sampen(raw_se)

    # 2. timing_regularity — inverse of burstiness (regular = low burstiness)
    b = burstiness(nonzero_iets)
    timing_regularity = 1.0 - normalize_burstiness(b)

    # 3. amount_variance — coefficient of variation of tx values
    val_cv = _coefficient_of_variation(values)
    amount_variance = _clamp(val_cv / 5.0, 0.0, 1.0)  # CV rarely exceeds 5

    # 4. interaction_diversity — unique counterparties / total txs
    all_addrs = {t.from_addr for t in sorted_txs} | {t.to_addr for t in sorted_txs}
    wallet_addr = _guess_wallet(sorted_txs)
    counterparties = all_addrs - {wallet_addr.lower()}
    diversity_raw = len(counterparties) / len(sorted_txs)
    interaction_diversity = _clamp(diversity_raw, 0.0, 1.0)

    # Enrich with OKX Address Analysis if available
    if analysis and analysis.unique_counterparties > 0 and analysis.total_tx_count > 0:
        analysis_diversity = analysis.unique_counterparties / analysis.total_tx_count
        interaction_diversity = (interaction_diversity + _clamp(analysis_diversity, 0.0, 1.0)) / 2

    # 5. burst_coefficient — shifted burstiness to [0, 1]
    burst_coefficient = normalize_burstiness(b)

    # 6. recency_decay — exponential decay from last tx to now
    current_time = now or int(time_mod.time())
    last_tx_time = timestamps[-1]
    days_since = (current_time - last_tx_time) / 86400.0
    # Half-life of 90 days: active wallet → 1.0, 1-year dormant → ~0.08
    recency_decay = math.exp(-days_since * math.log(2) / 90.0)
    recency_decay = _clamp(recency_decay, 0.0, 1.0)

    # 7. volume_skew — Fisher-Pearson skewness of tx values, normalised
    skew = _fisher_pearson_skewness(values)
    # Skewness range in practice: [-5, 15] for crypto tx distributions
    volume_skew = _clamp((skew + 5.0) / 20.0, 0.0, 1.0)

    # 8. chaos_dimension — Correlation Dimension of tx value series
    raw_cd = correlation_dimension(values, max_m=5)
    chaos_dimension = normalize_corr_dim(raw_cd, max_m=5.0)

    return FeatureVector(
        activity_entropy=round(activity_entropy, 4),
        timing_regularity=round(timing_regularity, 4),
        amount_variance=round(amount_variance, 4),
        interaction_diversity=round(interaction_diversity, 4),
        burst_coefficient=round(burst_coefficient, 4),
        recency_decay=round(recency_decay, 4),
        volume_skew=round(volume_skew, 4),
        chaos_dimension=round(chaos_dimension, 4),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mu = _mean(xs)
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1))


def _coefficient_of_variation(xs: list[float]) -> float:
    mu = _mean(xs)
    if mu == 0.0:
        return 0.0
    return _std(xs) / mu


def _fisher_pearson_skewness(xs: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    mu = _mean(xs)
    sigma = _std(xs)
    if sigma == 0.0:
        return 0.0
    return sum(((x - mu) / sigma) ** 3 for x in xs) * n / ((n - 1) * (n - 2))


def _guess_wallet(txs: list[TxRecord]) -> str:
    """Heuristic: the address that appears most frequently as `from_addr`."""
    from_counts: dict[str, int] = {}
    for t in txs:
        addr = t.from_addr.lower()
        from_counts[addr] = from_counts.get(addr, 0) + 1
    return max(from_counts, key=from_counts.get) if from_counts else ""


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))
