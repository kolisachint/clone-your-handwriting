"""Trace a binary glyph bitmap into font-unit outlines with potrace.

Output contours use one representation for both TrueType and CFF builds::

    [('move', (x, y)),
     ('line', (x, y)),
     ('curve', ((c1x, c1y), (c2x, c2y), (x, y))),   # cubic bezier
     ...
     ('close', None)]

Coordinates are font units, y-up, origin on the baseline. Outer contours are
clockwise and holes counter-clockwise (the TrueType convention); the font
builder reverses them for CFF.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import potrace

from handfont import layout

Point = tuple[float, float]
Op = tuple[str, Any]
Contour = list[Op]


@dataclass
class VectorGlyph:
    char: str
    contours: list[Contour]
    advance: float  # font units


def _pt(p: Any) -> Point:
    """potracer points are objects with .x/.y (bitmap col/row)."""
    return (float(p.x), float(p.y))


def _signed_area(pts: list[Point]) -> float:
    """Shoelace area; > 0 is counter-clockwise in y-up coordinates."""
    s = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def _on_curve_points(contour: Contour) -> list[Point]:
    pts: list[Point] = []
    for op, arg in contour:
        if op in ("move", "line"):
            pts.append(arg)
        elif op == "curve":
            pts.append(arg[2])
    return pts


def _inside(pts: list[Point], p: Point) -> bool:
    """Even-odd ray test of p against polygon pts."""
    x, y = p
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


def _reverse(contour: Contour) -> Contour:
    """Reverse a closed contour's direction, keeping its shape."""
    start = contour[0][1]
    segs = []  # (kind, controls, end, begin)
    cur = start
    for op, arg in contour[1:]:
        if op == "line":
            segs.append(("line", None, arg, cur))
            cur = arg
        elif op == "curve":
            c1, c2, end = arg
            segs.append(("curve", (c1, c2), end, cur))
            cur = end
    out: Contour = [("move", cur)]
    for kind, ctrl, _end, begin in reversed(segs):
        if kind == "line":
            out.append(("line", begin))
        else:
            c1, c2 = ctrl
            out.append(("curve", (c2, c1, begin)))
    out.append(("close", None))
    return out


def _orient(contours: list[Contour]) -> list[Contour]:
    """Outer contours (even nesting depth) clockwise, holes counter-clockwise."""
    pts = [_on_curve_points(c) for c in contours]
    out = []
    for i, c in enumerate(contours):
        depth = sum(_inside(pts[j], pts[i][0]) for j in range(len(contours)) if j != i)
        is_hole = depth % 2 == 1
        area = _signed_area(pts[i])
        want_ccw = is_hole
        if (area > 0) != want_ccw:
            c = _reverse(c)
        out.append(c)
    return out


def _clean(contour: Contour) -> Contour:
    """Drop zero-length lines and a final line that only returns to the start."""
    out: Contour = [contour[0]]
    cur = contour[0][1]
    for op, arg in contour[1:]:
        if op == "line":
            if arg == cur:
                continue
            cur = arg
        elif op == "curve":
            cur = arg[2]
        out.append((op, arg))
    if len(out) > 2 and out[-1][0] == "line" and out[-1][1] == out[0][1]:
        out.pop()
    out.append(("close", None))
    return out


def trace(ink: np.ndarray, baseline_px: int, px_per_mm: float) -> tuple[list[Contour], tuple[float, float]]:
    """Trace a glyph bitmap into font-unit contours.

    `ink` is bool HxW, True = ink, row 0 = top. Returns the contours and
    (xmin, xmax) of the ink box in font units; xmin is SIDE_BEARING_UNITS.
    Blank ink returns ([], (0, 0)).
    """
    ink = np.asarray(ink, dtype=bool)
    cols = np.flatnonzero(ink.any(axis=0))
    if cols.size == 0:
        return [], (0.0, 0.0)

    left = int(cols[0])
    right = int(cols[-1]) + 1  # pixel edge
    scale = layout.UNITS_PER_MM / px_per_mm
    sb = float(layout.SIDE_BEARING_UNITS)

    def to_units(p: Point) -> Point:
        x, y = p
        return ((x - left) * scale + sb, (baseline_px - y) * scale)

    # potracer treats True in a bool array as background, so pass the inverse.
    # Specks below ~0.2 mm^2 are dropped.
    turdsize = max(2, int(0.2 * px_per_mm * px_per_mm))
    path = potrace.Bitmap(~ink).trace(
        turdsize=turdsize,
        alphamax=1.0,
        opticurve=True,
        opttolerance=0.2,
    )

    contours: list[Contour] = []
    for curve in path.curves:
        cur = to_units(_pt(curve.start_point))
        ops: Contour = [("move", cur)]
        for seg in curve.segments:
            end = to_units(_pt(seg.end_point))
            if seg.is_corner:
                corner = to_units(_pt(seg.c))
                ops.append(("line", corner))
                ops.append(("line", end))
            else:
                c1 = to_units(_pt(seg.c1))
                c2 = to_units(_pt(seg.c2))
                ops.append(("curve", (c1, c2, end)))
            cur = end
        contours.append(ops)

    contours = [_clean(c) for c in _orient(contours)]
    xmax = sb + (right - left) * scale
    return contours, (sb, xmax)


def trace_glyph(g: Any) -> VectorGlyph:
    """Trace a GlyphBitmap-like object (char, ink, baseline_px, px_per_mm)."""
    contours, (_xmin, xmax) = trace(g.ink, g.baseline_px, g.px_per_mm)
    if not contours:
        advance = float(layout.SPACE_ADVANCE_UNITS)
    else:
        advance = xmax + layout.SIDE_BEARING_UNITS  # ink width + 2 * side bearing
    return VectorGlyph(char=g.char, contours=contours, advance=advance)
