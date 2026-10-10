"""End-to-end: printed template -> simulated handwriting -> phone photo -> font.

The "handwriting" is a system sans font drawn into the template's cells at the
template's own baseline, then warped, tilted, lit unevenly and JPEG-compressed
like a phone photo. The resulting font must keep the geometry the layout
promises: descenders below the baseline, caps on the cap line, x-height below
caps, and counters (holes) preserved.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from handfont import cli, layout
from handfont.template import render_page

DPI = 150
WRITE = "ABOabgjpy0?"
FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)


def _find_font() -> str | None:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _handwriting_font() -> ImageFont.FreeTypeFont:
    path = _find_font()
    if path is None:
        pytest.skip("no system sans font available for simulated handwriting")
    cap_mm = (layout.BASELINE_FRAC - layout.CAP_FRAC) * layout.CELL_H_MM
    cap_px = layout.mm_to_px(cap_mm, DPI)
    # Cap height of Arial/DejaVu is ~0.72 em.
    return ImageFont.truetype(path, size=cap_px / 0.72)


def _phone_photo(img: Image.Image, rng: np.random.Generator) -> np.ndarray:
    """Rotate ~5 deg, perspective-warp a few %, pad onto grey, light gradient, JPEG-ready."""
    page = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
    h, w = page.shape[:2]

    # Paste the page on a 1.3x larger grey (128) canvas, roughly centred.
    # Transform the canvas (not the bare page) so nothing is clipped off.
    cw, ch = int(w * 1.3), int(h * 1.3)
    canvas = np.full((ch, cw, 3), 128, np.uint8)
    x0, y0 = (cw - w) // 2, (ch - h) // 2
    canvas[y0 : y0 + h, x0 : x0 + w] = page
    grey = (128, 128, 128)

    # Rotate ~5 deg about the canvas centre.
    m = cv2.getRotationMatrix2D((cw / 2, ch / 2), 5.0, 1.0)
    arr = cv2.warpAffine(canvas, m, (cw, ch), borderValue=grey)

    # Perspective: move each corner by up to 3% of the canvas size.
    src = np.float32([[0, 0], [cw, 0], [cw, ch], [0, ch]])
    jitter = rng.uniform(-0.03, 0.03, size=(4, 2)).astype(np.float32) * np.float32([cw, ch])
    arr = cv2.warpPerspective(arr, cv2.getPerspectiveTransform(src, src + jitter), (cw, ch), borderValue=grey)

    # Uneven lighting: horizontal multiply 0.75 (left) -> 1.0 (right).
    gain = np.linspace(0.75, 1.0, cw, dtype=np.float32)[None, :, None]
    lit = np.clip(arr.astype(np.float32) * gain, 0, 255).astype(np.uint8)
    return lit


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Run the whole pipeline once; the tests below inspect its output."""
    base = tmp_path_factory.mktemp("e2e")
    font = _handwriting_font()
    scans = base / "scans"
    scans.mkdir()
    rng = np.random.default_rng(0)

    for p in range(layout.page_count()):
        img = render_page(p, dpi=DPI)
        draw = ImageDraw.Draw(img)
        for cell in layout.cells(p):
            if cell.char not in WRITE:
                continue
            draw.text(
                (layout.mm_to_px(cell.rect.x + 4, DPI), layout.mm_to_px(cell.baseline_y, DPI)),
                cell.char,
                font=font,
                fill=(0, 0, 0),
                anchor="ls",
            )
        if p == 0:
            photo = _phone_photo(img, rng)
            cv2.imwrite(str(scans / f"page{p}.jpg"), photo, [cv2.IMWRITE_JPEG_QUALITY, 85])
        else:
            img.save(scans / f"page{p}.png")

    out = base / "out"
    rc = cli.main(["build", str(scans), "--family", "Test Hand", "-o", str(out)])
    assert rc == 0
    return out


@pytest.fixture(scope="module")
def glyphs(built):
    ttf = next(built.glob("*.ttf"))
    font = TTFont(ttf)
    cmap = font.getBestCmap()
    gs = font.getGlyphSet()
    for c in WRITE:
        assert ord(c) in cmap, f"{c!r} missing from cmap"

    def bounds(ch: str):
        pen = BoundsPen(gs)
        gs[cmap[ord(ch)]].draw(pen)
        assert pen.bounds is not None, f"{ch!r} has no outline"
        return pen.bounds  # (xMin, yMin, xMax, yMax)

    return bounds, gs, cmap


def test_e2e_pipeline_geometry(built, glyphs):
    bounds, _, _ = glyphs
    print()
    for ch in "ABagy":
        print(f"bounds {ch!r}: {bounds(ch)}")

    for c in "gjpy":
        assert bounds(c)[1] < -50, f"{c!r} descender yMin={bounds(c)[1]}"

    for c in "AB":
        _, yMin, _, yMax = bounds(c)
        assert -40 <= yMin <= 40, f"{c!r} yMin={yMin}"
        assert 500 <= yMax <= 900, f"{c!r} yMax={yMax}"

    assert bounds("a")[3] < bounds("A")[3] - 100, (
        f"x-height {bounds('a')[3]} not below cap {bounds('A')[3]}"
    )


def test_e2e_counter_kept(built, glyphs):
    _, gs, cmap = glyphs
    pen = RecordingPen()
    gs[cmap[ord("O")]].draw(pen)
    closes = sum(1 for op, _ in pen.value if op in ("closePath", "endPath"))
    assert closes >= 2, f"'O' has {closes} contour(s); expected outer + counter"


def test_e2e_outputs_exist(built):
    assert next(built.glob("*.otf"), None) is not None
    assert next(built.glob("*.woff2"), None) is not None
    assert next(built.glob("*.woff"), None) is not None
    assert next(built.glob("*.css"), None) is not None
    assert (built / "preview.png").exists()


def test_template_command_writes_pdf(tmp_path):
    out = tmp_path / "t.pdf"
    assert cli.main(["template", "-o", str(out)]) == 0
    assert out.exists()


def test_build_empty_dir_fails(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert cli.main(["build", str(empty)]) == 1
