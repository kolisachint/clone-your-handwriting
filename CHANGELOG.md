# Changelog

## v0.4.0 — 2026-10-10

### Added

- AnnaHandNerdMono, a 5th style: AnnaHand in monospace.
  Every character is the same width (600 of 1000 units);
  wide letters are squeezed to fit.
- About 10,000 Nerd Font icons: Powerline, Font Awesome, Devicons,
  Octicons, Material and more.
- For terminals (Ghostty, iTerm, Kitty, WezTerm), code editors
  (VS Code), and prompts (powerlevel10k, starship).
- Formats: OTF, TTF, WOFF2, WOFF, CSS.
- Included in every bundle: web, desktop, iOS profile, Android,
  Office, design apps.
- New tool: `tools/nerd_mono.py`. Needs `--symbols` with
  `SymbolsNerdFontMono-Regular.ttf`.
- Bundles now include each font family's LICENSE file.

### Credits

- Icons from Nerd Fonts (MIT / SIL OFL).
  License: `fonts/AnnaHandNerdMono/LICENSE-NerdFonts`.

## v0.3.1 — 2026-10-10

### Fixed

- iOS profile: iOS said the fonts were invalid.
  Each font is now stored under the `Font` key, as iOS expects.
  Remove the old AnnaHand profile, then install the new one.

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
