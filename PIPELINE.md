# AnnaHand pipeline

One command runs a whole round:

    python tools/pipeline.py --round N

Run it from the repo root.

## Setup (once)

    python3 -m venv .venv && . .venv/bin/activate
    pip install -r tools/requirements.txt pytest pymupdf

## The loop

- Build
- Review
- Fix
- Hand over
- Writer writes
- Add photos
- Next round

## Four outcome categories

Every finding in report.md is in one of four groups.
Each group says who acts.

### 1. Auto-fixed

- Meaning: the pipeline fixed it. The judge saw it and the build dealt with it.
- Who acts: nobody.

### 2. Fixable in code

- Meaning: a rule in the tools is too strict or too loose.
- Who acts: the bot or a developer. Only tools/ changes. No handwriting.
- Known knobs:
  - tools/cleanup.py: `PEN_B`, `LINE_B`. Ink colour that counts as pen or ruled line.
  - tools/make.py: `OVERRIDE` (hand-picked copy for a letter),
    `PREFER_ALPHA` (copy of I), `PREFER_ALPHA_CLEAR` (t, g, y for Typed and Access),
    `EXPECT` (how many pieces a letter has).
  - tools/complete.py: `MAX_BEND` (15 degrees max bend when finishing a
    stroke), and the travel limit of 0.30 of cap height.
  - tools/specs.py: `SPECS` rows. Which letter sits in which spot on each photo.

### 3. Needs handwriting

- Meaning: the writer must write something again.
- Who acts: the writer.
- Action: send iterations/round-N/write-next.pdf.

### 4. Your decision

- Meaning: a style choice that no rule can make for you.
- Who acts: you.
- Example: should t be the textbook t or a plus-like cross?
  The setting is `PREFER_ALPHA_CLEAR` in tools/make.py.

## Start a new round

1. Put the new photos in `handwriting/<YYYY-MM-DD>/`.
2. Alphabet pages: add rows to `SPECS` in `tools/specs.py`.
3. Sentence pages: add the transcription to `PAGES` in `tools/words.py`.
4. From the repo root, run:

       python tools/pipeline.py --round N --words

   Use `N` = the next round number.
   `--words` is slow. Leave it out if you only added alphabet pages.
5. Read `iterations/round-N/report.md`.
6. Send `iterations/round-N/write-next.pdf` to the writer.

## Stages and files

Each stage reads some files and writes others.

- `handwriting/<date>/*.jpg`: the photos. Read by extract.py and words.py.
- `tools/specs.py`: row specs for alphabet photos. Read by extract.py.
- `tools/extract.py`: writes `tools/samples.pkl` (alphabet samples).
  Not committed (ignored by git).
- `tools/words.py`: writes `tools/word_samples.pkl` (sentence samples).
  Committed.
- `tools/make.py` (4 styles): reads both .pkl files. Writes
  `fonts/<Family>/` with OTF, TTF, WOFF2, WOFF and CSS.
  The hand style also writes `iterations/round-N/facts.json` (per glyph).
- `tools/judge.py` (or `tools/review_report.py`): reads facts.json and
  `fonts/AnnaHand/AnnaHand-Regular.ttf`. Writes
  `iterations/round-N/report.json` and `report.md`.
- `tools/handover.py`: reads report.json. Writes
  `iterations/round-N/write-next.pdf`.
- `tools/review.py`: reads a folder of style folders. Writes `previews/styles.png`.
- `tools/package.py`: reads `fonts/`. Writes `dist/` (ignored by git).
- `tools/pipeline.py`: writes `iterations/round-N/README.md`.

What stays tracked in git: `fonts/`, `previews/`, `iterations/`,
`tools/word_samples.pkl`, and the photos.

### What report.json needs

pipeline.py reads these keys. Anything else is ignored.

- `score`: a number or a short string.
- `counts`: an object. Keys are category names
  (auto-fixed, fixable-in-code, needs-handwriting, decide). Values are numbers.
- If there is no `counts`, pipeline.py counts the items in `items`
  (or `findings`, `checks`, `issues`, `results`). It reads each item's
  `category`, `outcome`, `action`, `status` or `bucket` field.

## For the bot: run a round with Haiku subagents

Use this when the user asks for a round. Use the "fast" category for workers.

1. Run the round (step 4 above) with the new round number N.
2. Worker A (reads only): read `iterations/round-N/report.md` and the
   contact sheets (`tools/sheet.py` makes one). Return a list:
   each finding, its category, and the file or glyph it touches.
   Do not edit anything.
3. Worker B (edits): take only the "Fixable in code" items from Worker A.
   Change only the knobs listed above. Do not change the photos,
   the fonts or the round folders.
   Do not commit.
4. If Worker B changed code, run the round again with N+1
   and `--skip-extract` (samples.pkl is kept).
5. Manager (you) checks it by eye before any PR:
   - open `previews/styles.png`,
   - open the new contact sheet,
   - compare the letters that changed with round N.
6. Items in "Needs handwriting" or "Your decision" are never guessed.
   Put them in the summary for the user.
7. Open a PR only if the user asked for one.
   Never commit or push on your own.

## Round 1 (2026-10-10) — where we are

- Score 44 / 100. See `iterations/round-1/report.md`.
- Fixed in code this round: `f` now sits on the line;
  x-height in the font now matches the handwriting (`n` was 18% off).
- Next: the writer fills in `iterations/round-1/write-next.pdf`.
  Mostly symbols (only 1 copy each) plus C, V, u, y, 2, 4.
