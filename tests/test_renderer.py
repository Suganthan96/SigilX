"""
tests/test_renderer.py

Determinism and structural sanity tests for services/renderer/composer.py
and the sub-modules it drives (palette, shapes, animator).
"""

from __future__ import annotations

from services.extractor.fingerprint import FeatureVector
from services.renderer.composer import render_portrait

WALLET_A = "0x0000000000000000000000000000000000dead"
WALLET_B = "0x0000000000000000000000000000000000beef"

FV = FeatureVector(
    activity_entropy=0.73,
    timing_regularity=0.21,
    amount_variance=0.88,
    interaction_diversity=0.55,
    burst_coefficient=0.67,
    recency_decay=0.90,
    volume_skew=0.43,
    chaos_dimension=0.61,
)

FV_OTHER = FeatureVector(
    activity_entropy=0.05,
    timing_regularity=0.95,
    amount_variance=0.10,
    interaction_diversity=0.08,
    burst_coefficient=0.02,
    recency_decay=0.15,
    volume_skew=0.05,
    chaos_dimension=0.05,
)


def test_render_is_well_formed_svg():
    svg = render_portrait(WALLET_A, "eth-mainnet", FV)
    assert svg.startswith("<svg")
    assert svg.strip().endswith("</svg>")
    assert 'viewBox="0 0 600 600"' in svg


def test_render_is_deterministic_for_same_inputs():
    svg1 = render_portrait(WALLET_A, "eth-mainnet", FV)
    svg2 = render_portrait(WALLET_A, "eth-mainnet", FV)
    assert svg1 == svg2


def test_render_is_deterministic_regardless_of_address_case():
    svg_lower = render_portrait(WALLET_A.lower(), "eth-mainnet", FV)
    svg_upper = render_portrait(WALLET_A.upper(), "eth-mainnet", FV)
    assert svg_lower == svg_upper


def test_different_wallets_produce_different_art():
    svg_a = render_portrait(WALLET_A, "eth-mainnet", FV)
    svg_b = render_portrait(WALLET_B, "eth-mainnet", FV)
    assert svg_a != svg_b


def test_different_chains_produce_different_art():
    svg_eth = render_portrait(WALLET_A, "eth-mainnet", FV)
    svg_poly = render_portrait(WALLET_A, "polygon-mainnet", FV)
    assert svg_eth != svg_poly


def test_different_feature_vectors_produce_different_art():
    svg_1 = render_portrait(WALLET_A, "eth-mainnet", FV)
    svg_2 = render_portrait(WALLET_A, "eth-mainnet", FV_OTHER)
    assert svg_1 != svg_2
