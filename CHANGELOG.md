# Changelog

## v0.3.0 — 2026-10-10

First release.

### Font

- 4 styles from one handwriting:
  AnnaHand, AnnaHandPaper, AnnaHandTyped, AnnaHandAccess.
- 98 characters each: A–Z, a–z, 0–9, punctuation, $ € £ ¥ ₹.
- Missing: the backtick `` ` ``.
- Formats: OTF, TTF, WOFF2, WOFF, CSS.
- Bundles: web, desktop, iOS profile, Android, Office, design apps.

### How it was made

- 5 notebook photos (`handwriting/2026-10-10/`), about 400 letter copies.
- Letters from alphabet lines and from sentence pages.
- Each written line straightened (tilt up to 3.5°).
- Letters sized to the writer's own cap, x-height and ascender lines.
- Stray ink removed: ruled-line stubs, lines through letters, blots.
- Strokes where the pen lifted early were finished to the line.
- Hurried copies skipped; the most typical copy kept.

### Pipeline

- `python tools/pipeline.py --round N` runs a whole round.
- Review sorts findings into: auto-fixed, fixable in code,
  needs handwriting, your decision.
- Handover writes a PDF of what to write next.
- See `PIPELINE.md`.

### Known gaps (round 1, score 44/100)

- Most symbols have only 1 copy.
- C, V, u, y, 2, 4: size varies between copies.
- A was hand-picked; confirm it.
- No kerning yet.
- Next step: fill in `iterations/round-1/write-next.pdf`.
