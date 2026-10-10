"""Photo or scan of a filled template -> per-character binary ink bitmaps.

Pipeline: find the four ArUco corner markers of one page, warp that page to a
flat image at ``dpi``, flatten the lighting, threshold dark ink, drop specks,
then crop each cell's writing area. Geometry comes only from ``layout``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from . import layout

#: Background-estimate kernel in mm. Must be wider than the widest pen stroke.
BG_KERNEL_MM = 9.0
#: Normalised grey (paper = 255) below this counts as ink. Guide colour sits above it.
INK_THRESHOLD = 110
#: Ink specks smaller than this (in mm, squared, times 4) are dropped.
SPECK_MM = 0.25
#: Cells with fewer ink pixels than this are treated as empty.
MIN_CELL_INK_PX = 20
#: RANSAC reprojection tolerance, in rectified pixels.
_RANSAC_PX = 5.0


@dataclass
class GlyphBitmap:
    char: str
    ink: np.ndarray  # bool, H x W, True = ink, cropped to the cell's writing_rect
    baseline_px: int  # row index of the baseline within `ink`
    px_per_mm: float


def load_image(path: str | Path) -> np.ndarray:
    """Read a PNG/JPEG/TIFF photo or scan as BGR. Unicode-safe on macOS."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"no image file at {p}")
    data = np.fromfile(str(p), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"could not decode {p} as an image (expected PNG, JPEG or TIFF)")
    return img


def _to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _detect_markers(gray: np.ndarray) -> dict[int, np.ndarray]:
    """Map marker id -> its 4 image corners (TL, TR, BR, BL of the marker)."""
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, layout.ARUCO_DICT))
    detector = cv2.aruco.ArucoDetector(
        dictionary, cv2.aruco.DetectorParameters(), cv2.aruco.RefineParameters()
    )
    corners, ids, _ = detector.detectMarkers(gray)
    found: dict[int, np.ndarray] = {}
    if ids is not None:
        for quad, mid in zip(corners, ids.ravel()):
            found[int(mid)] = quad.reshape(4, 2).astype(np.float32)
    return found


def rectify(image_bgr: np.ndarray, dpi: int = layout.DPI) -> tuple[int, np.ndarray]:
    """Warp the photographed page to a flat grayscale image.

    Returns (page index, uint8 image of size ``layout.page_px(dpi)``).
    Needs at least 3 of the 4 markers of one page; uses all their corners.
    """
    gray = _to_gray(image_bgr)
    found = _detect_markers(gray)

    best_page, best_ids = None, []
    for page in range(layout.page_count()):
        hit = [m for m in layout.marker_ids(page) if m in found]
        if len(hit) >= 3 and len(hit) > len(best_ids):
            best_page, best_ids = page, hit
    if best_page is None:
        raise ValueError(
            f"found markers {sorted(found)}; need 3+ corner squares of one page "
            "— make sure all four corners are in the photo"
        )

    ppm = dpi / 25.4
    rects = layout.marker_rects()
    src, dst = [], []
    for k, mid in enumerate(layout.marker_ids(best_page)):
        if mid not in found:
            continue
        r = rects[k]
        quad_mm = np.array(
            [(r.x, r.y), (r.x + r.w, r.y), (r.x + r.w, r.y + r.h), (r.x, r.y + r.h)],
            dtype=np.float32,
        )
        src.append(found[mid])
        dst.append(quad_mm * ppm)

    H, _ = cv2.findHomography(np.vstack(src), np.vstack(dst), cv2.RANSAC, _RANSAC_PX)
    if H is None:
        raise ValueError("could not fit a page transform to the markers; try a sharper, flatter photo")

    out_w, out_h = layout.page_px(dpi)
    flat = cv2.warpPerspective(
        gray,
        H,
        (out_w, out_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )
    return best_page, flat


def binarize(gray: np.ndarray) -> np.ndarray:
    """Flat-page grayscale -> bool mask, True = ink. Lighting- and speck-tolerant."""
    g = _to_gray(gray)
    px_per_mm = g.shape[1] / layout.PAGE_W_MM

    # Paper brightness estimate on a small copy (fast, and wider than any stroke).
    small_ppm = min(px_per_mm, 2.0)
    scale = small_ppm / px_per_mm
    small = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    k = int(round(BG_KERNEL_MM * small_ppm)) | 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    bg_small = cv2.morphologyEx(small, cv2.MORPH_CLOSE, kernel)
    bg = cv2.resize(bg_small, (g.shape[1], g.shape[0]), interpolation=cv2.INTER_LINEAR)

    norm = np.clip(g.astype(np.float32) * (255.0 / np.maximum(bg, 1).astype(np.float32)), 0, 255)
    ink = norm < INK_THRESHOLD

    # Drop specks: tiny connected blobs are dust, not handwriting.
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8), connectivity=8)
    min_area = (SPECK_MM * px_per_mm) ** 2 * 4
    keep = stats[:, cv2.CC_STAT_AREA] >= min_area
    keep[0] = False
    return keep[labels]


def _extract_page(image_bgr: np.ndarray, dpi: int) -> tuple[int, dict[str, GlyphBitmap]]:
    page, flat = rectify(image_bgr, dpi)

    # Marker squares overlap the bottom-corner cells' writing area by a few mm.
    # Paint them white so their black squares are never read as ink.
    for r in layout.marker_rects():
        flat[layout.mm_to_px(r.y, dpi) : layout.mm_to_px(r.y + r.h, dpi),
             layout.mm_to_px(r.x, dpi) : layout.mm_to_px(r.x + r.w, dpi)] = 255

    ink = binarize(flat)
    ppm = dpi / 25.4
    glyphs: dict[str, GlyphBitmap] = {}
    for cell in layout.cells(page):
        wr = cell.writing_rect()
        x0, x1 = layout.mm_to_px(wr.x, dpi), layout.mm_to_px(wr.x + wr.w, dpi)
        y0, y1 = layout.mm_to_px(wr.y, dpi), layout.mm_to_px(wr.y + wr.h, dpi)
        crop = ink[y0:y1, x0:x1]
        if int(np.count_nonzero(crop)) < MIN_CELL_INK_PX:
            continue
        baseline_px = layout.mm_to_px(cell.baseline_y, dpi) - y0
        glyphs[cell.char] = GlyphBitmap(cell.char, crop.copy(), baseline_px, ppm)
    return page, glyphs


def extract_glyphs(image_bgr: np.ndarray, dpi: int = layout.DPI) -> dict[str, GlyphBitmap]:
    """One scanned/photographed page -> {char: GlyphBitmap}. Empty cells are absent."""
    return _extract_page(image_bgr, dpi)[1]


def extract_from_files(paths, dpi: int = layout.DPI) -> dict[str, GlyphBitmap]:
    """Several page images -> one merged dict. A repeated page: the later file wins."""
    by_page: dict[int, dict[str, GlyphBitmap]] = {}
    for path in paths:
        page, glyphs = _extract_page(load_image(path), dpi)
        by_page[page] = glyphs
    merged: dict[str, GlyphBitmap] = {}
    for page in sorted(by_page):
        merged.update(by_page[page])
    return merged
