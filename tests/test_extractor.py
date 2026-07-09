"""
tests/test_extractor.py

Unit tests for services/extractor/entropy.py and services/extractor/fingerprint.py.
"""

from __future__ import annotations

import pytest

from services.extractor.entropy import (
    sample_entropy,
    normalize_sampen,
    correlation_dimension,
    normalize_corr_dim,
    burstiness,
    normalize_burstiness,
    hurst_exponent,
)
from services.extractor.fingerprint import build_fingerprint, MINIMUM_TX_COUNT
from services.extractor.okx_client import TxRecord, AddressAnalysis


# ---------------------------------------------------------------------------
# entropy.py
# ---------------------------------------------------------------------------

def test_sample_entropy_constant_series_is_zero():
    assert sample_entropy([5.0] * 10) == 0.0


def test_sample_entropy_too_short_series_is_zero():
    assert sample_entropy([1.0, 2.0, 3.0]) == 0.0


def test_normalize_sampen_clamped_to_unit_range():
    assert normalize_sampen(-1.0) == 0.0
    assert normalize_sampen(100.0) == 1.0
    assert 0.0 <= normalize_sampen(1.25) <= 1.0


def test_burstiness_perfectly_regular_intervals_is_minus_one():
    # Equal inter-event times -> sigma == 0 -> B == -1 (maximally regular)
    assert burstiness([10.0] * 8) == -1.0


def test_burstiness_too_few_events_is_zero():
    assert burstiness([]) == 0.0
    assert burstiness([5.0]) == 0.0


def test_normalize_burstiness_shifts_range():
    assert normalize_burstiness(-1.0) == 0.0
    assert normalize_burstiness(1.0) == 1.0
    assert normalize_burstiness(0.0) == 0.5


def test_correlation_dimension_short_series_is_zero():
    assert correlation_dimension(list(range(5))) == 0.0


def test_normalize_corr_dim_clamped():
    assert normalize_corr_dim(-1.0) == 0.0
    assert normalize_corr_dim(10.0, max_m=5.0) == 1.0


def test_hurst_exponent_short_series_defaults_to_random_walk():
    assert hurst_exponent(list(range(5))) == 0.5


def test_hurst_exponent_in_valid_range_for_longer_series():
    series = [float((i * 37) % 23) for i in range(60)]
    h = hurst_exponent(series)
    assert 0.0 <= h <= 1.0


# ---------------------------------------------------------------------------
# fingerprint.py
# ---------------------------------------------------------------------------

def _make_tx(i: int, *, value: float, ts: int, is_error: bool = False) -> TxRecord:
    return TxRecord(
        hash=f"0xhash{i}",
        from_addr="0xwallet0000000000000000000000000000000001",
        to_addr=f"0xcounterparty{i % 5:029d}",
        value_eth=value,
        timestamp=ts,
        block_number=1000 + i,
        gas_used=21000,
        is_error=is_error,
        method_id="0x",
    )


def _synthetic_txs(n: int = 20) -> list[TxRecord]:
    base_ts = 1_700_000_000
    txs = []
    for i in range(n):
        # Irregular spacing and varied values so the math has something to chew on.
        ts = base_ts + i * 3600 + (i % 3) * 500
        value = 0.1 * ((i % 7) + 1) ** 1.5
        txs.append(_make_tx(i, value=value, ts=ts))
    return txs


def test_build_fingerprint_raises_below_minimum_tx_count():
    txs = _synthetic_txs(MINIMUM_TX_COUNT - 1)
    with pytest.raises(ValueError):
        build_fingerprint(txs)


def test_build_fingerprint_ignores_errored_txs_towards_minimum():
    # 9 valid + several errored -> still below minimum, should raise.
    valid = _synthetic_txs(MINIMUM_TX_COUNT - 1)
    errored = [_make_tx(100 + i, value=1.0, ts=1_700_500_000 + i, is_error=True) for i in range(5)]
    with pytest.raises(ValueError):
        build_fingerprint(valid + errored)


def test_build_fingerprint_all_dimensions_in_unit_range():
    fv = build_fingerprint(_synthetic_txs(30))
    for name, value in fv.to_dict().items():
        assert 0.0 <= value <= 1.0, f"{name} out of range: {value}"


def test_build_fingerprint_is_deterministic():
    txs_a = _synthetic_txs(25)
    txs_b = list(reversed(_synthetic_txs(25)))  # same data, different input order

    fv_a = build_fingerprint(txs_a, now=1_800_000_000)
    fv_b = build_fingerprint(txs_b, now=1_800_000_000)

    assert fv_a.to_dict() == fv_b.to_dict()


def test_build_fingerprint_uses_address_analysis_when_available():
    txs = _synthetic_txs(20)
    analysis = AddressAnalysis(total_tx_count=20, unique_counterparties=18)
    fv = build_fingerprint(txs, analysis=analysis, now=1_800_000_000)
    assert 0.0 <= fv.interaction_diversity <= 1.0
