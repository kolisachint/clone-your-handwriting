"""Tests for handfont.scan using a synthetic page (no template.py needed)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from handfont import layout, scan

DPI = 150
ARUCO = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, layout.ARUCO_DICT))
GUIDE_BGR = tuple(int(v) for v in reversed(layout.GUIDE_RGB))
INK_CHARS = ("A", "B", "K", "g")  # all on page 0


def _px(mm: float) -> int:
    return layout.mm_to_px(mm, DPI)


def _draw_markers(img: np.ndarray, ids) -> None:
    for rect, mid in zip(layout.marker_rects(), ids):
        side = _px(rect.w)
        marker = cv2.aruco.generateImageMarker(ARUCO, mid, side, borderBits=1)
        x, y = _px(rect.x), _px(rect.y)
        img[y : y + side, x : x + side] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)


def _synthetic_page(page: int = 0, ink: str = "".join(INK_CHARS), marker_ids=None) -> np.ndarray:
    """White page with markers, light guides and labels, and dark strokes in some cells."""
    w, h = layout.page_px(DPI)
    img = np.full((h, w, 3), 255, np.uint8)
    if marker_ids is None:
        marker_ids = layout.marker_ids(page)
    _draw_markers(img, marker_ids)

    for cell in layout.cells(page):
        r = cell.rect
        x0, y0 = _px(r.x), _px(r.y)
        x1, y1 = _px(r.x + r.w), _px(r.y + r.h)
        cv2.rectangle(img, (x0, y0), (x1, y1), GUIDE_BGR, 2)
        for frac in (layout.CAP_FRAC, layout.XHEIGHT_FRAC, layout.BASELINE_FRAC, layout.DESCENDER_FRAC):
            y = _px(r.y + frac * r.h)
            cv2.line(img, (x0, y), (x1, y), GUIDE_BGR, 2)
        cv2.putText(img, cell.char, (x0 + _px(1), y0 + _px(4.5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, GUIDE_BGR, 2, cv2.LINE_AA)

    for cell in layout.cells(page):
        if cell.char in ink:
            wr = cell.writing_rect()
            cv2.putText(img, cell.char, (_px(wr.x + 3), _px(cell.baseline_y)),
                        cv2.FONT_HERSHEY_SIMPLEX, 3.0, (0, 0, 0), 8, cv2.LINE_AA)

    # Markers last: the bottom pair overlaps the bottom row's cell borders.
    _draw_markers(img, marker_ids)
    return img


def _phone_photo(clean: np.ndarray) -> np.ndarray:
    """Rotate ~8 deg, skew, shrink onto a larger grey canvas, add a brightness gradient."""
    h, w = clean.shape[:2]
    cw, ch = int(w * 1.25), int(h * 1.2)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    c = np.array([w / 2, h / 2])
    th = np.deg2rad(8)
    rot = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    dst = (src - c) @ rot.T * 0.85 + np.array([cw / 2, ch / 2])
    dst[1] += [-25, 35]
    dst[2] += [-40, -20]
    H = cv2.getPerspectiveTransform(src, dst.astype(np.float32))
    warped = cv2.warpPerspective(clean, H, (cw, ch), borderValue=(120, 120, 120))
    yy, xx = np.mgrid[0:ch, 0:cw].astype(np.float32)
    shade = 0.55 + 0.45 * (xx / cw) * (0.8 + 0.2 * yy / ch)
    return np.clip(warped.astype(np.float32) * shade[..., None], 0, 255).astype(np.uint8)


def test_direct_extraction_finds_inked_cells_only():
    glyphs = scan.extract_glyphs(_synthetic_page(), dpi=DPI)

    assert set(glyphs) == set(INK_CHARS)
    for ch, g in glyphs.items():
        assert g.ink.dtype == bool
        assert g.ink.any()
        assert g.px_per_mm == pytest.approx(DPI / 25.4)
        assert 0 <= g.baseline_px < g.ink.shape[0]
    # Caps sit on the baseline: lowest ink row is just below it (stroke half-width).
    for ch in ("A", "B", "K"):
        rows = np.where(glyphs[ch].ink.any(axis=1))[0]
        assert abs(rows.max() - glyphs[ch].baseline_px) <= 6


def test_photo_with_rotation_perspective_and_shading_still_extracts():
    clean = _synthetic_page()
    photo = _phone_photo(clean)

    clean_glyphs = scan.extract_glyphs(clean, dpi=DPI)
    photo_glyphs = scan.extract_glyphs(photo, dpi=DPI)

    assert set(photo_glyphs) == set(clean_glyphs) == set(INK_CHARS)
    for ch in INK_CHARS:
        a_clean = int(clean_glyphs[ch].ink.sum())
        a_photo = int(photo_glyphs[ch].ink.sum())
        assert abs(a_photo - a_clean) / a_clean < 0.30, ch


def test_page_one_markers_return_page_one():
    img = _synthetic_page(page=1, ink="", marker_ids=layout.marker_ids(1))
    page, gray = scan.rectify(img, dpi=DPI)
    assert page == 1
    assert gray.dtype == np.uint8
    assert gray.shape == (layout.page_px(DPI)[1], layout.page_px(DPI)[0])


def test_no_markers_raises_value_error():
    w, h = layout.page_px(DPI)
    blank = np.full((h, w, 3), 200, np.uint8)
    with pytest.raises(ValueError, match="need 3\\+ corner squares"):
        scan.rectify(blank, dpi=DPI)


def test_two_markers_only_raises_value_error():
    w, h = layout.page_px(DPI)
    img = np.full((h, w, 3), 255, np.uint8)
    ids = layout.marker_ids(0)
    for rect, mid in zip(layout.marker_rects()[:2], ids[:2]):
        side = _px(rect.w)
        marker = cv2.aruco.generateImageMarker(ARUCO, mid, side, borderBits=1)
        img[_px(rect.y) : _px(rect.y) + side, _px(rect.x) : _px(rect.x) + side] = cv2.cvtColor(
            marker, cv2.COLOR_GRAY2BGR
        )
    with pytest.raises(ValueError, match="need 3\\+ corner squares"):
        scan.rectify(img, dpi=DPI)


def test_load_image_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        scan.load_image(tmp_path / "nope.png")
