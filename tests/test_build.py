"""Trace synthetic glyph bitmaps and build a font from them (no scanner needed)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest
from fontTools.pens.pointInsidePen import PointInsidePen
from fontTools.ttLib import TTFont

from handfont import layout
from handfont.build import build_font
from handfont.vectorize import trace_glyph

PX_PER_MM = 10.0
H = W = 120
BASELINE_PX = 100
SCALE = layout.UNITS_PER_MM / PX_PER_MM  # font units per pixel


@dataclass
class FakeGlyph:
    char: str
    ink: np.ndarray
    baseline_px: int
    px_per_mm: float


def _blank() -> np.ndarray:
    return np.zeros((H, W), dtype=bool)


def _rect_I() -> FakeGlyph:
    ink = _blank()
    ink[30:BASELINE_PX, 40:50] = True
    return FakeGlyph("I", ink, BASELINE_PX, PX_PER_MM)


def _ring_O() -> FakeGlyph:
    yy, xx = np.mgrid[0:H, 0:W]
    d2 = (xx + 0.5 - 60) ** 2 + (yy + 0.5 - 75) ** 2
    ink = (d2 <= 25**2) & (d2 > 12**2)
    return FakeGlyph("O", ink, BASELINE_PX, PX_PER_MM)


def _bar_l() -> FakeGlyph:
    ink = _blank()
    ink[20:BASELINE_PX, 60:68] = True
    return FakeGlyph("l", ink, BASELINE_PX, PX_PER_MM)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("font")
    glyphs = [trace_glyph(g) for g in (_rect_I(), _ring_O(), _bar_l())]
    paths = build_font(glyphs, "HandTest", out)
    return paths


def test_all_files_written(built):
    for key in ("otf", "ttf", "woff2", "woff", "css"):
        assert built[key].exists(), key
        assert built[key].stat().st_size > 0, key


@pytest.mark.parametrize("key", ["ttf", "otf", "woff2"])
def test_fonts_load_with_cmap_and_metrics(built, key):
    font = TTFont(built[key])
    cmap = font.getBestCmap()
    assert ord("I") in cmap
    assert ord("O") in cmap
    assert 0x20 in cmap
    adv_o = font["hmtx"][cmap[ord("O")]][0]
    assert adv_o > 2 * layout.SIDE_BEARING_UNITS
    font.close()


def test_woff_loads(built):
    font = TTFont(built["woff"])
    assert ord("O") in font.getBestCmap()
    font.close()


def test_css_has_font_face(built):
    css = built["css"].read_text(encoding="utf-8")
    assert '@font-face' in css
    assert 'font-family: "HandTest"' in css
    assert "woff2" in css and "woff" in css and "ttf" in css
    assert "font-display: swap" in css


def _inside(font_path, point_units, glyph_name_for_char):
    font = TTFont(font_path)
    gs = font.getGlyphSet()
    pen = PointInsidePen(gs, point_units)
    gs[glyph_name_for_char].draw(pen)
    result = pen.getResult()
    font.close()
    return result


@pytest.mark.parametrize("key", ["ttf", "otf"])
def test_ring_hole_is_empty(built, key):
    font = TTFont(built[key])
    name = font.getBestCmap()[ord("O")]
    font.close()

    # Ring centre in font units: the glyph's ink box is symmetric about it.
    cx = (60 - 35) * SCALE + layout.SIDE_BEARING_UNITS  # col 60 vertex, ink starts at col 35
    cy = (BASELINE_PX - 75) * SCALE
    band = 18.5 * SCALE  # between inner (12 px) and outer (25 px) radius

    assert not _inside(built[key], (cx, cy), name), "centre of O must be the hole"
    assert _inside(built[key], (cx + band, cy), name), "point on the ring must be ink"


@pytest.mark.parametrize("key", ["ttf", "otf"])
def test_bar_I_is_filled(built, key):
    font = TTFont(built[key])
    name = font.getBestCmap()[ord("I")]
    font.close()
    cx = (45 - 40) * SCALE + layout.SIDE_BEARING_UNITS
    cy = (BASELINE_PX - 65) * SCALE  # ink rows 30..100 (pixel edges)
    assert _inside(built[key], (cx, cy), name)
