"""Render the printable handwriting template (A4, ArUco corners, guide boxes).

Everything geometric comes from :mod:`handfont.layout`. Guides and labels use
``layout.GUIDE_RGB``, which is light enough that the reader drops it as
non-ink, so the user's dark pen strokes are the only thing left.
"""

from __future__ import annotations

from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont

from handfont import layout

#: Header text colour (dark grey, so it reads as print, not as guide).
HEADER_RGB = (80, 80, 80)

TITLE = "handfont - handwriting sheet"  # ASCII: default font has no em dash
INSTRUCTIONS = (
    "Black/dark pen. One character per box. Sit letters on the darker baseline; "
    "tall letters reach the top line, x-height letters reach the middle line, "
    "descenders (g j p q y) go below.",
    "Keep inside the box. Scan or photograph flat, all 4 corner squares visible.",
)


def _font(px: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Scalable default font at ``px`` pixels; falls back to Pillow's bitmap font."""
    try:
        return ImageFont.load_default(size=px)
    except TypeError:  # Pillow < 10.1 has no size argument
        return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=font) > max_w:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _draw_markers(img: Image.Image, page: int, dpi: int) -> None:
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, layout.ARUCO_DICT))
    for marker_id, rect in zip(layout.marker_ids(page), layout.marker_rects()):
        side = layout.mm_to_px(rect.w, dpi)
        arr = cv2.aruco.generateImageMarker(dictionary, marker_id, side)
        img.paste(Image.fromarray(arr, mode="L"), (layout.mm_to_px(rect.x, dpi), layout.mm_to_px(rect.y, dpi)))


def _draw_header(draw: ImageDraw.ImageDraw, page: int, n_pages: int, dpi: int) -> None:
    # Keep clear of the markers (10..24 mm from each edge, plus a gap).
    left = layout.mm_to_px(27, dpi)
    right = layout.mm_to_px(layout.PAGE_W_MM - 27, dpi)
    max_w = right - left
    y = layout.mm_to_px(12, dpi)

    title_font = _font(layout.mm_to_px(4.2, dpi))
    body_font = _font(layout.mm_to_px(2.9, dpi))
    title_step = layout.mm_to_px(6.0, dpi)
    body_step = layout.mm_to_px(4.2, dpi)

    draw.text((left, y), TITLE, font=title_font, fill=HEADER_RGB)
    y += title_step

    draw.text((left, y), f"Page {page + 1} of {n_pages}", font=body_font, fill=HEADER_RGB)
    y += body_step

    for text in INSTRUCTIONS:
        for line in _wrap(draw, text, body_font, max_w):
            draw.text((left, y), line, font=body_font, fill=HEADER_RGB)
            y += body_step
        y += layout.mm_to_px(0.8, dpi)


def _draw_cell(draw: ImageDraw.ImageDraw, cell: layout.Cell, dpi: int, label_font) -> None:
    r = cell.rect
    x0 = layout.mm_to_px(r.x, dpi)
    y0 = layout.mm_to_px(r.y, dpi)
    x1 = layout.mm_to_px(r.x + r.w, dpi) - 1
    y1 = layout.mm_to_px(r.y + r.h, dpi) - 1
    guide = layout.GUIDE_RGB

    # Outer border.
    draw.rectangle([x0, y0, x1, y1], outline=guide, width=2)

    # Label in the top strip, then a light line under it.
    draw.text((x0 + layout.mm_to_px(1.0, dpi), y0 + layout.mm_to_px(0.8, dpi)), cell.char, font=label_font, fill=guide)
    strip_y = layout.mm_to_px(r.y + layout.LABEL_H_MM, dpi)
    draw.line([(x0 + 1, strip_y), (x1 - 1, strip_y)], fill=guide, width=1)

    # Typographic guide lines.
    for frac in (layout.CAP_FRAC, layout.XHEIGHT_FRAC, layout.DESCENDER_FRAC):
        y = layout.mm_to_px(r.y + frac * r.h, dpi)
        draw.line([(x0 + 1, y), (x1 - 1, y)], fill=guide, width=1)

    by = layout.mm_to_px(cell.baseline_y, dpi)
    draw.line([(x0 + 1, by - 1), (x1 - 1, by - 1)], fill=guide, width=3)


def render_page(page: int, dpi: int = layout.DPI, charset: str = layout.CHARSET) -> Image.Image:
    """Render 0-based ``page`` of the template as an RGB image at ``dpi``."""
    n_pages = layout.page_count(charset)
    if not 0 <= page < n_pages:
        raise ValueError(f"page {page} out of range (0..{n_pages - 1})")

    img = Image.new("RGB", layout.page_px(dpi), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    _draw_header(draw, page, n_pages, dpi)

    label_font = _font(layout.mm_to_px(layout.LABEL_H_MM * 0.75, dpi))
    for cell in layout.cells(page, charset):
        _draw_cell(draw, cell, dpi, label_font)

    # Markers last so grid lines never sit on top of a corner square.
    _draw_markers(img, page, dpi)
    return img


def write_pdf(path: str | Path, dpi: int = layout.DPI, charset: str = layout.CHARSET) -> None:
    """Write every page into one multi-page PDF that prints at true A4 size."""
    pages = [render_page(p, dpi, charset) for p in range(layout.page_count(charset))]
    pages[0].save(path, "PDF", save_all=True, append_images=pages[1:], resolution=dpi)


def write_pngs(out_dir: str | Path, dpi: int = layout.DPI, charset: str = layout.CHARSET) -> list[Path]:
    """Write ``page-1.png``, ``page-2.png``, ... into ``out_dir``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for p in range(layout.page_count(charset)):
        path = out / f"page-{p + 1}.png"
        render_page(p, dpi, charset).save(path, "PNG", dpi=(dpi, dpi))
        paths.append(path)
    return paths
