"""Command-line interface: ``handfont template`` and ``handfont build``."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from handfont.build import build_font
from handfont.layout import CHARSET
from handfont.preview import render_preview
from handfont.scan import extract_from_files
from handfont.template import write_pdf, write_pngs
from handfont.vectorize import trace_glyph

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    tomllib = None

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
A4_NOTE = "Print at 100% (Actual size) on A4 — do not use 'fit to page'."
_KV_RE = re.compile(r'^\s*([A-Za-z_][\w-]*)\s*=\s*"([^"]*)"\s*$', re.MULTILINE)


def _load_config(path) -> dict:
    """Read a small TOML config. Falls back to ``key = "value"`` lines."""
    if not path or not Path(path).exists():
        return {}
    text = Path(path).read_text(encoding="utf-8")
    if tomllib is not None:
        return tomllib.loads(text)
    return {m.group(1): m.group(2) for m in _KV_RE.finditer(text)}


def _cmd_template(args) -> int:
    out = Path(args.output)
    if str(args.output).endswith(".png"):
        paths = write_pngs(Path(args.output).parent or ".")
        for p in paths:
            print(p)
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        write_pdf(out)
        print(out)
    print(A4_NOTE)
    return 0


def _cmd_build(args) -> int:
    files: list[Path] = []
    for raw in args.inputs:
        p = Path(raw)
        if p.is_dir():
            files.extend(
                sorted(
                    f
                    for f in p.iterdir()
                    if f.is_file() and f.suffix.lower() in IMAGE_SUFFIXES
                )
            )
        else:
            files.append(p)

    if not files:
        print(
            f"No scan images found in: {', '.join(args.inputs)}",
            file=sys.stderr,
        )
        return 1

    try:
        cfg = _load_config(args.config)
    except ValueError as e:
        print(f"Error: could not read config {args.config}: {e}", file=sys.stderr)
        return 1
    family = args.family or cfg.get("family") or "MyHand"
    version = args.version or cfg.get("version") or "0.1.0"

    try:
        bitmaps = extract_from_files(files)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not bitmaps:
        print("No characters found in the scan images.", file=sys.stderr)
        return 1

    vglyphs = [trace_glyph(b) for b in bitmaps.values()]
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    paths = build_font(vglyphs, family, out, version=version)
    preview = render_preview(paths["ttf"], out / "preview.png", family)

    print(f"Found {len(bitmaps)} of {len(CHARSET)} characters")
    missing = [c for c in CHARSET if c not in bitmaps]
    if missing:
        print("Missing (rewrite these): " + " ".join(missing))
    for key in ("otf", "ttf", "woff2", "woff", "css"):
        print(paths[key])
    print(preview)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="handfont", description="Turn handwriting scans into a font."
    )
    sub = parser.add_subparsers(dest="command")

    p_tpl = sub.add_parser("template", help="write the printable template")
    p_tpl.add_argument("-o", "--output", default="template.pdf")

    p_build = sub.add_parser("build", help="build a font from scan images")
    p_build.add_argument("inputs", nargs="+", help="image files or folders")
    p_build.add_argument("--config", default=None, help="TOML config file")
    p_build.add_argument("--family", default=None, help="font family name")
    p_build.add_argument("--version", default=None, help="font version")
    p_build.add_argument("-o", "--output", default="dist", help="output folder")

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    if args.command == "template":
        return _cmd_template(args)
    return _cmd_build(args)


if __name__ == "__main__":
    raise SystemExit(main())
