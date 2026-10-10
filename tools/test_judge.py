"""Tests for tools/judge.py. Run from repo root:

    python -m pytest tools/test_judge.py -q
"""
import copy
import json
from pathlib import Path

import numpy as np
import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

import judge

FIXTURE_FACTS = Path("/tmp/hf_fixture/facts.json")
FIXTURE_FONT = Path("/tmp/hf_fixture/AnnaHand-Regular.ttf")
ALLOWED = {"auto-fixed", "auto-fixable", "needs-handwriting", "decide"}


def _rect_font(path, chars):
    """A tiny TTF: one rectangle per char. Caps/digits 0..700, x 0..367,
    descenders -300..450, everything else 0..700."""
    order = [".notdef"] + [f"g{ord(c):04X}" for c in chars]
    cmap = {ord(c): f"g{ord(c):04X}" for c in chars}
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    glyphs, metrics = {}, {}
    for name in order:
        ch = chr(int(name[1:], 16)) if name != ".notdef" else None
        if ch in judge.DESCENDERS:
            y0, y1 = -300, 450
        elif ch in judge.X_LETTERS:
            y0, y1 = 0, 367
        else:
            y0, y1 = 0, 700
        pen = TTGlyphPen(None)
        pen.moveTo((60, y0)); pen.lineTo((460, y0)); pen.lineTo((460, y1))
        pen.lineTo((60, y1)); pen.closePath()
        glyphs[name] = pen.glyph()
        metrics[name] = (520, 60)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=900, descent=-300)
    fb.setupNameTable({"familyName": "Synth", "styleName": "Regular"})
    fb.setupOS2(sCapHeight=700, sxHeight=367)
    fb.setupPost()
    fb.save(str(path))
    return path


@pytest.fixture(scope="module")
def font(tmp_path_factory):
    chars = [c for c in judge.REQUIRED if c != "`"]  # backtick deliberately absent
    return _rect_font(tmp_path_factory.mktemp("font") / "synth.ttf", chars)


def _facts(**glyph_overrides):
    glyphs = {}
    for ch in judge.REQUIRED:
        glyphs[ch] = {"char": ch, "samples": 5, "picked": "x", "src": "alpha",
                      "quality": [1, 0], "scale": 1.0, "completed": [],
                      "overridden": False, "kind": judge._kind(ch, None)}
    for ch, patch in glyph_overrides.items():
        glyphs[ch] = {**glyphs[ch], **patch}
    return {"style": "hand", "family": "Synth", "targets": {}, "glyphs": glyphs}


def _check_report_shape(report):
    for key in ("summary", "issues", "needs_handwriting", "decide", "auto_fixable"):
        assert key in report
    s = report["summary"]
    for key in ("glyphs", "by_action", "by_severity", "score"):
        assert key in s
    assert 0 <= s["score"] <= 100
    for i in report["issues"]:
        assert set(i) >= {"char", "check", "severity", "detail", "action"}
        assert i["action"] in ALLOWED
        assert i["severity"] in judge.SEVERITIES


def test_fixture_run_writes_both_files(tmp_path):
    if not (FIXTURE_FACTS.exists() and FIXTURE_FONT.exists()):
        pytest.skip("fixture missing in /tmp/hf_fixture")
    report = judge.run(FIXTURE_FACTS, FIXTURE_FONT, tmp_path)
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "report.md").exists()
    on_disk = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert on_disk == json.loads(json.dumps(report))
    _check_report_shape(on_disk)
    md = (tmp_path / "report.md").read_text(encoding="utf-8")
    for heading in ("Fixed automatically", "Can be fixed in code",
                    "Needs your handwriting", "Your decision"):
        assert f"## {heading}" in md


def test_single_sample_letter_needs_handwriting(tmp_path, font):
    facts = _facts(A={"samples": 1})
    report = judge.run(facts, font, tmp_path)
    _check_report_shape(report)
    assert "A" in report["needs_handwriting"]
    assert any(i["char"] == "A" and i["check"] == "low_samples"
               and i["severity"] == "warn" for i in report["issues"])


def test_missing_from_font_is_error(tmp_path, font):
    # backtick is absent from the font by construction; Ж is absent too
    facts = _facts()
    report = judge.run(facts, font, tmp_path, required=judge.REQUIRED + "Ж")
    _check_report_shape(report)
    assert "`" in report["needs_handwriting"]
    assert "Ж" in report["needs_handwriting"]
    errs = [i for i in report["issues"] if i["check"] == "coverage"]
    assert {i["char"] for i in errs} == {"`", "Ж"}
    assert all(i["severity"] == "error" for i in errs)


def test_hurried_resized_and_completed_checks(tmp_path, font):
    facts = _facts(
        B={"quality": [2, 7]},
        C={"scale": 1.2, "samples": 4},
        D={"scale": 0.9},
        E={"completed": [{"target": "baseline", "added_px": 900},
                         {"target": "cap", "added_px": 700}]},
    )
    report = judge.run(facts, font, None)
    issues = report["issues"]

    def get(char, check):
        return [i for i in issues if i["char"] == char and i["check"] == check]

    assert get("B", "hurried")[0]["action"] == "needs-handwriting"
    assert get("C", "resized")[0]["severity"] == "warn"
    assert get("D", "resized")[0]["action"] == "auto-fixed"
    done = get("E", "completed")
    info = [i for i in done if i["severity"] == "info"][0]
    warn = [i for i in done if i["severity"] == "warn"][0]
    assert info["action"] == "auto-fixed"
    assert info["detail"].startswith("2 stroke(s)")
    assert warn["action"] == "needs-handwriting"  # 1600 px > 1500


def test_overridden_needs_decision(tmp_path, font):
    report = judge.run(_facts(F={"overridden": True}), font, None)
    assert "F" in report["decide"]


def test_metric_checks_flag_bad_heights(tmp_path, font):
    facts = _facts()
    report = judge.run(facts, font, None)
    # every glyph is a rectangle with exact heights, so no metric warnings
    assert not [i for i in report["issues"] if i["check"].startswith("metric")]
    m = judge.check_metrics("n", {"yMin": 0, "yMax": 500, "adv": 500}, 700, 367)
    assert m and m[0]["action"] == "auto-fixable"
    m = judge.check_metrics("H", {"yMin": -60, "yMax": 700, "adv": 500}, 700, 367)
    assert any("below baseline" in i["detail"] for i in m)
    m = judge.check_metrics("g", {"yMin": -40, "yMax": 380, "adv": 500}, 700, 367)
    assert any("descender too short" in i["detail"] for i in m)


def test_confusable_identical_masks_have_iou_one():
    from PIL import ImageFont
    f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 48) \
        if Path("/System/Library/Fonts/Supplemental/Arial.ttf").exists() \
        else ImageFont.load_default()
    m = judge._glyph_mask(f, "H")
    assert m is not None and judge._iou(m, m) == pytest.approx(1.0)
    assert judge._iou(np.zeros((4, 4), bool), np.zeros((4, 4), bool)) == 0.0


def test_score_formula(tmp_path, font):
    issues = [judge.issue("a", "x", "warn", "d", "decide"),
              judge.issue("b", "x", "error", "d", "needs-handwriting"),
              judge.issue("c", "x", "info", "d", "auto-fixed"),
              judge.issue("d", "x", "info", "d", "auto-fixed")]
    r = judge.build_report(issues, 4)
    assert r["summary"]["score"] == pytest.approx(100 - 3 - 10 - 0.5 - 0.5)
    assert r["needs_handwriting"] == ["b"]
    assert r["decide"] == ["a"]
    many = [judge.issue("z", "x", "error", "d", "decide")] * 20
    assert judge.build_report(many, 1)["summary"]["score"] == 0


def test_cli_writes_files(tmp_path, font):
    facts_path = tmp_path / "facts.json"
    facts_path.write_text(json.dumps(_facts(A={"samples": 1})), encoding="utf-8")
    out = tmp_path / "out"
    assert judge.main(["--facts", str(facts_path), "--font", str(font),
                       "--out", str(out)]) == 0
    assert (out / "report.json").exists() and (out / "report.md").exists()
