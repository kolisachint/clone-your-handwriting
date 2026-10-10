"""Render a PNG specimen sheet for a built TTF font."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1600
MARGIN = 40
INK = (30, 30, 30)
LINE_FACTOR = 1.6


def render_preview(ttf_path, out_png, family) -> Path:
    """Draw the family name and sample lines in ``ttf_path`` to ``out_png``."""
    ttf_path = Path(ttf_path)
    out_png = Path(out_png)

    lines = [
        (family, 72),
        ("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 56),
        ("abcdefghijklmnopqrstuvwxyz", 56),
        ("0123456789 !?&@#()", 56),
        ("The quick brown fox jumps over the lazy dog.", 48),
    ]

    height = MARGIN * 2 + sum(int(size * LINE_FACTOR) for _, size in lines)
    img = Image.new("RGB", (WIDTH, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    y = MARGIN
    for text, size in lines:
        font = ImageFont.truetype(str(ttf_path), size)
        draw.text((MARGIN, y), text, font=font, fill=INK)
        y += int(size * LINE_FACTOR)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    return out_png
