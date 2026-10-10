#!/usr/bin/env python3
"""REVIEW stage of the font iteration pipeline.

Reads the BUILD facts (facts.json) and the built TTF, runs every check and
writes DIR/report.json and DIR/report.md. Each issue carries an action:

    auto-fixed        the pipeline already fixed it; just recorded
    auto-fixable      a code or tuning fix can solve it
    needs-handwriting only new samples from the writer help
    decide            a human style decision

CLI:
    python tools/judge.py --facts F.json --font X.ttf --out DIR

Python API:
    import judge                       # run from tools/ or add it to sys.path
    report = judge.run(facts, font_path, out_dir, required=None)
    # facts: dict or path to facts.json; out_dir None = do not write files
"""
import argparse
import json
import string
from pathlib import Path

import numpy as np
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ACTIONS = ("auto-fixed", "auto-fixable", "needs-handwriting", "decide")
SEVERITIES = ("info", "warn", "error")
REQUIRED = string.ascii_letters + string.digits + "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
UPPER_DIGIT = set(string.ascii_uppercase + string.digits)
X_LETTERS = set("acemnorsuvwxz")
DESCENDERS = set("gjpqy")
NO_BELOW = DESCENDERS | set(",;Q")  # glyphs that may go below the baseline
CONFUSABLES = [("l", "I"), ("l", "1"), ("I", "1"), ("O", "0"), ("o", "0"),
               ("n", "h"), ("t", "+"), ("S", "5"), ("Z", "2"), ("B", "8"),
               ("g", "9"), ("q", "9"), ("u", "v"), ("c", "e")]

HURRIED_ENDS = 6            # loose ends at or above this = hurried pick
RESIZE_WARN = 0.15          # |scale - 1| at or above: warn
RESIZE_INFO = 0.08          # |scale - 1| at or above: info (auto-fixed)
COMPLETED_PX_WARN = 1500    # total px the pipeline added by finishing strokes
CAP_TOL = 0.12
X_TOL = 0.15
BELOW_LIMIT = -40           # units; lower than this = sits below baseline
DESC_MIN = -80              # units; a descender shallower than this is too short
WIDE_RATIO = 1.8
IOU_WARN = 0.6
SCORE_WEIGHT = {"warn": 3, "error": 10, "info": 0.5}


def issue(char, check, severity, detail, action):
    assert severity in SEVERITIES and action in ACTIONS
    return {"char": char, "check": check, "severity": severity,
            "detail": detail, "action": action}


def _is_alnum(ch):
    return ch.isascii() and ch.isalnum()


def _kind(ch, rec):
    if rec and rec.get("kind"):
        return rec["kind"]
    if ch in UPPER_DIGIT:
        return "cap"
    if ch in DESCENDERS:
        return "desc"
    if ch in X_LETTERS:
        return "x"
    if ch.isalpha():
        return "asc"
    return "other"


# ---- facts checks -------------------------------------------------------

def check_coverage(ch, in_font):
    if in_font:
        return []
    return [issue(ch, "coverage", "error",
                  "not in the font file; no glyph to show", "needs-handwriting")]


def check_samples(ch, rec):
    n = rec.get("samples", 0) if rec else 0
    if _is_alnum(ch):
        if n <= 0:
            return [issue(ch, "low_samples", "warn",
                          "no sample found in the photos", "needs-handwriting")]
        if n == 1:
            return [issue(ch, "low_samples", "warn",
                          "only 1 sample in the photos", "needs-handwriting")]
        if n == 2:
            return [issue(ch, "low_samples", "info",
                          "only 2 samples in the photos", "needs-handwriting")]
        return []
    if n <= 1:
        return [issue(ch, "low_samples", "info",
                      f"{n} sample(s) for a symbol", "needs-handwriting")]
    return []


def check_hurried(ch, rec):
    quality = (rec or {}).get("quality") or [0, 0]
    ends = quality[1] if len(quality) > 1 else 0
    if ends >= HURRIED_ENDS:
        return [issue(ch, "hurried", "warn",
                      f"pick looks hurried ({ends} loose ends)", "needs-handwriting")]
    return []


def check_resized(ch, rec):
    if not rec:
        return []
    scale = rec.get("scale", 1.0)
    diff = abs(scale - 1.0)
    if diff >= RESIZE_WARN:
        n = rec.get("samples", 0)
        if n >= 3:
            why = f"size differs across {n} samples; more samples will even it out"
        else:
            why = f"size corrected by x{scale:.2f} from only {n} sample(s)"
        return [issue(ch, "resized", "warn", why, "needs-handwriting")]
    if diff >= RESIZE_INFO:
        return [issue(ch, "resized", "info",
                      f"size corrected by x{scale:.2f} automatically", "auto-fixed")]
    return []


def check_completed(ch, rec):
    if not rec:
        return []
    done = [c for c in rec.get("completed") or [] if c.get("added_px", 0) > 0]
    if not done:
        return []
    targets = "/".join(sorted({c.get("target", "?") for c in done}))
    out = [issue(ch, "completed", "info",
                 f"{len(done)} stroke(s) finished to {targets}", "auto-fixed")]
    total = sum(c["added_px"] for c in done)
    if total > COMPLETED_PX_WARN:
        out.append(issue(ch, "completed", "warn",
                         f"pen lifted early a lot ({total} px added)",
                         "needs-handwriting"))
    return out


def check_overridden(ch, rec):
    if rec and rec.get("overridden"):
        return [issue(ch, "overridden", "info", "hand-picked; confirm", "decide")]
    return []


# ---- font metrics -------------------------------------------------------

def measure(tt, chars):
    """Return {char: {"yMin","yMax","adv"}} for chars that are in the font."""
    cmap = tt.getBestCmap()
    glyphset = tt.getGlyphSet()
    hmtx = tt["hmtx"]
    out = {}
    for ch in chars:
        name = cmap.get(ord(ch))
        if not name:
            continue
        pen = BoundsPen(glyphset)
        glyphset[name].draw(pen)
        b = pen.bounds
        out[ch] = {"yMin": b[1] if b else None,
                   "yMax": b[3] if b else None,
                   "adv": hmtx[name][0]}
    return out


def check_metrics(ch, m, cap_h, x_h):
    out = []
    ymin, ymax = m["yMin"], m["yMax"]
    if ymax is None:
        return out
    if ch in UPPER_DIGIT:
        off = abs(ymax - cap_h) / cap_h
        if off > CAP_TOL:
            out.append(issue(ch, "metric_top", "warn",
                             f"top at {ymax:.0f}, cap height is {cap_h} "
                             f"({off * 100:.0f}% off)", "auto-fixable"))
    if ch in X_LETTERS:
        off = abs(ymax - x_h) / x_h
        if off > X_TOL:
            out.append(issue(ch, "metric_top", "warn",
                             f"top at {ymax:.0f}, x-height is {x_h} "
                             f"({off * 100:.0f}% off)", "auto-fixable"))
    if _is_alnum(ch) and ch not in NO_BELOW and ymin < BELOW_LIMIT:
        out.append(issue(ch, "metric_bottom", "warn",
                         f"sits below baseline (bottom at {ymin:.0f})",
                         "auto-fixable"))
    if ch in DESCENDERS and ymin > DESC_MIN:
        out.append(issue(ch, "metric_bottom", "warn",
                         f"descender too short (bottom at {ymin:.0f})",
                         "auto-fixable"))
    return out


def check_wide(chars, metrics, glyphs):
    by_kind = {}
    for ch in chars:
        if ch in metrics:
            by_kind.setdefault(_kind(ch, glyphs.get(ch)), []).append(ch)
    out = []
    for kind, members in by_kind.items():
        if len(members) < 3:
            continue
        median = float(np.median([metrics[c]["adv"] for c in members]))
        if median <= 0:
            continue
        for ch in members:
            adv = metrics[ch]["adv"]
            if adv > WIDE_RATIO * median:
                out.append(issue(ch, "wide", "info",
                                 f"wide glyph: advance {adv} vs median {median:.0f} "
                                 f"for {kind}", "decide"))
    return out


# ---- confusables --------------------------------------------------------

def _glyph_mask(font, ch):
    canvas = Image.new("L", (64, 64), 0)
    ImageDraw.Draw(canvas).text((32, 32), ch, font=font, fill=255, anchor="mm")
    ink = np.array(canvas) > 127
    ys, xs = np.nonzero(ink)
    if ys.size == 0:
        return None
    crop = ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    scale = 48 / max(h, w)
    nh, nw = max(1, round(h * scale)), max(1, round(w * scale))
    small = Image.fromarray((crop * 255).astype(np.uint8)).resize((nw, nh), Image.BILINEAR)
    out = np.zeros((48, 48), dtype=bool)
    oy, ox = (48 - nh) // 2, (48 - nw) // 2
    out[oy:oy + nh, ox:ox + nw] = np.array(small) > 127
    return out


def _iou(a, b):
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0


def check_confusables(font_path, cmap):
    font = ImageFont.truetype(str(font_path), 48)
    masks = {}

    def mask(ch):
        if ch not in masks:
            masks[ch] = _glyph_mask(font, ch) if ord(ch) in cmap else None
        return masks[ch]

    out = []
    for a, b in CONFUSABLES:
        ma, mb = mask(a), mask(b)
        if ma is None or mb is None:
            continue
        iou = _iou(ma, mb)
        if iou > IOU_WARN:
            out.append(issue(f"{a}/{b}", "confusable", "warn",
                             f"may look alike (IoU {iou:.2f}); give {a} or {b} "
                             "a distinct shape", "decide"))
    return out


# ---- report -------------------------------------------------------------

def build_report(issues, n_glyphs):
    by_action = {a: 0 for a in ACTIONS}
    by_sev = {s: 0 for s in SEVERITIES}
    penalty = 0.0
    for i in issues:
        by_action[i["action"]] += 1
        by_sev[i["severity"]] += 1
        penalty += SCORE_WEIGHT[i["severity"]]
    score = round(max(0.0, 100.0 - penalty), 1)

    def chars_for(action):
        return sorted({i["char"] for i in issues if i["action"] == action})

    return {
        "summary": {"glyphs": n_glyphs, "by_action": by_action,
                    "by_severity": by_sev, "score": score},
        "issues": issues,
        "needs_handwriting": chars_for("needs-handwriting"),
        "decide": chars_for("decide"),
        "auto_fixable": chars_for("auto-fixable"),
        "auto_fixed": chars_for("auto-fixed"),
    }


def _md_char(ch):
    return "`` ` ``" if ch == "`" else f"`{ch}`"


def _section(lines, title, issues, action):
    lines += [f"## {title}", ""]
    grouped = {}
    for i in issues:
        if i["action"] != action:
            continue
        label = f"[{i['severity']}] {i['detail']}"
        notes = grouped.setdefault(i["char"], [])
        if label not in notes:
            notes.append(label)
    if not grouped:
        lines += ["- None.", ""]
        return
    for ch in sorted(grouped):
        lines.append(f"- {_md_char(ch)}: " + "; ".join(grouped[ch]))
    lines.append("")


def to_markdown(report, facts):
    s = report["summary"]
    name = " ".join(x for x in (facts.get("family"), facts.get("style")) if x)
    lines = [f"# Font review: {name or 'untitled'}", "",
             f"Score: {s['score']} out of 100", "",
             f"Characters checked: {s['glyphs']}",
             f"Needs your handwriting: {len(report['needs_handwriting'])} character(s)",
             f"Your decision: {len(report['decide'])} item(s)",
             f"Fixed automatically: {len(report['auto_fixed'])} character(s)",
             f"Can be fixed in code: {len(report['auto_fixable'])} character(s)",
             ""]
    for title, action in (("Fixed automatically", "auto-fixed"),
                          ("Can be fixed in code", "auto-fixable"),
                          ("Needs your handwriting", "needs-handwriting"),
                          ("Your decision", "decide")):
        _section(lines, title, report["issues"], action)
    return "\n".join(lines) + "\n"


def run(facts, font_path, out_dir=None, required=None):
    """Review one build. Returns the report dict; writes files when out_dir is set."""
    if isinstance(facts, (str, Path)):
        facts = json.loads(Path(facts).read_text(encoding="utf-8"))
    req = list(dict.fromkeys(REQUIRED if required is None else required))
    glyphs = facts.get("glyphs", {})
    chars = req + [c for c in glyphs if c not in req]

    tt = TTFont(str(font_path))
    cmap = tt.getBestCmap()
    cap_h = tt["OS/2"].sCapHeight
    x_h = tt["OS/2"].sxHeight
    metrics = measure(tt, chars)

    issues = []
    for ch in chars:
        rec = glyphs.get(ch)
        if ch in req:
            issues += check_coverage(ch, ord(ch) in cmap)
        issues += check_samples(ch, rec)
        issues += check_hurried(ch, rec)
        issues += check_resized(ch, rec)
        issues += check_completed(ch, rec)
        issues += check_overridden(ch, rec)
        if ch in metrics:
            issues += check_metrics(ch, metrics[ch], cap_h, x_h)
    issues += check_wide(chars, metrics, glyphs)
    issues += check_confusables(font_path, cmap)

    report = build_report(issues, len(chars))
    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (out / "report.md").write_text(to_markdown(report, facts), encoding="utf-8")
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description="Review a built font against its facts.")
    p.add_argument("--facts", required=True)
    p.add_argument("--font", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    report = run(a.facts, a.font, a.out)
    s = report["summary"]
    print(f"score {s['score']}/100; {s['glyphs']} characters; "
          f"needs handwriting: {', '.join(report['needs_handwriting']) or 'none'}")
    print(f"wrote {Path(a.out) / 'report.json'} and {Path(a.out) / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
