"""
services/renderer/palette.py

Deterministic color palette engine.
Maps FeatureVector → HSL color palette used throughout the SVG.

Seed: keccak256-equivalent (SHA-256) of wallet+chain is used upstream;
this module receives a seeded random.Random instance.
"""

from __future__ import annotations

import colorsys
import random
from dataclasses import dataclass
from typing import NamedTuple

from ..extractor.fingerprint import FeatureVector


class HSL(NamedTuple):
    h: float   # 0–360
    s: float   # 0–100
    l: float   # 0–100

    def to_css(self) -> str:
        return f"hsl({self.h:.1f},{self.s:.1f}%,{self.l:.1f}%)"

    def to_hex(self) -> str:
        r, g, b = colorsys.hls_to_rgb(self.h / 360, self.l / 100, self.s / 100)
        return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))

    def lighten(self, amount: float) -> "HSL":
        return HSL(self.h, self.s, min(95.0, self.l + amount))

    def darken(self, amount: float) -> "HSL":
        return HSL(self.h, self.s, max(5.0, self.l - amount))

    def shift_hue(self, delta: float) -> "HSL":
        return HSL((self.h + delta) % 360, self.s, self.l)


@dataclass
class Palette:
    """Full color palette for one portrait."""
    background: HSL         # Canvas background
    primary: HSL            # Dominant shape color
    secondary: HSL          # Accent / complement color
    tertiary: HSL           # Highlight color
    glow: HSL               # Bloom / glow effect color
    stroke: HSL             # Outline stroke
    mids: list[HSL]         # 4–6 interpolated mid-tones for gradients


def build_palette(fv: FeatureVector, rng: random.Random) -> Palette:
    """
    Build a deterministic Palette from a FeatureVector.

    Mapping:
      activity_entropy  → hue family (warm ↔ cool)
      timing_regularity → saturation (muted ↔ vivid)
      recency_decay     → lightness / opacity of background
      burst_coefficient → hue spread between primary and secondary
      volume_skew       → whether to use complementary or analogous harmony
    """
    # -----------------------------------------------------------------------
    # 1. Base hue — activity_entropy drives the hue family
    #    0.0 = cool blues/teals (HSL ~180–240)
    #    1.0 = warm magentas/reds (HSL ~300–360/0–30)
    #
    #    Interpolation: low entropy → 195 (teal), high entropy → 320 (violet-red)
    # -----------------------------------------------------------------------
    base_hue = _lerp(195.0, 320.0, fv.activity_entropy)

    # Add a small seeded jitter (±15°) to break monotony
    base_hue = (base_hue + rng.uniform(-15, 15)) % 360

    # -----------------------------------------------------------------------
    # 2. Saturation — timing_regularity (regular = desaturated, chaotic = vivid)
    # -----------------------------------------------------------------------
    saturation = _lerp(45.0, 90.0, 1.0 - fv.timing_regularity)

    # -----------------------------------------------------------------------
    # 3. Background — always dark, recency_decay lightens it slightly
    # -----------------------------------------------------------------------
    bg_lightness = _lerp(4.0, 10.0, fv.recency_decay)
    background = HSL(base_hue, saturation * 0.3, bg_lightness)

    # -----------------------------------------------------------------------
    # 4. Primary color
    # -----------------------------------------------------------------------
    primary_lightness = _lerp(45.0, 65.0, fv.amount_variance)
    primary = HSL(base_hue, saturation, primary_lightness)

    # -----------------------------------------------------------------------
    # 5. Secondary / accent — hue offset driven by burst_coefficient
    #    Low burst → analogous (±30°), high burst → complementary (±150–180°)
    # -----------------------------------------------------------------------
    hue_offset = _lerp(30.0, 175.0, fv.burst_coefficient)
    secondary_hue = (base_hue + hue_offset * rng.choice([1, -1])) % 360
    secondary = HSL(secondary_hue, saturation * 0.85, primary_lightness * 1.1)

    # -----------------------------------------------------------------------
    # 6. Tertiary — volume_skew drives whether it's a split-complement or triad
    # -----------------------------------------------------------------------
    triad_offset = _lerp(90.0, 120.0, fv.volume_skew)
    tertiary = HSL((base_hue + triad_offset) % 360, saturation * 0.7, 70.0)

    # -----------------------------------------------------------------------
    # 7. Glow — bright, slightly shifted version of primary for bloom
    # -----------------------------------------------------------------------
    glow = HSL(base_hue, min(100.0, saturation * 1.1), 75.0)

    # -----------------------------------------------------------------------
    # 8. Stroke — dark, low-opacity version of secondary
    # -----------------------------------------------------------------------
    stroke = HSL(secondary_hue, saturation * 0.5, 20.0)

    # -----------------------------------------------------------------------
    # 9. Mid-tones — gradient stops between primary and secondary
    # -----------------------------------------------------------------------
    num_mids = rng.randint(4, 6)
    mids = [
        HSL(
            _lerp(base_hue, secondary_hue, t),
            _lerp(saturation, saturation * 0.7, t),
            _lerp(primary_lightness, 70.0, t),
        )
        for t in [i / (num_mids - 1) for i in range(num_mids)]
    ]

    return Palette(
        background=background,
        primary=primary,
        secondary=secondary,
        tertiary=tertiary,
        glow=glow,
        stroke=stroke,
        mids=mids,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation, t clamped to [0, 1]."""
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t
