"""Checks on the committed AnnaHandNerdMono build. Run from the repo root:
    python -m pytest tools/test_nerd_mono.py -q

Only reads fonts/AnnaHandNerdMono, so it runs in CI without the Nerd Fonts
source files in /tmp.
"""
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

OUT = Path(__file__).resolve().parents[1] / "fonts" / "AnnaHandNerdMono"
STEM = "AnnaHandNerdMono-Regular"
CELL = 600
FLAVORS = ("ttf", "otf", "woff2", "woff")


@pytest.fixture(scope="module")
def ttf():
    return TTFont(OUT / f"{STEM}.ttf")


def test_files_exist():
    for ext in FLAVORS:
        assert (OUT / f"{STEM}.{ext}").is_file(), ext
    assert (OUT / "AnnaHandNerdMono.css").is_file()
    assert (OUT / "LICENSE-NerdFonts").is_file()


@pytest.mark.parametrize("ext", FLAVORS)
def test_flavor_loads_with_cmap(ext):
    cmap = TTFont(OUT / f"{STEM}.{ext}").getBestCmap()
    assert ord("A") in cmap and ord("a") in cmap and ord("0") in cmap


def test_all_advances_equal_cell(ttf):
    advances = {adv for adv, _lsb in ttf["hmtx"].metrics.values()}
    assert advances == {CELL}


def test_hhea_and_os2_report_monospace(ttf):
    assert ttf["post"].isFixedPitch == 1
    assert ttf["hhea"].advanceWidthMax == CELL
    assert ttf["OS/2"].xAvgCharWidth == CELL
    assert ttf["OS/2"].panose.bProportion == 9


def test_nerd_symbols_present(ttf):
    cmap = ttf.getBestCmap()
    for cp in (0xE0B0, 0xF015, 0xE615, 0xF09B, 0xF07C):
        assert cp in cmap, hex(cp)


def test_cmap_has_wide_subtable(ttf):
    formats = {t.format for t in ttf["cmap"].tables}
    assert {4, 12} <= formats


def test_family_name(ttf):
    name = ttf["name"]
    assert name.getDebugName(1) == "AnnaHandNerdMono"
    assert name.getDebugName(16) == "AnnaHandNerdMono"
    assert name.getDebugName(6) == STEM


def test_glyph_count_matches_cmap(ttf):
    assert ttf["maxp"].numGlyphs == len(ttf.getGlyphOrder())
    assert len(ttf.getBestCmap()) >= 10000


def test_otf_is_cff_and_monospace():
    otf = TTFont(OUT / f"{STEM}.otf")
    assert "CFF " in otf
    assert otf["post"].isFixedPitch == 1
    assert {adv for adv, _ in otf["hmtx"].metrics.values()} == {CELL}
    assert otf.getBestCmap()[0xE0B0] is not None
