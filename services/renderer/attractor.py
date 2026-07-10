"""
services/renderer/attractor.py

Renders a Chain Portrait as a raster PNG built from a Clifford strange
attractor — the classic "chaos math" generative art technique: iterate a
simple nonlinear 2D map hundreds of thousands of times and accumulate a
density histogram of where the trajectory visits. The shape, its "handedness"
and how tightly it loops are entirely determined by four parameters (a, b, c,
d); here those come from the wallet's feature vector, and the trajectory
itself is seeded the same deterministic way as the rest of the renderer
(SHA-256 of wallet+chain), so a given wallet always produces the same image.

    x[n+1] = sin(a * y[n]) + c * cos(a * x[n])
    y[n+1] = sin(b * x[n]) + d * cos(b * y[n])

Not every (a, b, c, d) combination produces an interesting bounded attractor —
some diverge, some collapse to a fixed point. _stabilize() deterministically
nudges the parameters (using the same seeded RNG) until the trajectory is
well-behaved, so every wallet still gets a rich image rather than a blank one.
"""

from __future__ import annotations

import io
import math
import random

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from ..extractor.fingerprint import FeatureVector
from .palette import build_palette

MIN_ITERATIONS = 150_000
MAX_ITERATIONS = 450_000
BURN_IN = 1_000
SAMPLE_CHECK = 6_000
MAX_STABILIZE_ATTEMPTS = 25


def render_attractor_png(
    wallet_address: str,
    chain: str,
    fv: FeatureVector,
    size: int = 900,
) -> bytes:
    """
    Render a Chain Portrait as a PNG, deterministic per (wallet_address, chain).

    Returns:
        Raw PNG bytes.
    """
    rng = _make_rng(wallet_address, chain)
    palette = build_palette(fv, rng)

    a, b, c, d = _feature_vector_to_params(fv, rng)
    a, b, c, d = _stabilize(a, b, c, d, rng)

    # interaction_diversity -> point density: wallets that touch many unique
    # counterparties render a richer, denser point-cloud than narrow/repetitive ones.
    iterations = int(_lerp(MIN_ITERATIONS, MAX_ITERATIONS, fv.interaction_diversity))

    canvas = None
    for _ in range(MAX_STABILIZE_ATTEMPTS):
        xs, ys = _iterate(a, b, c, d, iterations)
        candidate = _accumulate(xs, ys, size)
        # The cheap short-sample check in _stabilize() catches divergence and
        # fixed points, but not slow-converging spirals — those only reveal
        # themselves at full resolution/iteration count, where nearly all mass
        # piles into a small area instead of covering the frame. Rendering is
        # fast (~0.3s for 300k points), so re-checking here and reshuffling
        # params on failure is cheap insurance against a boring result.
        if _is_rich(candidate):
            canvas = candidate
            break
        a, b, c, d = _stabilize(
            a + rng.uniform(-0.3, 0.3), b + rng.uniform(-0.3, 0.3),
            c + rng.uniform(-0.3, 0.3), d + rng.uniform(-0.3, 0.3),
            rng,
        )
    if canvas is None:
        canvas = candidate  # best effort — still bounded/non-degenerate, just sparser

    # burst_coefficient -> point sharpness: bursty wallets (activity clustered
    # in tight bunches) get crisp, sharply-defined trails; steady/regular
    # wallets get a softer, more diffuse glow, as if smoothed over time.
    blur_sigma = _lerp(1.8, 0.0, fv.burst_coefficient)
    if blur_sigma > 0.05:
        canvas = gaussian_filter(canvas, sigma=blur_sigma)

    image = _colorize(canvas, palette, fv)

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _is_rich(canvas: np.ndarray) -> bool:
    """True if the full-resolution histogram actually fills a healthy portion
    of the frame, rather than concentrating almost entirely into one small
    region (a slow-converging spiral or near-fixed point)."""
    total = canvas.sum()
    if total <= 0:
        return False
    visited_fraction = (canvas > 0).sum() / canvas.size
    max_share = canvas.max() / total
    return visited_fraction > 0.12 and max_share < 0.01


# ---------------------------------------------------------------------------
# Seeding (matches composer.py's determinism contract)
# ---------------------------------------------------------------------------

def _make_rng(wallet_address: str, chain: str) -> random.Random:
    import hashlib
    seed_input = f"{wallet_address.lower()}:{chain}:attractor".encode("utf-8")
    seed_bytes = hashlib.sha256(seed_input).digest()
    return random.Random(int.from_bytes(seed_bytes, "big"))


# ---------------------------------------------------------------------------
# Parameter mapping
# ---------------------------------------------------------------------------

def _feature_vector_to_params(fv: FeatureVector, rng: random.Random) -> tuple[float, float, float, float]:
    """
    Map the 8D feature vector to Clifford attractor coefficients (a, b, c, d),
    each in the classic "interesting" range of roughly [-2, 2].
    """
    a = _lerp(-2.0, 2.0, fv.activity_entropy)
    b = _lerp(-2.0, 2.0, fv.chaos_dimension)
    c = _lerp(-2.0, 2.0, fv.amount_variance)
    d = _lerp(-2.0, 2.0, fv.timing_regularity)

    # Small seeded jitter so distinct wallets with similar feature vectors
    # (e.g. two dormant wallets) don't collapse onto visually identical params.
    a += rng.uniform(-0.05, 0.05)
    b += rng.uniform(-0.05, 0.05)
    c += rng.uniform(-0.05, 0.05)
    d += rng.uniform(-0.05, 0.05)
    return a, b, c, d


def _stabilize(a: float, b: float, c: float, d: float, rng: random.Random) -> tuple[float, float, float, float]:
    """
    Ensure (a, b, c, d) produces a bounded, non-degenerate attractor.
    Deterministically perturbs the parameters (via the seeded rng) until the
    trajectory neither diverges nor collapses to a near-fixed point.
    """
    for _ in range(MAX_STABILIZE_ATTEMPTS):
        if _is_stable(a, b, c, d):
            return a, b, c, d
        a += rng.uniform(-0.3, 0.3)
        b += rng.uniform(-0.3, 0.3)
        c += rng.uniform(-0.3, 0.3)
        d += rng.uniform(-0.3, 0.3)

    # Fell through without finding a stable set — fall back to a known-good
    # classic Clifford configuration so we never render a blank image.
    return -1.4, 1.6, 1.0, 0.7


def _is_stable(a: float, b: float, c: float, d: float) -> bool:
    """
    A "stable" attractor here means bounded AND actually space-filling —
    not collapsed onto a fixed point or short periodic cycle. A short cycle
    can still show a healthy min/max spread over a few thousand points (it
    keeps revisiting the same handful of locations), so the real test is
    how many distinct regions of a coarse grid get visited: a genuine
    chaotic trajectory covers a large fraction of it; a period-N cycle only
    ever touches N cells no matter how long you run it.
    """
    x, y = 0.1, 0.1
    xs = np.empty(SAMPLE_CHECK, dtype=np.float64)
    ys = np.empty(SAMPLE_CHECK, dtype=np.float64)
    for i in range(BURN_IN + SAMPLE_CHECK):
        x, y = math.sin(a * y) + c * math.cos(a * x), math.sin(b * x) + d * math.cos(b * y)
        if not (math.isfinite(x) and math.isfinite(y)):
            return False
        if abs(x) > 10 or abs(y) > 10:
            return False
        if i >= BURN_IN:
            xs[i - BURN_IN] = x
            ys[i - BURN_IN] = y

    x_range = xs.max() - xs.min()
    y_range = ys.max() - ys.min()
    if x_range < 0.05 or y_range < 0.05:
        return False

    grid = 60
    hist, _, _ = np.histogram2d(xs, ys, bins=grid)
    visited_fraction = (hist > 0).sum() / (grid * grid)
    return visited_fraction > 0.15


# ---------------------------------------------------------------------------
# Trajectory iteration + density accumulation
# ---------------------------------------------------------------------------

def _iterate(a: float, b: float, c: float, d: float, iterations: int, burn_in: int = BURN_IN) -> tuple[np.ndarray, np.ndarray]:
    """
    Iterate the map, discarding the first `burn_in` points before recording.
    Without this, the initial transient — which can wander far from where the
    trajectory eventually settles, especially for tightly-converging spiral-
    type attractors — gets included in the recorded points and badly distorts
    the auto-scaled canvas bounds computed in _accumulate() (the real
    attractor ends up squeezed into a tiny corner of the frame).
    """
    xs = np.empty(iterations, dtype=np.float64)
    ys = np.empty(iterations, dtype=np.float64)
    x, y = 0.1, 0.1
    sin, cos = math.sin, math.cos
    for _ in range(burn_in):
        x, y = sin(a * y) + c * cos(a * x), sin(b * x) + d * cos(b * y)
    for i in range(iterations):
        x, y = sin(a * y) + c * cos(a * x), sin(b * x) + d * cos(b * y)
        xs[i] = x
        ys[i] = y
    return xs, ys


def _accumulate(xs: np.ndarray, ys: np.ndarray, size: int) -> np.ndarray:
    """Bin the trajectory into a size x size density histogram, centered and padded."""
    pad = 0.08
    x_min, x_max = xs.min(), xs.max()
    y_min, y_max = ys.min(), ys.max()
    x_range = (x_max - x_min) or 1.0
    y_range = (y_max - y_min) or 1.0
    x_min -= x_range * pad
    x_max += x_range * pad
    y_min -= y_range * pad
    y_max += y_range * pad

    hist, _, _ = np.histogram2d(
        xs, ys, bins=size, range=[[x_min, x_max], [y_min, y_max]]
    )
    return hist.T  # transpose so rows=y (image convention)


def _colorize(canvas: np.ndarray, palette, fv: FeatureVector) -> Image.Image:
    """Map the density histogram to an RGB image using the deterministic palette."""
    # Log compression: attractors have a few very hot pixels and a long tail
    # of lightly-visited ones — without this the glow would be nearly invisible.
    density = np.log1p(canvas)
    peak = density.max() or 1.0

    # volume_skew -> contrast: wallets whose value is dominated by a few large
    # transactions get a punchier, higher-contrast gamma curve; evenly-sized
    # transactions get a softer, more uniform falloff.
    gamma = _lerp(0.85, 0.35, fv.volume_skew)
    intensity = np.clip(density / peak, 0.0, 1.0) ** gamma

    bg = _hsl_to_rgb01(palette.background.h, palette.background.s, palette.background.l)
    glow = _hsl_to_rgb01(palette.glow.h, palette.glow.s, palette.glow.l)
    primary = _hsl_to_rgb01(palette.primary.h, palette.primary.s, palette.primary.l)

    # Two-stage ramp: background -> primary (mid density) -> glow (hottest pixels)
    mid_mask = intensity[..., None]
    low_to_mid = bg + (primary - bg) * np.clip(intensity * 2.0, 0, 1)[..., None]
    mid_to_high = primary + (glow - primary) * np.clip(intensity * 2.0 - 1.0, 0, 1)[..., None]
    rgb = np.where(mid_mask < 0.5, low_to_mid, mid_to_high)

    # recency_decay -> overall brightness: dormant wallets render dimmer/fainter,
    # recently-active wallets render at full vividness.
    brightness = _lerp(0.45, 1.0, fv.recency_decay)
    rgb = rgb * brightness

    rgb8 = np.clip(rgb * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(rgb8, mode="RGB")


def _hsl_to_rgb01(h: float, s: float, l: float) -> np.ndarray:
    import colorsys
    r, g, b = colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
    return np.array([r, g, b], dtype=np.float64)


def _lerp(a: float, b: float, t: float) -> float:
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t
