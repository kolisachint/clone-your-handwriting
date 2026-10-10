#!/usr/bin/env python3
"""Turn a font review report into a printable A4 handwriting handover PDF.

Page 1 says which characters to write next and why. Later pages are
ruled writing lines with a grey prompt above each line.

API:   make_pdf(report, out_path, round_no=1, family="AnnaHand") -> page count
CLI:   python tools/handover.py --report R.json --out OUT.pdf --round N --family NAME
"""
import argparse
import json
import os
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

MAX_CHARS = 30
GRID_COLS = 5
CELL_W = 30          # mm
ROW_H = 27           # mm
FALLBACK_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
FALLBACK_NAME = "UniFallback"
SEVERITY_RANK = {"error": 0, "warn": 1, "info": 2}
REASON_WORDS = {
    "coverage": "missing",
    "hurried": "looked hurried",
    "resized": "size varies",
    "completed": "stroke stopped short",
}
HOW_TO_WRITE = [
    "Use the same pen as last time.",
    "Write slowly.",
    "Finish every stroke down to the line.",
    "Leave a small gap between letters.",
    "Plan about 10 minutes.",
]
HOW_TO_HAND_OVER = [
    "Take a photo from straight above, in daylight.",
    "Keep the whole page in the photo.",
    "Send it to hoo in Discord with @hoo.",
]
PANGRAMS = [
    "The quick brown fox jumps over the lazy dog.",
    "Pack my box with five dozen liquor jugs.",
]

WORDS = """
the and for are but not you all any can had her was one our out day get has him
his how man new now old see two way who boy did its let put say she too use
about after again air also another answer around away back be because been before
being below between big book both call came come could day different does down
each end even every example find first follow found from give good great group
hand help here high home house however large last left letter like line little
long look made make many may mean men might more most much must name never next
night number off often once only open or other over own part people place plan
point put read right room same school second see seem set several she should show
side since small so some something sound still such take tell than that their
them then there these they thing think this those though thought three through
time together too took toward try turn under until upon us use very walk want
water way we well went were what when where which while white who why will with
within without word work world would write year yet young
quiz jazz zebra fizz box fox vex jinx kayak quick query quote aqua equal liquid
zone maze dozen
bright brown cloud coffee dance dream early earth energy eye family fire
future garden glass gold grow happy heart jump keep kind knee knife lazy
lemon lunch magic market measure metal mix music nature needle orange paper
pencil quiet quilt rain river rock sailor sugar summer table tiger train
under value voice wave winter yellow zoo
""".split()

# Snippets for symbols. Keys are the characters themselves.
SNIPPETS = {
    "'": "it's don't I'm",
    '"': '"hi" "ok"',
    "(": "(a) (ok) (1)",
    ")": "(a) (ok) (1)",
    "[": "[a] [1]",
    "]": "[a] [1]",
    "{": "{a} {b}",
    "}": "{a} {b}",
    "<": "a<b 1<2",
    ">": "b>a 2>1",
    "/": "a/b 1/2",
    "\\": "a\\b c\\d",
    "|": "a|b x|y",
    "_": "a_b my_file",
    "-": "well-known x-ray",
    "+": "1+1 a+b",
    "=": "a=b 2=2",
    "*": "a*b 2*3",
    "#": "#1 #tag",
    "@": "a@b.com @hoo",
    "&": "you & me",
    "%": "50% 10%",
    "$": "$5 $10",
    "!": "yes! wow!",
    "?": "why? ok?",
    ":": "10:45 a:b",
    ";": "a; b; c",
    "^": "2^3 x^2",
    "~": "~5 a~b",
    "`": "`code` `x`",
    "£": "£5 £10",
    "€": "€5 €20",
    "¥": "¥5 ¥100",
    "₹": "₹5 ₹10",
    "—": "yes — no",
}


def _reason(issue):
    check = issue.get("check", "") or ""
    if check == "low_samples":
        m = re.search(r"(\d+)\s+sample", issue.get("detail", "") or "")
        if m:
            n = int(m.group(1))
            return "only 1 copy" if n == 1 else f"only {n} copies"
        return "few copies"
    if check in REASON_WORDS:
        return REASON_WORDS[check]
    return check.replace("_", " ") or "check"


def plan_chars(report):
    """Return (items, more) where items is [(char, reason_text)], capped."""
    by_char = {}
    for issue in report.get("issues") or []:
        by_char.setdefault(issue.get("char"), []).append(issue)

    needed = []
    for c in report.get("needs_handwriting") or []:
        if c and c not in needed:
            needed.append(c)

    def severity_rank(c):
        ranks = [SEVERITY_RANK.get(i.get("severity"), 3) for i in by_char.get(c, [])]
        return min(ranks) if ranks else SEVERITY_RANK["info"]

    def category(c):
        if c.isalpha():
            return 0
        if c.isdigit():
            return 1
        return 2

    order = sorted(range(len(needed)),
                   key=lambda i: (severity_rank(needed[i]), category(needed[i]), i))
    ordered = [needed[i] for i in order]
    shown, more = ordered[:MAX_CHARS], max(0, len(ordered) - MAX_CHARS)

    items = []
    for c in shown:
        reasons = []
        for issue in by_char.get(c, []):
            r = _reason(issue)
            if r not in reasons:
                reasons.append(r)
        items.append((c, ", ".join(reasons) or "new"))
    return items, more


def _encodable(text):
    try:
        text.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


_fallback_state = {"tried": False, "ok": False}


def _fallback_ok():
    if not _fallback_state["tried"]:
        _fallback_state["tried"] = True
        if os.path.exists(FALLBACK_PATH):
            try:
                pdfmetrics.registerFont(TTFont(FALLBACK_NAME, FALLBACK_PATH))
                _fallback_state["ok"] = True
            except Exception:
                _fallback_state["ok"] = False
    return _fallback_state["ok"]


def _font_for(text, bold=False):
    """Standard Helvetica when cp1252 can encode the text, else the fallback TTF.

    Returns None when the text cannot be drawn at all.
    """
    if _encodable(text):
        return "Helvetica-Bold" if bold else "Helvetica"
    if _fallback_ok():
        return FALLBACK_NAME
    return None


def _words_for(c):
    if c.isalpha():
        low = c.lower()
        if c.isupper():
            starts = [w for w in WORDS if w[0] == low]
            if starts:
                return [w.capitalize() for w in starts[:3]]
            return [w.upper() for w in [w for w in WORDS if low in w][:3]]
        return [w for w in WORDS if low in w][:3]
    return None


def _prompt_lines(c):
    """The two prompt lines for one needed character."""
    if c.isdigit():
        line2 = f"{c}0{c} {c}.{c} 1{c}{c}"
    elif c.isalpha():
        words = _words_for(c)
        line2 = " ".join(words) if words else c * 3
    else:
        line2 = SNIPPETS.get(c, c * 3)
    return ["  ".join([c] * 5), line2]


def _draw_centered_wrapped(c, text, font, size, x_center, y_top, width):
    lines = simpleSplit(text, font, size, width)
    y = y_top
    for line in lines:
        c.setFont(font, size)
        c.setFillGray(0.4)
        c.drawCentredString(x_center, y, line)
        y -= size * 1.25
    return y


def _draw_bullets(c, heading, bullets, y_mm, width_mm=170):
    c.setFillGray(0)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(20 * mm, y_mm * mm, heading)
    y = y_mm - 8
    for text in bullets:
        lines = simpleSplit("\u2022  " + text, "Helvetica", 13, width_mm * mm)
        for i, line in enumerate(lines):
            x = 20 * mm
            c.setFont("Helvetica", 13)
            c.setFillGray(0)
            if i == 0:
                c.drawString(x, y * mm, line)
            else:
                c.drawString(x + 5 * mm, y * mm, line)
            y -= 6.5
        y -= 1
    return y


def _draw_overview(c, report, round_no, items, more, skipped):
    W, H = A4
    score = (report.get("summary") or {}).get("score")
    score_txt = "?" if score is None else f"{score:g}"

    c.setFillGray(0)
    c.setFont("Helvetica-Bold", 26)
    c.drawString(20 * mm, 280 * mm, f"Round {round_no} \u2014 what to write")
    c.setFont("Helvetica", 14)
    c.drawString(20 * mm, 269 * mm, f"Score now: {score_txt} / 100")

    grid_top = 258.0
    x0 = (210 - GRID_COLS * CELL_W) / 2.0
    y = grid_top
    if not items:
        c.setFont("Helvetica", 13)
        c.drawString(20 * mm, (y - 5) * mm, "Nothing needs writing this round.")
        y -= 12
    for i, (ch, reason) in enumerate(items):
        row, col = divmod(i, GRID_COLS)
        if col == 0 and i > 0:
            y -= ROW_H
        cell_x = (x0 + col * CELL_W) * mm
        cx = cell_x + CELL_W * mm / 2.0
        font = _font_for(ch, bold=True)
        c.setFillGray(0)
        c.setFont(font, 34)
        c.drawCentredString(cx, (y - 10) * mm, ch)
        _draw_centered_wrapped(c, reason, "Helvetica", 9, cx,
                               (y - 16) * mm, CELL_W * mm - 4 * mm)
    if items:
        y -= ROW_H
    y -= 3

    notes = []
    if more:
        notes.append(f"+{more} more next round")
    if skipped:
        notes.append("No font for: " + " ".join(skipped) + " (not drawn)")
    for note in notes:
        c.setFillGray(0.3)
        c.setFont("Helvetica", 11)
        c.drawString(20 * mm, y * mm, note)
        y -= 6

    y = _draw_bullets(c, "How to write", HOW_TO_WRITE, y - 6)
    _draw_bullets(c, "How to hand it over", HOW_TO_HAND_OVER, y - 4)


def _draw_writing_page(c, rows, family, round_no, page_no):
    """rows: list of (baseline_mm, prompt_text)."""
    for base, prompt in rows:
        b = base * mm
        c.setStrokeGray(0.85)
        c.setLineWidth(0.5)
        c.line(20 * mm, b + 5 * mm, 190 * mm, b + 5 * mm)
        c.setStrokeGray(0.35)
        c.setLineWidth(1)
        c.line(20 * mm, b, 190 * mm, b)
        font = _font_for(prompt) or "Helvetica"
        c.setFont(font, 9)
        c.setFillGray(0.45)
        c.drawString(20 * mm, b + 1.2 * mm, prompt)
    c.setFont("Helvetica", 7)
    c.setFillGray(0.5)
    c.drawString(20 * mm, 10 * mm, f"{family} \u00b7 round {round_no} \u00b7 page {page_no}")


def make_pdf(report, out_path, round_no=1, family="AnnaHand"):
    """Write the handover PDF to out_path. Returns the page count."""
    items, more = plan_chars(report)

    skipped = []
    usable = []
    for ch, reason in items:
        if _font_for(ch) is None:
            skipped.append(ch)
        else:
            usable.append((ch, reason))
    items = usable

    prompt_lines = []
    for ch, _ in items:
        if _font_for(ch) is None:
            continue
        prompt_lines.extend(_prompt_lines(ch))
    prompt_lines.extend(PANGRAMS)

    # Writing lines: baseline every 14mm from 270mm down to 20mm.
    baselines = []
    y = 270.0
    while y >= 20 - 1e-9:
        baselines.append(y)
        y -= 14
    per_page = len(baselines)

    c = canvas.Canvas(out_path, pagesize=A4)
    c.setTitle(f"{family} round {round_no} handover")
    c.setAuthor("hoocode")

    _draw_overview(c, report, round_no, items, more, skipped)
    c.showPage()

    pages = 1
    for start in range(0, len(prompt_lines), per_page):
        chunk = prompt_lines[start:start + per_page]
        rows = list(zip(baselines, chunk))
        pages += 1
        _draw_writing_page(c, rows, family, round_no, pages)
        c.showPage()

    c.save()
    return pages


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", required=True, help="review report.json")
    ap.add_argument("--out", required=True, help="output PDF path")
    ap.add_argument("--round", type=int, default=1, dest="round_no")
    ap.add_argument("--family", default="AnnaHand")
    args = ap.parse_args(argv)

    with open(args.report, encoding="utf-8") as f:
        report = json.load(f)
    pages = make_pdf(report, args.out, round_no=args.round_no, family=args.family)
    print(f"wrote {args.out} ({pages} pages)")
    return pages


if __name__ == "__main__":
    main()
