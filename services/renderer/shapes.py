"""
services/renderer/shapes.py

Deterministic shape / geometry engine.
Generates SVG path data for all visual elements in a Chain Portrait.

Shape vocabulary:
  - Orbs      — filled circles with radial gradients (base layer)
  - Sigils    — closed polygon / curve paths (mid layer)
  - Filaments — thin curved lines / arcs (detail layer)
  - Sparks    — small accent dots / highlights (top layer)

All geometry seeded from the wallet fingerprint via the caller's rng.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import NamedTuple

from ..extractor.fingerprint import FeatureVector


# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------

class Point(NamedTuple):
    x: float
    y: float


@dataclass
class Orb:
    cx: float
    cy: float
    r: float
    color_index: int   # index into Palette.mids
    opacity: float
    blur: float        # feGaussianBlur stdDeviation


@dataclass
class Sigil:
    path_d: str        # SVG path data string
    fill: str          # CSS color string
    stroke: str
    stroke_width: float
    opacity: float


@dataclass
class Filament:
    path_d: str
    stroke: str
    stroke_width: float
    opacity: float
    dash: str          # stroke-dasharray value


@dataclass
class Spark:
    cx: float
    cy: float
    r: float
    color: str
    opacity: float


@dataclass
class ShapeSet:
    orbs: list[Orb]
    sigils: list[Sigil]
    filaments: list[Filament]
    sparks: list[Spark]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

SIZE = 600   # SVG canvas size in px


def build_shapes(fv: FeatureVector, rng: random.Random, palette) -> ShapeSet:
    """
    Generate all visual elements for the portrait.

    Args:
        fv:      Feature vector.
        rng:     Seeded deterministic random instance.
        palette: Palette from palette.py.

    Returns:
        ShapeSet containing all layers.
    """
    orbs = _generate_orbs(fv, rng, palette)
    sigils = _generate_sigils(fv, rng, palette)
    filaments = _generate_filaments(fv, rng, palette)
    sparks = _generate_sparks(fv, rng, palette)
    return ShapeSet(orbs=orbs, sigils=sigils, filaments=filaments, sparks=sparks)


# ---------------------------------------------------------------------------
# Layer generators
# ---------------------------------------------------------------------------

def _generate_orbs(fv: FeatureVector, rng: random.Random, palette) -> list[Orb]:
    """
    Orbs: large glowing circles. Density driven by interaction_diversity.
    Clustering driven by burst_coefficient.
    """
    count = int(_lerp(3, 12, fv.interaction_diversity))

    # Cluster centers (burst_coefficient → how many tight clusters)
    num_clusters = max(1, int(_lerp(1, 4, fv.burst_coefficient)))
    cluster_centers = [
        Point(rng.uniform(SIZE * 0.15, SIZE * 0.85), rng.uniform(SIZE * 0.15, SIZE * 0.85))
        for _ in range(num_clusters)
    ]

    orbs = []
    for i in range(count):
        center = cluster_centers[i % num_clusters]
        spread = _lerp(SIZE * 0.3, SIZE * 0.05, fv.burst_coefficient)
        cx = _clamp(center.x + rng.gauss(0, spread), SIZE * 0.05, SIZE * 0.95)
        cy = _clamp(center.y + rng.gauss(0, spread), SIZE * 0.05, SIZE * 0.95)

        # Radius: volume_skew creates large/small contrast
        base_r = _lerp(20, 80, rng.random())
        scale = _lerp(0.5, 2.5, fv.volume_skew) if rng.random() < 0.3 else 1.0
        r = _clamp(base_r * scale, 10, SIZE * 0.35)

        orbs.append(Orb(
            cx=cx,
            cy=cy,
            r=r,
            color_index=i % len(palette.mids),
            opacity=_lerp(0.3, 0.85, fv.recency_decay),
            blur=_lerp(4, 18, 1.0 - fv.timing_regularity),
        ))

    return orbs


def _generate_sigils(fv: FeatureVector, rng: random.Random, palette) -> list[Sigil]:
    """
    Sigils: closed polygon/curve shapes. Complexity driven by amount_variance.
    Symmetry driven by timing_regularity.
    """
    count = int(_lerp(2, 8, fv.amount_variance))
    sigils = []

    for _ in range(count):
        cx = rng.uniform(SIZE * 0.1, SIZE * 0.9)
        cy = rng.uniform(0.1, SIZE * 0.9)
        size = _lerp(30, 140, rng.random() * fv.amount_variance)

        # Edge count: timing_regularity → few regular → many irregular
        n_verts = int(_lerp(3, 12, fv.amount_variance + rng.uniform(-0.2, 0.2)))
        n_verts = max(3, n_verts)

        # Chaos dimension → add bezier curvature
        use_curves = fv.chaos_dimension > 0.4

        # Symmetry via timing_regularity: high = uniform radius, low = varied
        radii = [
            size * _lerp(0.7, 1.0, fv.timing_regularity) + rng.gauss(0, size * 0.2 * (1 - fv.timing_regularity))
            for _ in range(n_verts)
        ]

        path_d = _polygon_path(cx, cy, radii, n_verts, use_curves, rng, fv.chaos_dimension)

        fill_color = palette.primary.to_css() if rng.random() > 0.5 else palette.secondary.to_css()
        stroke_color = palette.glow.to_css()

        sigils.append(Sigil(
            path_d=path_d,
            fill=fill_color,
            stroke=stroke_color,
            stroke_width=_lerp(0.5, 2.5, fv.timing_regularity),
            opacity=_lerp(0.2, 0.6, fv.recency_decay),
        ))

    return sigils


def _generate_filaments(fv: FeatureVector, rng: random.Random, palette) -> list[Filament]:
    """
    Filaments: thin curved lines connecting points of interest.
    Density driven by activity_entropy. chaos_dimension → waviness.
    """
    count = int(_lerp(5, 35, fv.activity_entropy))
    filaments = []

    for _ in range(count):
        p1 = Point(rng.uniform(0, SIZE), rng.uniform(0, SIZE))
        p2 = Point(rng.uniform(0, SIZE), rng.uniform(0, SIZE))

        # Control points for cubic bezier; chaos_dimension → wild curves
        wave_amp = _lerp(20, SIZE * 0.4, fv.chaos_dimension)
        cp1 = Point(
            p1.x + rng.gauss(0, wave_amp),
            p1.y + rng.gauss(0, wave_amp),
        )
        cp2 = Point(
            p2.x + rng.gauss(0, wave_amp),
            p2.y + rng.gauss(0, wave_amp),
        )

        path_d = f"M {p1.x:.1f} {p1.y:.1f} C {cp1.x:.1f} {cp1.y:.1f} {cp2.x:.1f} {cp2.y:.1f} {p2.x:.1f} {p2.y:.1f}"

        # Dash pattern: regular wallets get solid, bursty wallets get dashes
        if fv.burst_coefficient > 0.5:
            gap = rng.uniform(4, 15)
            dash = f"{rng.uniform(2, gap):.1f} {gap:.1f}"
        else:
            dash = "none"

        color = palette.secondary.to_css() if rng.random() > 0.4 else palette.tertiary.to_css()

        filaments.append(Filament(
            path_d=path_d,
            stroke=color,
            stroke_width=_lerp(0.3, 1.5, rng.random()),
            opacity=_lerp(0.1, 0.45, fv.recency_decay * rng.random()),
            dash=dash,
        ))

    return filaments


def _generate_sparks(fv: FeatureVector, rng: random.Random, palette) -> list[Spark]:
    """
    Sparks: small glowing accent dots. Density driven by interaction_diversity.
    """
    count = int(_lerp(10, 80, fv.interaction_diversity))
    sparks = []

    for _ in range(count):
        sparks.append(Spark(
            cx=rng.uniform(5, SIZE - 5),
            cy=rng.uniform(5, SIZE - 5),
            r=_lerp(0.5, 3.0, rng.random()),
            color=palette.glow.to_css() if rng.random() > 0.5 else palette.tertiary.to_css(),
            opacity=_lerp(0.2, 0.9, rng.random() * fv.recency_decay),
        ))

    return sparks


# ---------------------------------------------------------------------------
# Path builders
# ---------------------------------------------------------------------------

def _polygon_path(
    cx: float,
    cy: float,
    radii: list[float],
    n: int,
    use_curves: bool,
    rng: random.Random,
    curve_intensity: float,
) -> str:
    """Generate a closed SVG path for a polygon or smooth closed curve."""
    angles = [2 * math.pi * i / n - math.pi / 2 for i in range(n)]
    pts = [
        Point(cx + radii[i] * math.cos(angles[i]), cy + radii[i] * math.sin(angles[i]))
        for i in range(n)
    ]

    if not use_curves:
        coords = " ".join(f"{p.x:.1f},{p.y:.1f}" for p in pts)
        return f"M {pts[0].x:.1f} {pts[0].y:.1f} L {coords} Z"

    # Smooth closed cubic bezier spline
    cp_dist = _lerp(0.2, 0.5, curve_intensity)
    parts = [f"M {pts[0].x:.1f} {pts[0].y:.1f}"]
    for i in range(n):
        curr = pts[i]
        nxt = pts[(i + 1) % n]
        mx, my = (curr.x + nxt.x) / 2, (curr.y + nxt.y) / 2
        cp1 = Point(curr.x + (mx - curr.x) * cp_dist * rng.uniform(0.8, 1.2),
                    curr.y + (my - curr.y) * cp_dist * rng.uniform(0.8, 1.2))
        cp2 = Point(nxt.x - (nxt.x - mx) * cp_dist * rng.uniform(0.8, 1.2),
                    nxt.y - (nxt.y - my) * cp_dist * rng.uniform(0.8, 1.2))
        parts.append(f"C {cp1.x:.1f} {cp1.y:.1f} {cp2.x:.1f} {cp2.y:.1f} {nxt.x:.1f} {nxt.y:.1f}")
    parts.append("Z")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lerp(a: float, b: float, t: float) -> float:
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
