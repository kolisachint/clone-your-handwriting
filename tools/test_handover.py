"""Tests for tools/handover.py. Run from repo root:
    python -m pytest tools/test_handover.py -q
"""
import fitz  # pymupdf

from handover import make_pdf, plan_chars

REPORT = {
    "summary": {"score": 38.0},
    "issues": [
        {"char": "`", "check": "coverage", "severity": "error",
         "detail": "not in the font file; no glyph to show", "action": "needs-handwriting"},
        {"char": "A", "check": "low_samples", "severity": "warn",
         "detail": "only 2 samples in the photos", "action": "needs-handwriting"},
        {"char": "A", "check": "resized", "severity": "info",
         "detail": "size corrected", "action": "auto-fixed"},
        {"char": "m", "check": "completed", "severity": "info",
         "detail": "1 stroke(s) finished to cap", "action": "auto-fixed"},
        {"char": "4", "check": "low_samples", "severity": "info",
         "detail": "1 sample(s) for a symbol", "action": "needs-handwriting"},
        {"char": "?", "check": "low_samples", "severity": "info",
         "detail": "1 sample(s) for a symbol", "action": "needs-handwriting"},
    ],
    "needs_handwriting": ["A", "m", "4", "`", "?"],
}


def test_priority_order_and_reasons():
    items, more = plan_chars(REPORT)
    assert more == 0
    assert [c for c, _ in items] == ["`", "A", "m", "4", "?"]
    reasons = dict(items)
    assert reasons["`"] == "missing"
    assert reasons["A"] == "only 2 copies, size varies"
    assert reasons["m"] == "stroke stopped short"
    assert reasons["4"] == "only 1 copy"


def test_make_pdf_writes_pages(tmp_path):
    out = tmp_path / "handover.pdf"
    pages = make_pdf(REPORT, str(out), round_no=2, family="AnnaHand")
    assert out.exists()
    assert pages >= 2

    doc = fitz.open(str(out))
    assert doc.page_count == pages
    text = "".join(page.get_text() for page in doc)
    doc.close()
    assert "Round" in text
    assert "m  m  m" in text
