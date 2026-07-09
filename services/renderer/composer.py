"""
services/renderer/composer.py

Assembles the final SVG from all renderer sub-modules.

Entry point: render_portrait(wallet_address, chain, feature_vector) → str (SVG)

Determinism guarantee:
  All randomness seeded from SHA-256(wallet_address.lower() + ":" + chain).
  Same inputs → character-for-character identical SVG output.
"""

from __future__ import annotations

import hashlib
import random

from ..extractor.fingerprint import FeatureVector
from .palette import build_palette, Palette
from .shapes import build_shapes, ShapeSet, SIZE
from .animator import build_animation_css


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_portrait(
    wallet_address: str,
    chain: str,
    fv: FeatureVector,
) -> str:
    """
    Render a deterministic Chain Portrait SVG.

    Args:
        wallet_address: EVM wallet address (normalized to lowercase internally).
        chain:          Chain identifier (e.g. "eth-mainnet").
        fv:             Normalized FeatureVector from the extraction pipeline.

    Returns:
        Complete SVG string, 600×600px, with embedded CSS animations.
        Character-for-character identical for the same inputs.
    """
    rng = _make_rng(wallet_address, chain)

    palette = build_palette(fv, rng)
    shapes = build_shapes(fv, rng, palette)
    anim_css = build_animation_css(fv, rng)

    return _assemble_svg(fv, palette, shapes, anim_css, wallet_address, chain)


# ---------------------------------------------------------------------------
# SVG assembly
# ---------------------------------------------------------------------------

def _assemble_svg(
    fv: FeatureVector,
    palette: Palette,
    shapes: ShapeSet,
    anim_css: str,
    wallet_address: str,
    chain: str,
) -> str:
    parts: list[str] = []

    # ── Header ──────────────────────────────────────────────────────────────
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {SIZE} {SIZE}" width="{SIZE}" height="{SIZE}" '
        f'style="background:{palette.background.to_css()}">'
    )

    # ── Embedded styles ──────────────────────────────────────────────────────
    parts.append(f"<style>{anim_css}</style>")

    # ── Defs: gradients + filters ────────────────────────────────────────────
    parts.append("<defs>")

    # Radial gradient per orb color
    for i, mid_color in enumerate(palette.mids):
        parts.append(
            f'<radialGradient id="orb-grad-{i}" cx="50%" cy="35%" r="65%">'
            f'<stop offset="0%" stop-color="{mid_color.lighten(25).to_css()}" stop-opacity="0.9"/>'
            f'<stop offset="60%" stop-color="{mid_color.to_css()}" stop-opacity="0.6"/>'
            f'<stop offset="100%" stop-color="{mid_color.darken(20).to_css()}" stop-opacity="0"/>'
            f"</radialGradient>"
        )

    # Linear gradient for background vignette
    parts.append(
        '<radialGradient id="bg-vignette" cx="50%" cy="50%" r="70%">'
        f'<stop offset="0%" stop-color="{palette.background.lighten(5).to_css()}" stop-opacity="1"/>'
        f'<stop offset="100%" stop-color="{palette.background.darken(3).to_css()}" stop-opacity="1"/>'
        "</radialGradient>"
    )

    # Glow filter
    parts.append(
        '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur stdDeviation="8" result="blur"/>'
        '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>'
        "</filter>"
    )

    # Soft blur filter for orbs
    parts.append(
        '<filter id="soft-blur" x="-30%" y="-30%" width="160%" height="160%">'
        '<feGaussianBlur stdDeviation="12"/>'
        "</filter>"
    )

    parts.append("</defs>")

    # ── Background ────────────────────────────────────────────────────────────
    parts.append(
        f'<rect class="sigilx-bg" width="{SIZE}" height="{SIZE}" '
        f'fill="url(#bg-vignette)"/>'
    )

    # ── Orb layer (bottom) ───────────────────────────────────────────────────
    parts.append('<g id="layer-orbs">')
    for orb in shapes.orbs:
        cid = orb.color_index % len(palette.mids)
        parts.append(
            f'<circle class="sigilx-orb" '
            f'cx="{orb.cx:.1f}" cy="{orb.cy:.1f}" r="{orb.r:.1f}" '
            f'fill="url(#orb-grad-{cid})" '
            f'opacity="{orb.opacity:.2f}" '
            f'filter="url(#soft-blur)"/>'
        )
    parts.append("</g>")

    # ── Filament layer (mid-bottom) ───────────────────────────────────────────
    parts.append('<g id="layer-filaments">')
    for fil in shapes.filaments:
        dash_attr = f'stroke-dasharray="{fil.dash}"' if fil.dash != "none" else ""
        parts.append(
            f'<path class="sigilx-filament" '
            f'd="{fil.path_d}" '
            f'fill="none" '
            f'stroke="{fil.stroke}" '
            f'stroke-width="{fil.stroke_width:.2f}" '
            f'opacity="{fil.opacity:.2f}" '
            f'{dash_attr}/>'
        )
    parts.append("</g>")

    # ── Sigil layer (mid-top) ─────────────────────────────────────────────────
    parts.append('<g id="layer-sigils">')
    for sig in shapes.sigils:
        parts.append(
            f'<path class="sigilx-sigil" '
            f'd="{sig.path_d}" '
            f'fill="{sig.fill}" '
            f'stroke="{sig.stroke}" '
            f'stroke-width="{sig.stroke_width:.2f}" '
            f'opacity="{sig.opacity:.2f}" '
            f'filter="url(#glow)"/>'
        )
    parts.append("</g>")

    # ── Spark layer (top) ─────────────────────────────────────────────────────
    parts.append('<g id="layer-sparks">')
    for sp in shapes.sparks:
        parts.append(
            f'<circle class="sigilx-spark" '
            f'cx="{sp.cx:.1f}" cy="{sp.cy:.1f}" r="{sp.r:.2f}" '
            f'fill="{sp.color}" '
            f'opacity="{sp.opacity:.2f}"/>'
        )
    parts.append("</g>")

    # ── Watermark (corner, small) ─────────────────────────────────────────────
    short_addr = wallet_address[:6] + "…" + wallet_address[-4:]
    parts.append(
        f'<text x="{SIZE - 10}" y="{SIZE - 8}" '
        f'text-anchor="end" '
        f'font-family="monospace" font-size="9" '
        f'fill="{palette.stroke.to_css()}" opacity="0.5">'
        f'SigilX · {short_addr} · {chain}'
        f"</text>"
    )

    # ── Close ─────────────────────────────────────────────────────────────────
    parts.append("</svg>")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Seeded RNG
# ---------------------------------------------------------------------------

def _make_rng(wallet_address: str, chain: str) -> random.Random:
    """
    Create a deterministic random.Random instance seeded from the wallet + chain.
    SHA-256 is used as a platform-independent, stable hash (unlike Python's hash()).
    """
    seed_input = f"{wallet_address.lower()}:{chain}".encode("utf-8")
    seed_bytes = hashlib.sha256(seed_input).digest()
    seed_int = int.from_bytes(seed_bytes, "big")
    return random.Random(seed_int)
