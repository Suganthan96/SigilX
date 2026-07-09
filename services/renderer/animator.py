"""
services/renderer/animator.py

Generates the <style> block with CSS @keyframes animations.
Animation parameters are driven by the FeatureVector — deterministically.

Rules:
  - burst_coefficient  → animation speed (slow/meditative → fast/frantic)
  - chaos_dimension    → number of distinct animation cycles
  - timing_regularity  → whether animations are smooth or jerky
  - recency_decay      → pulse intensity (active wallets pulse strongly)
"""

from __future__ import annotations

import random
from ..extractor.fingerprint import FeatureVector


def build_animation_css(fv: FeatureVector, rng: random.Random) -> str:
    """
    Build the complete <style> block for SVG animations.

    Returns:
        A CSS string (without <style> tags) ready to embed in SVG.
    """
    # Animation speed: burst wallets animate faster
    base_duration = _lerp(12.0, 3.0, fv.burst_coefficient)   # seconds
    pulse_duration = _lerp(6.0, 1.5, fv.burst_coefficient)

    # Timing function: regular wallets get easeInOut, chaotic get linear
    easing = "ease-in-out" if fv.timing_regularity > 0.5 else "linear"

    # Pulse intensity: recency_decay drives scale amplitude
    pulse_scale_max = _lerp(1.01, 1.08, fv.recency_decay)
    pulse_scale_min = _lerp(0.99, 0.94, fv.recency_decay)

    # Rotation speed and direction
    rotate_deg = rng.choice([360, -360])
    float_amp = _lerp(3.0, 18.0, fv.chaos_dimension)    # px up/down float
    glow_opacity_max = _lerp(0.6, 1.0, fv.recency_decay)
    glow_opacity_min = _lerp(0.1, 0.4, 1.0 - fv.recency_decay)

    css = f"""
    /* === SigilX Chain Portrait Animations === */

    @keyframes sigilx-orb-pulse {{
      0%   {{ transform: scale(1.0);      opacity: {glow_opacity_min:.2f}; }}
      50%  {{ transform: scale({pulse_scale_max:.3f}); opacity: {glow_opacity_max:.2f}; }}
      100% {{ transform: scale(1.0);      opacity: {glow_opacity_min:.2f}; }}
    }}

    @keyframes sigilx-sigil-rotate {{
      from {{ transform: rotate(0deg); }}
      to   {{ transform: rotate({rotate_deg}deg); }}
    }}

    @keyframes sigilx-float {{
      0%   {{ transform: translateY(0px); }}
      50%  {{ transform: translateY(-{float_amp:.1f}px); }}
      100% {{ transform: translateY(0px); }}
    }}

    @keyframes sigilx-filament-draw {{
      from {{ stroke-dashoffset: 1000; opacity: 0; }}
      to   {{ stroke-dashoffset: 0;    opacity: 1; }}
    }}

    @keyframes sigilx-spark-twinkle {{
      0%   {{ opacity: 0;    r: 0.5; }}
      50%  {{ opacity: 1;    r: 2.5; }}
      100% {{ opacity: 0;    r: 0.5; }}
    }}

    @keyframes sigilx-bg-breathe {{
      0%   {{ opacity: 0.85; }}
      50%  {{ opacity: 1.0;  }}
      100% {{ opacity: 0.85; }}
    }}

    .sigilx-orb {{
      animation: sigilx-orb-pulse {pulse_duration:.2f}s {easing} infinite;
      transform-origin: center;
    }}

    .sigilx-orb:nth-child(2n) {{
      animation-delay: -{pulse_duration * 0.5:.2f}s;
    }}

    .sigilx-orb:nth-child(3n) {{
      animation-delay: -{pulse_duration * 0.33:.2f}s;
      animation-duration: {pulse_duration * 1.3:.2f}s;
    }}

    .sigilx-sigil {{
      animation: sigilx-sigil-rotate {base_duration:.2f}s linear infinite,
                 sigilx-float {base_duration * 0.7:.2f}s {easing} infinite;
      transform-origin: center;
    }}

    .sigilx-sigil:nth-child(2n) {{
      animation-direction: reverse;
      animation-delay: -{base_duration * 0.4:.2f}s;
    }}

    .sigilx-sigil:nth-child(3n) {{
      animation-duration: {base_duration * 1.5:.2f}s, {base_duration * 1.1:.2f}s;
    }}

    .sigilx-filament {{
      stroke-dasharray: 1000;
      stroke-dashoffset: 0;
      animation: sigilx-bg-breathe {base_duration * 0.8:.2f}s {easing} infinite;
    }}

    .sigilx-spark {{
      animation: sigilx-spark-twinkle {_lerp(1.5, 0.5, fv.burst_coefficient):.2f}s {easing} infinite;
    }}

    .sigilx-spark:nth-child(3n) {{
      animation-delay: -{_lerp(0.3, 0.1, fv.burst_coefficient):.2f}s;
    }}

    .sigilx-spark:nth-child(5n) {{
      animation-delay: -{_lerp(0.7, 0.2, fv.burst_coefficient):.2f}s;
      animation-duration: {_lerp(2.0, 0.7, fv.burst_coefficient):.2f}s;
    }}

    .sigilx-bg {{
      animation: sigilx-bg-breathe {base_duration * 2:.2f}s {easing} infinite;
    }}
    """

    return css.strip()


def _lerp(a: float, b: float, t: float) -> float:
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t
