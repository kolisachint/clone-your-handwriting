from __future__ import annotations

import cv2
import numpy as np
import pytest

from handfont import layout, template


@pytest.fixture(scope="module")
def pages():
    return [template.render_page(p) for p in range(layout.page_count())]


def _gray(img) -> np.ndarray:
    return np.asarray(img.convert("L"))


def test_page_size_matches_layout(pages):
    for img in pages:
        assert img.mode == "RGB"
        assert img.size == layout.page_px()


def test_page_count_matches_layout(pages):
    assert len(pages) == layout.page_count() == 2


@pytest.mark.parametrize("page", [0, 1])
def test_markers_detectable_with_expected_ids(pages, page):
    gray = _gray(pages[page])
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, layout.ARUCO_DICT))
    detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(gray)
    assert ids is not None
    found = sorted(int(i) for i in ids.ravel())
    assert found == sorted(layout.marker_ids(page))


@pytest.mark.parametrize("page", [0, 1])
def test_markers_sit_at_their_corners_in_tl_tr_br_bl_order(pages, page):
    gray = _gray(pages[page])
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, layout.ARUCO_DICT))
    detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(gray)
    by_id = {int(i): c.reshape(4, 2).mean(axis=0) for c, i in zip(corners, ids.ravel())}
    for marker_id, rect in zip(layout.marker_ids(page), layout.marker_rects()):
        cx = layout.mm_to_px(rect.x + rect.w / 2)
        cy = layout.mm_to_px(rect.y + rect.h / 2)
        assert np.hypot(*(by_id[marker_id] - np.array([cx, cy]))) < 5


def test_pdf_written_and_non_empty(tmp_path):
    out = tmp_path / "template.pdf"
    template.write_pdf(out)
    assert out.is_file()
    data = out.read_bytes()
    assert len(data) > 0
    assert data.startswith(b"%PDF")
    assert data.count(b"/Type /Page\n") + data.count(b"/Type /Page ") + data.count(b"/Type/Page") >= layout.page_count()


def test_pngs_written(tmp_path):
    paths = template.write_pngs(tmp_path / "pngs")
    assert [p.name for p in paths] == [f"page-{i}.png" for i in range(1, layout.page_count() + 1)]
    assert all(p.stat().st_size > 0 for p in paths)


@pytest.mark.parametrize("page", [0, 1])
def test_writing_rects_contain_no_ink(pages, page):
    gray = _gray(pages[page])
    dpi = layout.DPI
    for cell in layout.cells(page):
        wr = cell.writing_rect()
        x0 = layout.mm_to_px(wr.x, dpi)
        y0 = layout.mm_to_px(wr.y, dpi)
        x1 = layout.mm_to_px(wr.x + wr.w, dpi)
        y1 = layout.mm_to_px(wr.y + wr.h, dpi)
        region = gray[y0:y1, x0:x1]
        assert region.size > 0
        assert region.min() >= 150, f"darker than guide in cell {cell.char!r}: min={region.min()}"
