#!/usr/bin/env python3
"""Run one whole iteration of AnnaHand, end to end.

Run from the repo root:

    python tools/pipeline.py --round N
    python tools/pipeline.py --round N --skip-extract
    python tools/pipeline.py --round N --words

Steps (each one prints a heading, then OK / FAIL / SKIP and how long it took):

    a) EXTRACT   tools/extract.py           -> tools/samples.pkl        (required)
    b) WORDS     tools/words.py             -> tools/word_samples.pkl   (only with --words)
    c) BUILD     tools/make.py x 4 styles   -> fonts/AnnaHand*/         (required)
    d) REVIEW    tools/judge.py (or review_report.py)
                                            -> iterations/round-N/report.json + report.md
    e) HANDOVER  tools/handover.py          -> iterations/round-N/write-next.pdf
    f) PREVIEW   tools/review.py            -> previews/styles.png
    g) PACKAGE   tools/package.py           -> dist/
    h) README    iterations/round-N/README.md

Extract and build are required: if either fails, the pipeline stops and
exits 1. Any other step that fails is reported as FAIL and the rest still
runs. A step that cannot run yet (for example, judge.py not written) is SKIP.
"""

import argparse
import datetime
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
FONTS = ROOT / "fonts"
PREVIEWS = ROOT / "previews"
HANDWRITING = ROOT / "handwriting"
ITERATIONS = ROOT / "iterations"
PY = sys.executable

# (style, family). Folder name == family name.
FAMILIES = [
    ("hand", "AnnaHand"),
    ("paper", "AnnaHandPaper"),
    ("typed", "AnnaHandTyped"),
    ("access", "AnnaHandAccess"),
]
MAIN_FAMILY = "AnnaHand"
MAIN_FONT = FONTS / MAIN_FAMILY / f"{MAIN_FAMILY}-Regular.ttf"


class Skip(Exception):
    """Raised by a step that cannot run yet. Not a failure."""


RESULTS = []  # (label, status, seconds, note)


def run(cmd, cwd):
    """Run a child process, streaming its output. Raises on non-zero exit."""
    args = [str(c) for c in cmd]
    print("  $ " + " ".join(args), flush=True)
    subprocess.run(args, cwd=str(cwd), check=True)


def step(label, fn, required=False):
    """Run one step with a heading, a timer and an OK / FAIL / SKIP line."""
    print(f"\n== {label} ==", flush=True)
    t0 = time.monotonic()
    try:
        fn()
        status, note = "OK", ""
    except Skip as e:
        status, note = "SKIP", str(e)
    except Exception as e:  # CalledProcessError, RuntimeError, ...
        status, note = "FAIL", str(e)
    dt = time.monotonic() - t0
    RESULTS.append((label, status, dt, note))
    tail = f" - {note}" if note else ""
    print(f"-- {label}: {status} ({dt:.1f}s){tail}", flush=True)
    if status == "FAIL" and required:
        print("\nRequired step failed. Stopping here.", flush=True)
        print_summary()
        sys.exit(1)


def print_summary():
    print("\n== Summary ==")
    total = 0.0
    for label, status, dt, note in RESULTS:
        total += dt
        line = f"{status:<4}  {dt:6.1f}s  {label}"
        if note and status != "OK":
            line += f"  ({note})"
        print(line)
    print(f"Total: {total:.1f}s")


# ---------------------------------------------------------------- steps

def do_extract(args):
    if args.skip_extract:
        raise Skip("skipped by --skip-extract")
    run([PY, "extract.py"], cwd=TOOLS)


def do_words(args):
    if not args.words or args.skip_words:
        raise Skip("not requested (add --words to run it)")
    run([PY, "words.py"], cwd=TOOLS)


def do_build(args, round_dir):
    if not (TOOLS / "samples.pkl").exists():
        raise RuntimeError("tools/samples.pkl is missing; run without --skip-extract")
    facts = round_dir / "facts.json"
    for style, family in FAMILIES:
        cmd = [PY, "make.py", FONTS / family, family, "--style", style]
        if style == "hand":
            cmd += ["--dump", facts]
        run(cmd, cwd=TOOLS)
    if not MAIN_FONT.exists():
        raise RuntimeError(f"expected {MAIN_FONT.relative_to(ROOT)} after build")
    if not facts.exists():
        raise RuntimeError("expected facts.json after build")


def find_judge():
    for name in ("judge.py", "review_report.py"):
        p = TOOLS / name
        if p.exists():
            return p
    return None


def do_review(round_dir):
    judge = find_judge()
    if judge is None:
        raise Skip("no tools/judge.py or tools/review_report.py yet")
    run([PY, judge, "--facts", round_dir / "facts.json",
         "--font", MAIN_FONT, "--out", round_dir], cwd=ROOT)
    if not (round_dir / "report.json").exists():
        raise RuntimeError("judge ran but report.json was not written")


def do_handover(n, round_dir):
    script = TOOLS / "handover.py"
    if not script.exists():
        raise Skip("no tools/handover.py yet")
    report = round_dir / "report.json"
    if not report.exists():
        raise Skip("no report.json (review skipped or failed)")
    out = round_dir / "write-next.pdf"
    run([PY, script, "--report", report, "--out", out,
         "--round", str(n), "--family", MAIN_FAMILY], cwd=ROOT)
    if not out.exists():
        raise RuntimeError("handover ran but write-next.pdf was not written")


def do_preview():
    # review.py wants ROOT/<hand|paper|typed|access|raw>/*.ttf
    tmp = Path(tempfile.mkdtemp(prefix="hfv-preview-"))
    try:
        for style, family in FAMILIES:
            (tmp / style).symlink_to(FONTS / family, target_is_directory=True)
        # no separate raw build yet: show the handwritten style as "raw"
        (tmp / "raw").symlink_to(FONTS / MAIN_FAMILY, target_is_directory=True)
        PREVIEWS.mkdir(exist_ok=True)
        run([PY, TOOLS / "review.py", tmp, PREVIEWS / "styles.png"], cwd=ROOT)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def do_package():
    run([PY, TOOLS / "package.py"], cwd=ROOT)


# ---------------------------------------------------------------- report

CATEGORIES = ["auto-fixed", "fixable in code", "needs handwriting", "your decision"]


def categorize(label):
    """Map any judge label (auto_fixed, fixable-in-code, needs_handwriting,
    decide...) onto one of the four categories. None if unknown."""
    s = str(label).lower()
    # "auto-fixable" (judge) means a code fix: check it before "auto"
    if "code" in s or "fixable" in s:
        return "fixable in code"
    if "auto" in s:
        return "auto-fixed"
    if "hand" in s or "writing" in s:
        return "needs handwriting"
    if "decid" in s or "decision" in s or "choice" in s:
        return "your decision"
    return None


def read_report(path):
    """Pull score and category counts out of report.json.

    judge.py writes:  summary.score (0-100) and summary.by_action
    (action -> number of issues), plus an 'issues' list where each item
    has an 'action'. Other shapes are accepted as fallbacks. Anything not
    found is reported as unknown rather than guessed.
    """
    info = {"score": "not in report.json", "counts": None}
    if not path.exists():
        info["score"] = "no report.json"
        return info
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        info["score"] = f"report.json unreadable: {e}"
        return info
    if not isinstance(data, dict):
        return info

    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    score = summary.get("score", data.get("score"))
    if isinstance(score, dict):
        score = score.get("overall", score.get("total"))
    if isinstance(score, (int, float)):
        info["score"] = f"{score} / 100"      # judge scores are out of 100
    elif score is not None:
        info["score"] = str(score)

    counts = {c: 0 for c in CATEGORIES}
    found = False
    by_action = summary.get("by_action", data.get("counts"))
    if isinstance(by_action, dict):
        for k, v in by_action.items():
            cat = categorize(k)
            if cat and isinstance(v, (int, float)):
                counts[cat] += int(v)
                found = True
    else:
        items = data.get("issues", data.get("items"))
        for it in items if isinstance(items, list) else []:
            if not isinstance(it, dict):
                continue
            cat = categorize(it.get("action", ""))
            if cat:
                counts[cat] += 1
                found = True
    info["counts"] = counts if found else None
    return info


def photo_list():
    if not HANDWRITING.exists():
        return []
    files = []
    for p in sorted(HANDWRITING.glob("*/*")):
        if p.suffix.lower() in (".jpg", ".jpeg"):
            files.append(p.relative_to(ROOT).as_posix())
    return files


def write_readme(n, round_dir):
    info = read_report(round_dir / "report.json")
    photos = photo_list()
    today = datetime.date.today().isoformat()

    def link(name):
        p = round_dir / name
        return f"[{name}]({name})" if p.exists() else f"{name} (not made yet)"

    lines = [
        f"# AnnaHand round {n}",
        "",
        f"Date: {today}",
        "",
        "## Score",
        "",
        f"- Score: {info['score']}",
    ]
    if info["counts"] is None:
        lines.append("- Category counts: not found in report.json")
    else:
        lines.append("- Issues by category:")
        for c in CATEGORIES:
            lines.append(f"  - {c}: {info['counts'][c]}")
    lines += [
        "",
        "## Files",
        "",
        f"- Report: {link('report.md')}",
        f"- Handwriting to write next: {link('write-next.pdf')}",
        f"- Facts (per glyph): {link('facts.json')}",
        "",
        f"## Photos used ({len(photos)})",
        "",
    ]
    lines += [f"- {p}" for p in photos] or ["- none found"]
    lines += [
        "",
        "## Categories",
        "",
        "- Auto-fixed: the pipeline did it. Nothing to do.",
        "- Fixable in code: the bot or a developer changes tools/. No handwriting.",
        "- Needs handwriting: see write-next.pdf.",
        "- Your decision: a style choice for you to make.",
        "",
    ]
    (round_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--round", type=int, required=True, help="round number N")
    ap.add_argument("--skip-extract", action="store_true",
                    help="reuse tools/samples.pkl")
    ap.add_argument("--words", action="store_true",
                    help="also run words.py (slow; reviewed by hand)")
    ap.add_argument("--skip-words", action="store_true",
                    help="same as the default: do not run words.py")
    args = ap.parse_args()
    if args.round < 0:
        ap.error("--round must be 0 or more")

    n = args.round
    round_dir = ITERATIONS / f"round-{n}"
    round_dir.mkdir(parents=True, exist_ok=True)
    print(f"AnnaHand pipeline, round {n}")
    print(f"Output: {round_dir.relative_to(ROOT)}")

    step("a) EXTRACT", lambda: do_extract(args), required=True)
    step("b) WORDS", lambda: do_words(args))
    step("c) BUILD", lambda: do_build(args, round_dir), required=True)
    step("d) REVIEW", lambda: do_review(round_dir))
    step("e) HANDOVER", lambda: do_handover(n, round_dir))
    step("f) PREVIEW", do_preview)
    step("g) PACKAGE", do_package)
    step("h) README", lambda: write_readme(n, round_dir))

    print_summary()
    failed = [r[0] for r in RESULTS if r[1] == "FAIL"]
    if failed:
        print("\nSome optional steps failed. Read the lines above:")
        for label in failed:
            print(f"  - {label}")
    print(f"\nRound {n} README: {(round_dir / 'README.md').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
