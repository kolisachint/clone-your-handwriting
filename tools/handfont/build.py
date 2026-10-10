"""Assemble traced glyphs into OTF, TTF, WOFF2, WOFF and a CSS @font-face."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

from fontTools import agl
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.roundTools import otRound
from fontTools.pens.boundsPen import ControlBoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from handfont import layout
from handfont.vectorize import VectorGlyph

_NOTDEF = ".notdef"
_SPACE_CP = 0x20
_NBSP_CP = 0x00A0
_CU2QU_MAX_ERR = 1.0
_VENDOR = "HFNT"


def _glyph_name(cp: int) -> str:
    if cp == _SPACE_CP:
        return "space"
    if cp == _NBSP_CP:
        return "nbspace"
    return agl.UV2AGL.get(cp, f"uni{cp:04X}")


def _ipt(p) -> tuple[int, int]:
    return (otRound(p[0]), otRound(p[1]))


def _replay(contours, pen) -> None:
    """Feed vector ops into any fontTools pen, rounding to integer units."""
    for contour in contours:
        for op, arg in contour:
            if op == "move":
                pen.moveTo(_ipt(arg))
            elif op == "line":
                pen.lineTo(_ipt(arg))
            elif op == "curve":
                c1, c2, end = arg
                pen.curveTo(_ipt(c1), _ipt(c2), _ipt(end))
            elif op == "close":
                pen.closePath()


def _bounds(contours) -> tuple[float, float, float, float] | None:
    pen = ControlBoundsPen(None)
    _replay(contours, pen)
    return pen.bounds


def _css_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _ps_name(family: str, style: str) -> str:
    base = re.sub(r"[^A-Za-z0-9-]", "", family) or "HandFont"
    return f"{base}-{re.sub(r'[^A-Za-z0-9-]', '', style) or 'Regular'}"


def _version_revision(version: str) -> float:
    try:
        return float(".".join(version.split(".")[:2]))
    except ValueError:
        return 1.0


def _layout_glyphs(glyphs: list[VectorGlyph]):
    """Return (glyph_order, cmap, outlines) with .notdef, space and nbsp first."""
    order = [_NOTDEF]
    cmap: dict[int, str] = {}
    outlines: dict[str, tuple[list, float]] = {
        _NOTDEF: ([], float(layout.SPACE_ADVANCE_UNITS)),
    }

    def add_blank(cp: int) -> None:
        name = _glyph_name(cp)
        order.append(name)
        cmap[cp] = name
        outlines[name] = ([], float(layout.SPACE_ADVANCE_UNITS))

    add_blank(_SPACE_CP)
    add_blank(_NBSP_CP)

    for g in glyphs:
        if len(g.char) != 1:
            raise ValueError(f"glyph char must be one character, got {g.char!r}")
        cp = ord(g.char)
        if cp in cmap:
            continue  # first occurrence wins
        name = _glyph_name(cp)
        if name in outlines:
            name = f"{name}.{cp:04X}"
        order.append(name)
        cmap[cp] = name
        outlines[name] = (g.contours, float(g.advance))
    return order, cmap, outlines


def _metrics(order, outlines):
    """name -> (advance, lsb, xmax) with lsb/xmax from control box."""
    metrics = {}
    for name in order:
        contours, advance = outlines[name]
        box = _bounds(contours) if contours else None
        if box is None:
            metrics[name] = (advance, 0, 0)
        else:
            xmin, _ymin, xmax, _ymax = box
            metrics[name] = (advance, otRound(xmin), otRound(xmax))
    return metrics


def _common_tables(fb: FontBuilder, *, family, style, version, order, cmap, metrics, outlines):
    ps = _ps_name(family, style)
    asc = layout.ASCENDER_UNITS + 60
    desc = layout.DESCENDER_UNITS - 60

    fb.updateHead(fontRevision=_version_revision(version))
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupHorizontalMetrics({n: (adv, lsb) for n, (adv, lsb, _x) in metrics.items()})

    advances = [adv for adv, _l, _x in metrics.values()]
    lsbs = [lsb for _a, lsb, _x in metrics.values()]
    rsbs = [adv - xmax for adv, _l, xmax in metrics.values() if xmax]
    fb.setupHorizontalHeader(
        ascent=asc,
        descent=desc,
        lineGap=0,
        advanceWidthMax=max(advances),
        minLeftSideBearing=min(lsbs),
        minRightSideBearing=min(rsbs) if rsbs else 0,
        xMaxExtent=max((x for _a, _l, x in metrics.values()), default=0),
    )
    fb.setupNameTable(
        {
            "familyName": family,
            "styleName": style,
            "uniqueFontIdentifier": f"{ps};{version}",
            "fullName": f"{family} {style}",
            "version": f"Version {version}",
            "psName": ps,
        }
    )
    fb.setupOS2(
        version=4,  # needed for USE_TYPO_METRICS in fsSelection
        fsType=0,  # installable embedding
        fsSelection=0x80 | (0x40 if style == "Regular" else 0),  # USE_TYPO_METRICS (+REGULAR)
        achVendID=_VENDOR,
        sTypoAscender=asc,
        sTypoDescender=desc,
        sTypoLineGap=0,
        usWinAscent=asc,
        usWinDescent=-desc,
        sxHeight=layout.X_HEIGHT_UNITS,
        sCapHeight=layout.CAP_HEIGHT_UNITS,
        usDefaultChar=0,
        usBreakChar=_SPACE_CP,
    )
    fb.setupPost()
    return ps


def _build_otf(path: Path, *, family, style, version, order, cmap, metrics, outlines) -> None:
    fb = FontBuilder(layout.UNITS_PER_EM, isTTF=False)
    ps = _common_tables(
        fb, family=family, style=style, version=version, order=order, cmap=cmap,
        metrics=metrics, outlines=outlines,
    )
    charstrings = {}
    for name in order:
        contours, advance = outlines[name]
        pen = T2CharStringPen(advance, None)
        # TrueType convention is clockwise outers; CFF wants counter-clockwise.
        _replay(contours, ReverseContourPen(pen))
        charstrings[name] = pen.getCharString()
    fb.setupCFF(
        ps,
        {"FamilyName": family, "Weight": style, "FullName": f"{family} {style}"},
        charstrings,
        {},
    )
    fb.save(path)


def _build_ttf(path: Path, *, family, style, version, order, cmap, metrics, outlines) -> None:
    fb = FontBuilder(layout.UNITS_PER_EM, isTTF=True)
    _common_tables(
        fb, family=family, style=style, version=version, order=order, cmap=cmap,
        metrics=metrics, outlines=outlines,
    )
    glyphs = {}
    for name in order:
        contours, _advance = outlines[name]
        pen = TTGlyphPen(None)
        _replay(contours, Cu2QuPen(pen, max_err=_CU2QU_MAX_ERR, reverse_direction=False))
        glyphs[name] = pen.glyph()
    fb.setupGlyf(glyphs)
    fb.save(path)


def _css(family: str, stem: str, *, style: str) -> str:
    fam = _css_escape(family)
    return (
        f"/* {family} {style} - generated by handfont */\n"
        "@font-face {\n"
        f'  font-family: "{fam}";\n'
        f'  src: url("{quote(stem + ".woff2")}") format("woff2"),\n'
        f'       url("{quote(stem + ".woff")}") format("woff"),\n'
        f'       url("{quote(stem + ".ttf")}") format("truetype");\n'
        "  font-display: swap;\n"
        "}\n"
        "\n"
        "/* Usage example:\n"
        f'body {{\n  font-family: "{fam}", serif;\n}}\n'
        "*/\n"
    )


def build_font(
    glyphs: list[VectorGlyph],
    family: str,
    out_dir: Path,
    style: str = "Regular",
    version: str = "0.1.0",
) -> dict[str, Path]:
    """Write OTF, TTF, WOFF2, WOFF and a CSS file for `family` into `out_dir`.

    Returns a dict with keys "otf", "ttf", "woff2", "woff", "css".
    Characters from layout.CHARSET that are absent from `glyphs` are left out.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{family}-{style}"

    order, cmap, outlines = _layout_glyphs(glyphs)
    metrics = _metrics(order, outlines)
    kw = dict(family=family, style=style, version=version, order=order,
              cmap=cmap, metrics=metrics, outlines=outlines)

    paths = {
        "otf": out_dir / f"{stem}.otf",
        "ttf": out_dir / f"{stem}.ttf",
        "woff2": out_dir / f"{stem}.woff2",
        "woff": out_dir / f"{stem}.woff",
        "css": out_dir / f"{family}.css",
    }

    _build_otf(paths["otf"], **kw)
    _build_ttf(paths["ttf"], **kw)

    for flavor, key in (("woff2", "woff2"), ("woff", "woff")):
        font = TTFont(paths["ttf"])
        font.flavor = flavor
        font.save(paths[key])
        font.close()

    paths["css"].write_text(_css(family, stem, style=style), encoding="utf-8")
    return paths
