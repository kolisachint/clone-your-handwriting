"""Single source of truth for the handwriting template geometry.

The template generator draws exactly this, and the scan reader crops exactly
this. All coordinates are millimetres from the page's top-left corner.

Page anatomy (A4 portrait, 210 x 297 mm):

    [M0]                                   [M1]     <- ArUco markers
     title / page n of N / instructions
     +------+------+------+------+------+------+
     | A    | B    | C    | ...                  <- label in the cell's top strip
     |------ cap line (light) -------------|
     |------ x-height line (light) --------|
     |====== baseline (light) =============|
     |------ descender line (light) -------|
     +------+------+------+------+------+------+
    [M3]                                   [M2]

Guide lines and labels are printed in a light colour (GUIDE_RGB) so the
reader can drop them with a simple threshold; ink is assumed dark.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Characters --------------------------------------------------------------

UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWER = "abcdefghijklmnopqrstuvwxyz"
DIGITS = "0123456789"
PUNCT = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"

#: Every glyph the user writes, in template order. Space is generated, not written.
CHARSET: str = UPPER + LOWER + DIGITS + PUNCT  # 94 chars

# --- Page --------------------------------------------------------------------

PAGE_W_MM = 210.0
PAGE_H_MM = 297.0

#: ArUco dictionary name in cv2.aruco (e.g. cv2.aruco.DICT_4X4_50).
ARUCO_DICT = "DICT_4X4_50"
MARKER_MM = 14.0
MARKER_MARGIN_MM = 10.0  # from page edge to marker's outer edge

#: Pixel resolution used when rendering / rectifying a page.
DPI = 300

#: Light colour for guides and labels (R, G, B 0-255). Must stay well above
#: the reader's ink threshold in grayscale.
GUIDE_RGB = (150, 200, 235)

# --- Grid --------------------------------------------------------------------

COLS = 7
ROWS = 7
CELLS_PER_PAGE = COLS * ROWS  # 49 -> 2 pages for 94 chars

GRID_LEFT_MM = 15.0
GRID_TOP_MM = 42.0
GRID_W_MM = PAGE_W_MM - 2 * GRID_LEFT_MM  # 180
CELL_W_MM = GRID_W_MM / COLS  # ~25.7
CELL_H_MM = 32.0  # 7 rows * 32 = 224 -> grid ends at 266 mm, clear of the bottom markers (273 mm)

#: Top strip of each cell holding the printed label (not part of the glyph).
LABEL_H_MM = 6.0

# Guide lines, as a fraction of the cell height measured from the cell top.
CAP_FRAC = 0.30
XHEIGHT_FRAC = 0.50
BASELINE_FRAC = 0.72
DESCENDER_FRAC = 0.92

#: Inset applied when cropping a cell so the printed border is not read as ink.
CROP_INSET_MM = 1.2

# --- Font metrics ------------------------------------------------------------

UNITS_PER_EM = 1000
#: Font units per millimetre of cell: cap height (baseline - cap line) maps to 700 units.
CAP_HEIGHT_UNITS = 700
UNITS_PER_MM = CAP_HEIGHT_UNITS / ((BASELINE_FRAC - CAP_FRAC) * CELL_H_MM)
X_HEIGHT_UNITS = round((BASELINE_FRAC - XHEIGHT_FRAC) * CELL_H_MM * UNITS_PER_MM)
ASCENDER_UNITS = round((BASELINE_FRAC - LABEL_H_MM / CELL_H_MM) * CELL_H_MM * UNITS_PER_MM)
DESCENDER_UNITS = -round((1.0 - BASELINE_FRAC) * CELL_H_MM * UNITS_PER_MM)
#: Side bearing added left and right of every glyph's ink box.
SIDE_BEARING_UNITS = 60
SPACE_ADVANCE_UNITS = 300


@dataclass(frozen=True)
class Rect:
    x: float  # mm, left
    y: float  # mm, top
    w: float
    h: float


@dataclass(frozen=True)
class Cell:
    char: str
    page: int  # 0-based
    row: int
    col: int
    rect: Rect  # whole cell, mm

    @property
    def baseline_y(self) -> float:
        return self.rect.y + BASELINE_FRAC * self.rect.h

    def writing_rect(self) -> Rect:
        """Area where ink belongs: below the label strip, inside the border."""
        r = self.rect
        top = r.y + LABEL_H_MM
        return Rect(r.x + CROP_INSET_MM, top, r.w - 2 * CROP_INSET_MM, r.y + r.h - CROP_INSET_MM - top)


def page_count(charset: str = CHARSET) -> int:
    return -(-len(charset) // CELLS_PER_PAGE)


def cells(page: int, charset: str = CHARSET) -> list[Cell]:
    """Cells on one page, row-major."""
    chunk = charset[page * CELLS_PER_PAGE : (page + 1) * CELLS_PER_PAGE]
    out = []
    for i, ch in enumerate(chunk):
        row, col = divmod(i, COLS)
        rect = Rect(GRID_LEFT_MM + col * CELL_W_MM, GRID_TOP_MM + row * CELL_H_MM, CELL_W_MM, CELL_H_MM)
        out.append(Cell(ch, page, row, col, rect))
    return out


def all_cells(charset: str = CHARSET) -> list[Cell]:
    return [c for p in range(page_count(charset)) for c in cells(p, charset)]


def marker_ids(page: int) -> tuple[int, int, int, int]:
    """ArUco ids for (top-left, top-right, bottom-right, bottom-left) on `page`.

    Unique per page, so the reader knows which page a scan is without OCR.
    """
    b = page * 4
    return (b, b + 1, b + 2, b + 3)


def marker_rects() -> tuple[Rect, Rect, Rect, Rect]:
    """Marker squares, mm, in (TL, TR, BR, BL) order."""
    m, s = MARKER_MARGIN_MM, MARKER_MM
    return (
        Rect(m, m, s, s),
        Rect(PAGE_W_MM - m - s, m, s, s),
        Rect(PAGE_W_MM - m - s, PAGE_H_MM - m - s, s, s),
        Rect(m, PAGE_H_MM - m - s, s, s),
    )


def mm_to_px(mm: float, dpi: int = DPI) -> int:
    return round(mm / 25.4 * dpi)


def page_px(dpi: int = DPI) -> tuple[int, int]:
    """(width, height) of a rectified page in pixels."""
    return mm_to_px(PAGE_W_MM, dpi), mm_to_px(PAGE_H_MM, dpi)
