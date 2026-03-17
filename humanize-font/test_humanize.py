#!/usr/bin/env python3
"""
Test script for ttf_humanize.py.
Verifies that the humanizer runs correctly and produces a valid, modified font.
Run from the humanize-font directory: python test_humanize.py
"""

import sys
from pathlib import Path

# Run from script's directory
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Use fixed seed so humanizer output is reproducible for comparison
import ttf_humanize

ttf_humanize.RANDOM_SEED = 42


def test_input_font_exists():
    """Input font must exist."""
    assert ttf_humanize.INPUT_FONT.exists(), (
        f"Input font not found: {ttf_humanize.INPUT_FONT}"
    )
    print("  [OK] Input font exists")


def test_run_humanizer():
    """Running the humanizer should exit 0 and create output file."""
    code = ttf_humanize.main()
    assert code == 0, f"humanizer main() returned {code}"
    assert ttf_humanize.OUTPUT_FONT.exists(), (
        f"Output font not created: {ttf_humanize.OUTPUT_FONT}"
    )
    print("  [OK] Humanizer ran and created output font")


def test_output_is_valid_ttf():
    """Output file should be a loadable TTF with expected tables."""
    from fontTools.ttLib import TTFont

    font = TTFont(ttf_humanize.OUTPUT_FONT)
    assert "glyf" in font, "Missing glyf table"
    assert "head" in font, "Missing head table"
    glyph_count = len(font["glyf"])
    assert glyph_count > 0, "Font has no glyphs"
    font.close()
    print(f"  [OK] Output is valid TTF ({glyph_count} glyphs)")


def test_glyph_count_unchanged():
    """Humanized font should have the same number of glyphs as input."""
    from fontTools.ttLib import TTFont

    orig = TTFont(ttf_humanize.INPUT_FONT)
    human = TTFont(ttf_humanize.OUTPUT_FONT)
    orig_count = len(orig["glyf"])
    human_count = len(human["glyf"])
    orig.close()
    human.close()
    assert orig_count == human_count, (
        f"Glyph count changed: {orig_count} -> {human_count}"
    )
    print(f"  [OK] Glyph count unchanged ({orig_count})")


def test_coordinates_actually_changed():
    """At least one simple glyph should have different coordinates after humanization."""
    from fontTools.ttLib import TTFont

    orig = TTFont(ttf_humanize.INPUT_FONT)
    human = TTFont(ttf_humanize.OUTPUT_FONT)
    glyf_orig = orig["glyf"]
    glyf_human = human["glyf"]

    changed_count = 0
    for name in list(glyf_orig.keys())[:50]:  # check first 50 glyphs
        go = glyf_orig[name]
        gh = glyf_human[name]
        if not hasattr(go, "coordinates") or go.numberOfContours <= 0:
            continue
        co_orig = list(go.coordinates)
        co_human = list(gh.coordinates)
        if len(co_orig) != len(co_human):
            continue
        if co_orig != co_human:
            changed_count += 1

    orig.close()
    human.close()
    assert changed_count > 0, (
        "No glyph coordinates changed (humanization may not be applied)"
    )
    print(f"  [OK] Coordinates changed in at least one glyph (checked first 50, {changed_count} differed)")


def test_structure_preserved():
    """Each glyph should keep same number of points and contours."""
    from fontTools.ttLib import TTFont

    orig = TTFont(ttf_humanize.INPUT_FONT)
    human = TTFont(ttf_humanize.OUTPUT_FONT)
    glyf_orig = orig["glyf"]
    glyf_human = human["glyf"]

    for name in glyf_orig.keys():
        go = glyf_orig[name]
        gh = glyf_human[name]
        assert go.numberOfContours == gh.numberOfContours, (
            f"Glyph {name}: contour count changed"
        )
        if hasattr(go, "coordinates") and go.numberOfContours > 0:
            assert len(go.coordinates) == len(gh.coordinates), (
                f"Glyph {name}: point count changed"
            )

    orig.close()
    human.close()
    print("  [OK] Glyph structure preserved (contours and point counts)")


def main():
    print("Testing ttf_humanize ...")
    tests = [
        test_input_font_exists,
        test_run_humanizer,
        test_output_is_valid_ttf,
        test_glyph_count_unchanged,
        test_coordinates_actually_changed,
        test_structure_preserved,
    ]
    failed = []
    for test_fn in tests:
        try:
            test_fn()
        except AssertionError as e:
            print(f"  [FAIL] {test_fn.__name__}: {e}")
            failed.append(test_fn.__name__)
        except Exception as e:
            print(f"  [ERROR] {test_fn.__name__}: {e}")
            failed.append(test_fn.__name__)

    if failed:
        print(f"\nFailed: {', '.join(failed)}")
        return 1
    print("\nAll tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
