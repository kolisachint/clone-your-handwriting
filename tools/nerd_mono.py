"""Build AnnaHandNerdMono: AnnaHand plus Nerd Font symbols, all in one cell width.

Every glyph gets the same advance (CELL units at UPM 1000), so the font works
in a terminal or code editor. Base letters wider than 90% of the cell are
squeezed horizontally; the rest are only centred. Nerd Font symbols that
AnnaHand does not already cover are scaled to fit the cell and added.

Run from the repo root:
    python tools/nerd_mono.py                  # version from the base font
    python tools/nerd_mono.py --version 0.4.0

Needs fontTools[woff] (brotli for WOFF2). Outputs in --out (default
fonts/AnnaHandNerdMono): TTF, WOFF2, WOFF, OTF, AnnaHandNerdMono.css and
LICENSE-NerdFonts (copied from the LICENSE next to --symbols).
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path
from urllib.parse import quote

from fontTools.fontBuilder import FontBuilder
from fontTools.misc.roundTools import otRound
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen, ControlBoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

FAMILY = "AnnaHandNerdMono"
STYLE = "Regular"
PS_NAME = f"{FAMILY}-{STYLE}"
CELL = 600  # advance of every glyph, units at UPM 1000
INK_MAX = CELL * 0.9  # base letters wider than this are squeezed
UPM = 1000
NERD_DESC = (
    "Includes Nerd Fonts symbols (MIT, OFL and CC BY 4.0 icon sets; "
    "see LICENSE-NerdFonts)"
)
DEFAULT_BASE = "fonts/AnnaHand/AnnaHand-Regular.ttf"
DEFAULT_SYMBOLS = "/tmp/nfs/SymbolsNerdFontMono-Regular.ttf"
DEFAULT_OUT = "fonts/AnnaHandNerdMono"


def _default_version(base: TTFont) -> str:
    """AnnaHand head.fontRevision 0.3 -> '0.3.0'."""
    rev = base["head"].fontRevision
    major = int(rev)
    minor = round((rev - major) * 10)
    return f"{major}.{minor}.0"


def _ops(glyph_set, name: str) -> list:
    """Recorded outline of one glyph, components decomposed."""
    pen = DecomposingRecordingPen(glyph_set)
    glyph_set[name].draw(pen)
    return pen.value


def _replay(ops, pen) -> None:
    for op, args in ops:
        getattr(pen, op)(*args)


def _bounds(ops):
    """Tight (xmin, ymin, xmax, ymax) of the outline, or None when empty."""
    pen = BoundsPen(None)
    _replay(ops, pen)
    return pen.bounds


def _map(ops, sx: float, sy: float, dx: float, dy: float) -> list:
    """Scale then shift every point, rounding to whole units."""

    def tp(p):
        return (otRound(sx * p[0] + dx), otRound(sy * p[1] + dy))

    return [
        (op, tuple(None if p is None else tp(p) for p in args))
        for op, args in ops
    ]


def _base_outline(glyph_set, name: str) -> list:
    """Squeeze if too wide, then centre the ink in the cell (horizontal only)."""
    ops = _ops(glyph_set, name)
    box = _bounds(ops)
    if box is None:
        return []
    xmin, _ymin, xmax, _ymax = box
    sx = min(1.0, INK_MAX / (xmax - xmin))
    dx = CELL / 2 - sx * (xmin + xmax) / 2
    return _map(ops, sx, 1.0, dx, 0.0)


def _symbol_outline(glyph_set, name: str, cap: float, em_asc: int, em_desc: int) -> list:
    """Scale the 2048-unit symbol into the cell and line it up with the caps."""
    ops = _ops(glyph_set, name)
    box = _bounds(ops)
    if box is None:
        return []
    em = em_asc - em_desc  # symbol em box height
    s = min(UPM / em, CELL / em)
    xmin, _ymin, xmax, _ymax = box
    if (xmax - xmin) * s > CELL:  # never spill past the cell
        s = CELL / (xmax - xmin)
    dx = CELL / 2 - s * (xmin + xmax) / 2
    # centre of the symbol em box lands on the centre of the caps
    dy = cap / 2 - s * (em_asc + em_desc) / 2
    return _map(ops, s, s, dx, dy)


def _collect(base: TTFont, symbols: TTFont):
    """Return (glyph_order, cmap, outlines) with outlines name -> ops."""
    base_gs = base.getGlyphSet()
    sym_gs = symbols.getGlyphSet()
    cap = base["OS/2"].sCapHeight
    em_asc = symbols["hhea"].ascent
    em_desc = symbols["hhea"].descent

    order = list(base.getGlyphOrder())
    outlines = {n: _base_outline(base_gs, n) for n in order}
    cmap = dict(base.getBestCmap())

    made: dict[str, str] = {}  # symbols glyph name -> new glyph name
    sym_cmap = symbols.getBestCmap()
    for cp in sorted(sym_cmap):
        if cp in cmap:
            continue  # AnnaHand's own glyph wins
        src = sym_cmap[cp]
        if src not in made:
            name = f"nf_{cp:X}"
            made[src] = name
            order.append(name)
            outlines[name] = _symbol_outline(sym_gs, src, cap, em_asc, em_desc)
        cmap[cp] = made[src]
    return order, cmap, outlines


def _metrics(order, outlines):
    """name -> (advance, lsb, xmax); lsb/xmax are 0 for empty glyphs.

    Uses the control box, because the glyf xMin is computed from control
    points. hmtx lsb must equal that xMin or readers shift the glyph.
    """
    metrics = {}
    for name in order:
        pen = ControlBoundsPen(None)
        _replay(outlines[name], pen)
        box = pen.bounds
        if box is None:
            metrics[name] = (CELL, 0, 0)
        else:
            metrics[name] = (CELL, otRound(box[0]), otRound(box[2]))
    return metrics


def _common_tables(fb: FontBuilder, base: TTFont, *, version, order, cmap, metrics):
    """Metrics, names and OS/2 shared by the TTF and OTF builds."""
    hhea = base["hhea"]
    base_os2 = base["OS/2"]
    asc, desc = hhea.ascent, hhea.descent
    ps = PS_NAME
    full = f"{FAMILY} {STYLE}"

    fb.updateHead(fontRevision=float(".".join(version.split(".")[:2])))
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupHorizontalMetrics({n: (adv, lsb) for n, (adv, lsb, _x) in metrics.items()})

    inked = [(lsb, xmax) for _a, lsb, xmax in metrics.values() if xmax]
    fb.setupHorizontalHeader(
        ascent=asc,
        descent=desc,
        lineGap=0,
        advanceWidthMax=CELL,
        minLeftSideBearing=min((l for l, _x in inked), default=0),
        minRightSideBearing=min((CELL - x for _l, x in inked), default=0),
        xMaxExtent=max((x for _l, x in inked), default=0),
    )
    fb.setupNameTable(
        {
            "familyName": FAMILY,
            "styleName": STYLE,
            "uniqueFontIdentifier": f"{ps};{version}",
            "fullName": full,
            "version": f"Version {version}",
            "psName": ps,
            "description": NERD_DESC,
            "typographicFamily": FAMILY,
            "typographicSubfamily": STYLE,
        }
    )
    fb.setupOS2(
        version=4,  # needed for USE_TYPO_METRICS in fsSelection
        fsType=0,
        fsSelection=0x80 | 0x40,  # USE_TYPO_METRICS | REGULAR
        achVendID=base_os2.achVendID,
        usWeightClass=base_os2.usWeightClass,
        xAvgCharWidth=CELL,
        sTypoAscender=asc,
        sTypoDescender=desc,
        sTypoLineGap=0,
        usWinAscent=asc,
        usWinDescent=-desc,
        sxHeight=base_os2.sxHeight,
        sCapHeight=base_os2.sCapHeight,
        usDefaultChar=0,
        usBreakChar=0x20,
    )
    os2 = fb.font["OS/2"]
    os2.panose.bProportion = 9  # monospaced
    os2.usFirstCharIndex = min(min(cmap), 0xFFFF)
    os2.usLastCharIndex = min(max(cmap), 0xFFFF)
    os2.recalcUnicodeRanges(fb.font)
    os2.recalcCodePageRanges(fb.font)
    fb.setupPost(isFixedPitch=1)
    return ps, full


def _build_ttf(path: Path, base, *, version, order, cmap, metrics, outlines) -> None:
    fb = FontBuilder(UPM, isTTF=True)
    _common_tables(fb, base, version=version, order=order, cmap=cmap, metrics=metrics)
    glyphs = {}
    for name in order:
        pen = TTGlyphPen(None)
        _replay(outlines[name], pen)
        glyphs[name] = pen.glyph()
    fb.setupGlyf(glyphs)
    fb.save(path)


class _CubicPen(BasePen):
    """Turn quadratic TrueType segments into rounded cubic curves.

    Reversing quadratic contours directly with ReverseContourPen mangles
    implied on-curve points, so convert first and reverse the cubics.
    """

    def __init__(self):
        super().__init__(None)
        self.value: list = []

    def _moveTo(self, p):
        self.value.append(("moveTo", (p,)))

    def _lineTo(self, p):
        self.value.append(("lineTo", (p,)))

    def _curveToOne(self, p1, p2, p3):
        self.value.append(("curveTo", (p1, p2, p3)))

    def _closePath(self):
        self.value.append(("closePath", ()))

    def _endPath(self):
        self.value.append(("endPath", ()))


def _build_otf(path: Path, base, *, version, order, cmap, metrics, outlines) -> None:
    fb = FontBuilder(UPM, isTTF=False)
    ps, full = _common_tables(
        fb, base, version=version, order=order, cmap=cmap, metrics=metrics
    )
    charstrings = {}
    for name in order:
        cubic = _CubicPen()
        _replay(outlines[name], cubic)
        pen = T2CharStringPen(CELL, None)
        # TrueType outer contours run clockwise; CFF wants counter-clockwise.
        _replay(cubic.value, ReverseContourPen(pen))
        charstrings[name] = pen.getCharString()
    fb.setupCFF(
        ps,
        {"FamilyName": FAMILY, "Weight": STYLE, "FullName": full},
        charstrings,
        {},
    )
    fb.font["CFF "].cff.topDictIndex[0].isFixedPitch = True
    fb.save(path)


def _css(stem: str) -> str:
    return (
        f"/* {FAMILY} {STYLE} - generated by tools/nerd_mono.py */\n"
        "@font-face {\n"
        f'  font-family: "{FAMILY}";\n'
        f'  src: url("{quote(stem + ".woff2")}") format("woff2"),\n'
        f'       url("{quote(stem + ".woff")}") format("woff"),\n'
        f'       url("{quote(stem + ".ttf")}") format("truetype");\n'
        "  font-display: swap;\n"
        "}\n"
        "\n"
        "/* Usage example:\n"
        f'body {{\n  font-family: "{FAMILY}", monospace;\n}}\n'
        "*/\n"
    )


def build(base_path: Path, symbols_path: Path, out_dir: Path, version: str | None) -> dict[str, Path]:
    base = TTFont(base_path)
    symbols = TTFont(symbols_path)
    version = version or _default_version(base)
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"--version must look like 0.4.0, got {version!r}")

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = PS_NAME
    order, cmap, outlines = _collect(base, symbols)
    metrics = _metrics(order, outlines)
    kw = dict(version=version, order=order, cmap=cmap, metrics=metrics, outlines=outlines)

    paths = {
        "ttf": out_dir / f"{stem}.ttf",
        "otf": out_dir / f"{stem}.otf",
        "woff2": out_dir / f"{stem}.woff2",
        "woff": out_dir / f"{stem}.woff",
        "css": out_dir / f"{FAMILY}.css",
        "license": out_dir / "LICENSE-NerdFonts",
    }
    _build_ttf(paths["ttf"], base, **kw)
    _build_otf(paths["otf"], base, **kw)
    for flavor in ("woff2", "woff"):
        font = TTFont(paths["ttf"])
        font.flavor = flavor
        font.save(paths[flavor])
        font.close()
    paths["css"].write_text(_css(stem), encoding="utf-8")
    lic = symbols_path.with_name("LICENSE")
    shutil.copyfile(lic, paths["license"])
    print(f"{FAMILY} {version}: {len(order)} glyphs, {len(cmap)} codepoints")
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", default=DEFAULT_BASE, help="AnnaHand TTF")
    ap.add_argument("--symbols", default=DEFAULT_SYMBOLS, help="SymbolsNerdFontMono TTF")
    ap.add_argument("--out", default=DEFAULT_OUT, help="output directory")
    ap.add_argument("--version", default=None, help="e.g. 0.4.0 (default: from base head)")
    args = ap.parse_args()
    paths = build(Path(args.base), Path(args.symbols), Path(args.out), args.version)
    for key, p in paths.items():
        print(f"  {key:6} {p} {p.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
