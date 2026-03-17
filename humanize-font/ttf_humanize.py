#!/usr/bin/env python3
"""
Humanize a .ttf font by subtly altering glyph vector outlines.
Uses fontTools; assumes the .ttf file and this script are in the same directory.
"""

import math
import random
from pathlib import Path

from fontTools.ttLib import TTFont

# -----------------------------------------------------------------------------
# Tunable parameters (experiment variables)
# -----------------------------------------------------------------------------

# 1. Coordinate noise: range of randomness added to x/y
x_noise = 3
y_noise = 3

# 2. Shirorekha protection: prevent distortion near top headline (Devanagari)
shirorekha_y_threshold = 500
shirorekha_noise = 1

# 3. Curve distortion: sine-based smooth variation
curve_amplitude = 3
curve_frequency = 50

# 4. Directional bias: consistent shift of strokes
x_bias = 1.5
y_bias = 0

# 5. Corner softening: slightly round sharp edges (0 = none, 1 = very soft)
corner_softness = 0.2

# 6. Vertical vs curve sensitivity: vertical strokes less distorted
vertical_preserve_threshold = 2  # slope threshold (|dy/dx|)
vertical_noise = 1
curve_noise = 4

# 7. Glyph selection: only these glyphs are modified (None = all)
target_glyphs = None  # e.g. ["0061", "0062", "0063"] or None

# 8. Baseline protection: avoid breaking alignment
baseline_y = 0
baseline_tolerance = 10
baseline_noise = 0.5

# 9. Global scaling distortion: slight per-glyph stretch/compress
x_scale_variation = 0.01
y_scale_variation = 0.01

# I/O and reproducibility
SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_FONT = SCRIPT_DIR / "Ams Chandrakant.ttf"
OUTPUT_FONT = SCRIPT_DIR / "Ams Chandrakant_humanized.ttf"
RANDOM_SEED = None  # set to an int for reproducible runs


def _get_on_curve_indices_per_contour(glyph):
    """Return list of lists: for each contour, indices of on-curve points."""
    coords = glyph.coordinates
    flags = glyph.flags
    end_pts = glyph.endPtsOfContours
    on_curve_per_contour = []
    start = 0
    for end in end_pts:
        on_curve = [i for i in range(start, end + 1) if flags[i]]
        on_curve_per_contour.append(on_curve)
        start = end + 1
    return on_curve_per_contour


def _slope_to_next_on_curve(coords, flags, idx, end_pts_of_contours):
    """Slope (dy/dx) from point idx to the next on-curve point in its contour."""
    # Find which contour idx belongs to and the next on-curve index in that contour
    start = 0
    for end in end_pts_of_contours:
        if start <= idx <= end:
            # Next on-curve in this contour (wrap to start of contour)
            for i in range(1, end - start + 2):
                next_idx = start + (idx - start + i) % (end - start + 1)
                if flags[next_idx]:
                    dx = coords[next_idx][0] - coords[idx][0]
                    dy = coords[next_idx][1] - coords[idx][1]
                    if abs(dx) < 1e-6:
                        return float("inf") if dy != 0 else 0.0
                    return dy / dx
            return 0.0
        start = end + 1
    return 0.0


def humanize_glyph(glyph, glyph_name, glyf_table):
    """
    Apply controlled distortions to a simple glyph's outline.
    Skips composite glyphs. Modifies glyph in place.
    """
    if not hasattr(glyph, "coordinates") or glyph.numberOfContours <= 0:
        return False
    coords = glyph.coordinates
    flags = glyph.flags
    n = len(coords)
    if n == 0:
        return False

    end_pts = glyph.endPtsOfContours
    on_curve_per_contour = _get_on_curve_indices_per_contour(glyph)

    # --- 1. Corner softening (on original geometry) ---
    # For each on-curve point, blend toward midpoint of prev/next on-curve in same contour
    if corner_softness > 0:
        for contour_on_curve in on_curve_per_contour:
            if len(contour_on_curve) < 3:
                continue
            for k, idx in enumerate(contour_on_curve):
                prev_idx = contour_on_curve[(k - 1) % len(contour_on_curve)]
                next_idx = contour_on_curve[(k + 1) % len(contour_on_curve)]
                x, y = coords[idx]
                px, py = coords[prev_idx]
                nx, ny = coords[next_idx]
                mid_x = (px + nx) / 2
                mid_y = (py + ny) / 2
                new_x = x + corner_softness * (mid_x - x)
                new_y = y + corner_softness * (mid_y - y)
                coords[idx] = (new_x, new_y)

    # --- 2. Global scaling distortion (per-glyph) ---
    sx = 1.0 + random.uniform(-x_scale_variation, x_scale_variation)
    sy = 1.0 + random.uniform(-y_scale_variation, y_scale_variation)
    for i in range(n):
        x, y = coords[i]
        coords[i] = (x * sx, y * sy)

    # --- 2b. Precompute slope at each point (for noise selection) ---
    slopes = [_slope_to_next_on_curve(coords, flags, i, end_pts) for i in range(n)]

    # --- 3. Per-point: noise selection, protections, noise, sine, bias ---
    for i in range(n):
        x, y = coords[i]

        # Effective noise scale: vertical strokes use vertical_noise, else curve_noise
        slope = slopes[i]
        abs_slope = abs(slope) if math.isfinite(slope) else 1e9
        if abs_slope >= vertical_preserve_threshold:
            eff_x_noise = vertical_noise
            eff_y_noise = vertical_noise
        else:
            eff_x_noise = curve_noise
            eff_y_noise = curve_noise

        # Shirorekha protection: near top headline, reduce noise
        if y > shirorekha_y_threshold:
            eff_x_noise = min(eff_x_noise, shirorekha_noise)
            eff_y_noise = min(eff_y_noise, shirorekha_noise)

        # Baseline protection: near baseline, reduce noise
        if abs(y - baseline_y) <= baseline_tolerance:
            eff_x_noise = min(eff_x_noise, baseline_noise)
            eff_y_noise = min(eff_y_noise, baseline_noise)

        # Scale by global x_noise/y_noise (so we still respect overall strength)
        rx = eff_x_noise * (x_noise / max(curve_noise, 1))
        ry = eff_y_noise * (y_noise / max(curve_noise, 1))

        # Random coordinate noise
        x += random.uniform(-rx, rx)
        y += random.uniform(-ry, ry)

        # Sine-based curve distortion (smooth human-like variation)
        x += curve_amplitude * math.sin(y / curve_frequency)

        # Directional bias
        x += x_bias
        y += y_bias

        # Round to integers (TrueType requirement)
        coords[i] = (round(x), round(y))

    glyph.recalcBounds(glyf_table)
    return True


def main():
    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    font_path = INPUT_FONT
    out_path = OUTPUT_FONT
    if not font_path.exists():
        print(f"Input font not found: {font_path}")
        return 1

    print(f"Loading {font_path} ...")
    font = TTFont(font_path)
    glyf = font["glyf"]
    glyph_order = list(glyf.keys())

    if target_glyphs is not None:
        glyph_order = [g for g in glyph_order if g in target_glyphs]

    processed = 0
    for name in glyph_order:
        glyph = glyf[name]
        if humanize_glyph(glyph, name, glyf):
            processed += 1

    print(f"Saving {out_path} ({processed} glyphs humanized) ...")
    font.save(out_path)
    font.close()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
