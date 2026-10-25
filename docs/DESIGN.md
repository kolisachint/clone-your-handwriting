# Design: Clone Your Handwriting

Status: **draft v2, decisions recorded**. No code changes until this is agreed.
Date: 2026-10-25. Base: `main` at v0.4.0 (AnnaHand).

## 0. Decisions (2026-10-25)

| # | Question | Decision |
|---|----------|----------|
| D1 | Name | **Clone Your Handwriting**. Repo `clone-your-handwriting`, Python package `clone-your-handwriting`, import `cyh`, command `cyh` |
| D2 | AnnaHand | Stays in this repo as the **example writer** (`writers/anna/`) |
| D3 | License | **MIT** for code. Fonts default to OFL-1.1 (section 9) |
| D4 | Capture | **Template and freeform are both first-class**. The writer picks whichever is comfortable and can mix them |
| D5 | Personal data | **Remove every personal item**. Existing photos are removed; the owner supplies new photos for the next phase (section 8) |
| D6 | Mono / Nerd Font | **Dropped**. Handwriting is not monospaced. AnnaHandNerdMono is removed after v0.4.0 |
| D7 | Agents | **Opt-in** in the template repo; the pipeline works without them |
| D8 | Charset v1 | ASCII 94 + `₹ € £ ¥ —` (Latin-Ext accents come next). *Assumed from "yes"; confirm* |
| D9 | Built fonts | Example fonts are **committed and published as release zips**, so they work as both showcase and test fixture |
| D10 | Templates | Specify every template: writer kit, template repo, issue/PR templates, contributing, license, quality bar (sections 6–10) |

## 1. Goal

Anyone can turn photos of their own handwriting into installable fonts, and
improve them round by round, with the same quality loop AnnaHand went through.

**Hybrid** means two ways in and one engine:

- **Local**: `pipx install clone-your-handwriting`, run `cyh` on your laptop.
  Photos never leave your machine.
- **GitHub**: create your own repo from the template. Upload photos, and
  Actions build, review and open a "Round N" PR with the report and the
  "write next" sheet.

**Community** contributions improve the engine (capture, cleanup, styles,
checks, packaging, charsets). Each person's handwriting lives in their own
repo, and adding it to the gallery is opt-in.

Non-goals for v1: joined-up cursive with contextual ligatures, non-Latin scripts,
a hosted web app, monospaced styles.

## 2. Where the repo is today

Carries over as-is:

- A full round loop: build → judge → 4 outcome groups → handover PDF → writer writes → next round.
- A glyph engine: vectorize, build (OTF/TTF/WOFF2/WOFF/CSS), strokes, cleanup,
  stroke completion, deskew.
- Review and handover (`judge.py`, `handover.py`; report.json is a clean contract).
- Packaging for 6 surfaces (web, desktop, iOS profile, Android, Office, design).
- 4 handwriting styles: hand, paper, typed, access.

Blockers to "anyone":

| # | Blocker | Where |
|---|---------|-------|
| B1 | Letters are found by hand-written per-photo specs (pixel crop, rotation, row index, token strings that must match ink-group counts) | `specs.py`, `extract.py` |
| B2 | Sentence pages need hard-coded transcriptions; a two-page spread is assumed | `words.py` PAGES |
| B3 | Ink mask only sees blue pen; PEN_B and LINE_B were measured on these photos | `seg.py`, `cleanup.py` |
| B4 | Per-letter overrides keyed on file names and row numbers | `make.py` |
| B5 | `AnnaHand` name, `com.annahand.*` IDs, demo text and blurbs | `pipeline.py`, `package.py`, `review.py`, `handover.py` |
| B6 | Scripts do their work at import time and depend on the working directory | `extract.py`, `words.py`, `make.py` |
| B7 | macOS font paths and `/tmp` paths | 10 files (appendix) |
| B8 | Pickle between stages: unsafe to accept from strangers | `*.pkl` |
| B9 | 3 version sources; no LICENSE; no copyright or license in the font name table | `__init__.py`, `make.py`, `build.py` |
| B10 | No end-to-end test; some tests need `/tmp` fixtures | `tools/test_*.py` |
| B11 | Personal data in text, PDF metadata, photos and history | section 8 |

`handfont/layout.py` already describes the printable template (ArUco markers,
fixed cells). It was never built; it is the fix for B1.

## 3. Target architecture

```
clone-your-handwriting/
├─ cyh/                          ← engine package (no writer-specific code)
│  ├─ cli.py                     ← cyh new | kit | add | round | package | check
│  ├─ config.py                  ← writer.yaml + overrides.yaml schema
│  ├─ capture/
│  │  ├─ template.py             ← printable sheets from a charset (PDF)
│  │  ├─ scan.py                 ← find markers, unwarp, cut cells
│  │  ├─ freeform.py             ← sentence pages + known text (generalised words.py)
│  │  └─ legacy_specs.py         ← old SPECS format, read-only, for history
│  ├─ ink.py                     ← pen, paper and ruling colour per photo (any pen)
│  ├─ samples.py                 ← Sample type; PNG + samples.json, no pickle
│  ├─ select.py  normalize.py  cleanup.py  complete.py  strokes.py
│  ├─ styles/  hand.py paper.py typed.py access.py   (registry; new styles = new file)
│  ├─ vectorize.py  build.py
│  ├─ judge.py  handover.py  preview.py
│  ├─ package.py                 ← family, IDs, blurbs from writer.yaml
│  ├─ charsets/  ascii.yaml  currency.yaml  latin-ext.yaml (later)
│  └─ assets/fonts/              ← bundled open font for PDFs and previews
├─ writers/anna/                 ← the example writer
│  ├─ writer.yaml  overrides.yaml  pages.yaml
│  ├─ photos/<date>/             ← new photos supplied by the owner (D5)
│  ├─ rounds/round-N/            ← report.md, report.json, facts.json, write-next.pdf
│  ├─ fonts/<Family>/            ← committed (D9)
│  └─ previews/
├─ template-repo/                ← copied into every "create your own" repo
├─ gallery/index.yaml            ← opt-in published writers
├─ tests/  fixtures/synthetic/   ← no real person's data in CI
├─ docs/   writer-guide.md  contributor-guide.md  quality.md  privacy.md
└─ LICENSE  CONTRIBUTING.md  CODE_OF_CONDUCT.md  SECURITY.md  .github/
```

Rule: **engine code knows nothing about a writer.** Everything writer-specific
lives in `writers/<slug>/`, or in the person's own repo with the same layout.

### 3.1 `writer.yaml`

```yaml
slug: anna
family: AnnaHand                  # styles append Paper, Typed, Access
display_name: Anna                # pseudonym allowed and encouraged
copyright: "© 2026 The AnnaHand authors"
font_license: OFL-1.1
photo_license: none               # none | CC-BY-4.0  (photos are never required upstream)
version: 0.5.0                    # the font version; single source
id_prefix: io.github.<owner>.annahand
capture: [template, freeform]     # either or both (D4)
charset: [ascii, currency]
ink: auto                         # or a calibration block written by `cyh check`
styles: [hand, paper, typed, access]
style_options:
  access: {slashed_zero: true}
  typed:  {prefer_alphabet: "tgy"}
sample_text: "The quick brown fox jumps over the lazy dog."
```

### 3.2 `overrides.yaml`

These point to stable sample ids, not code:

```yaml
pick:            {A: "2026-11-01/IMG_0001#c12"}
exclude:         ["2026-11-01/IMG_0003#r4"]
expect_pieces:   {i: 2, j: 2, "%": 3}
prefer_alphabet: [I]
```

"Your decision" findings in the report become a suggested diff to this file.

### 3.3 Samples without pickle

`samples/` holds one PNG mask per sample plus `samples.json` (char, source,
cell or row, baseline, cap, slope, `schema_version`). It is safe to accept in a PR
and diffs cleanly. One release ships a converter from the old pickle, for migration only.

## 4. Capture: template or freeform (D4)

The writer chooses. Both feed the same samples, and they can be mixed.

| | **Template** | **Freeform** |
|---|---|---|
| Writer does | `cyh kit` → print sheets with corner markers and boxed cells (faint guide letter + baseline). Write each letter 3 times. Photograph | `cyh kit --freeform` → a prompt sheet of pangrams and symbol sentences. Write them on **any** paper. Photograph |
| Labelling | None: page id + cell = character | None: the tool supplied the text. Words that fail to align are skipped and reported |
| Good for | Fastest to a full charset; even size and baseline | Natural shapes; people with no printer; notebooks |
| Round 2+ | `write-next.pdf` is a template with only the missing or weak characters | `write-next.pdf` is a prompt sheet with words built from the weak characters |

- Template: A4 or Letter, ArUco DICT_4X4_50, page id in the markers, so photos
  can arrive in any order or rotation.
- Freeform: the generalised `words.py` alignment. Prompt text comes from
  `pages.yaml` (pre-filled by `cyh kit`). Spread, rotation and margins are options, not constants.
- Writer tips are printed on the kit: daylight, no shadow, page flat and
  filling the frame, one pen for the whole kit.

### 4.1 Any pen, any paper

`ink.py` clusters each photo in Lab colour: paper = brightest large cluster,
pen = dark dense strokes, ruling = thin long periodic lines. This replaces
the blue-hue mask, which is kept only as a regression detector. `cyh check
photos/` reports per photo: ink found, ruling found, blur, tilt, resolution, pass or fail.

## 5. Hybrid workflow

### 5.1 Local

```
pipx install clone-your-handwriting
cyh new myhand                # writers/myhand/ with writer.yaml
cyh kit                       # template.pdf and/or prompts.pdf
cyh add ~/Pictures/*.jpg      # copy to photos/<date>/, strip EXIF, check quality
cyh round                     # build → judge → report.md + write-next.pdf
cyh package                   # dist/ zips for every surface
```

### 5.2 GitHub (your own repo)

1. **Use this template** on `clone-your-handwriting-template`. It is private by default.
2. Edit `writer.yaml` in the browser, then upload photos to `photos/<date>/`.
3. `round.yml` builds and judges, then opens a **"Round N" PR**: report as the body,
   preview images, `write-next.pdf` as an artifact.
4. Merge = accept the round. Tag `v*` = release with zips.
5. The engine is pinned (`cyh==X.Y`). Dependabot proposes upgrades, and the PR
   shows before/after previews.

### 5.3 Contributing upstream

| Contribution | Where | Gate |
|---|---|---|
| Engine fix or feature | `cyh/` | Unit tests + golden tests (section 10) |
| New style | `cyh/styles/<name>.py` + preview | Golden tests + style review |
| New judge check | `judge.py` + test | Must map to one of the 4 outcome groups |
| New surface | `package.py` | Install notes + manual checklist |
| Charset or locale | `cyh/charsets/*.yaml` | Template renders; judge knows the set |
| Gallery entry | `gallery/index.yaml` (link only) | Consent, font license, quality tier ≥ Preview |
| Test fixture | `tests/fixtures/<id>/` | Explicit consent, no personal text, PNG + JSON only |

## 6. Agent roles (opt-in, D7)

| Task | Model |
|---|---|
| Round summary and PR body from report.json | Haiku |
| Issue triage and labelling with an outcome group | Haiku |
| Draft `pages.yaml` or check a transcription | Haiku |
| Docs, changelog, gallery entry checks | Haiku |
| "Fixable in code" → propose an `overrides.yaml` or knob change | Sonnet |
| Engine PRs and review of community PRs | Sonnet |
| "Your decision" options with trade-offs | Sonnet |

In the template repo the agents run via the Claude GitHub Action when the owner
adds it. Nothing in the pipeline depends on them.

## 7. Templates to add (D10)

### 7.1 Upstream repo

| File | Content |
|---|---|
| `LICENSE` | MIT, "Copyright (c) 2026 Clone Your Handwriting contributors" |
| `writers/anna/fonts/OFL.txt` | SIL OFL 1.1 for the example fonts |
| `CONTRIBUTING.md` | Setup; how to run tests; the golden-test rule; what goes upstream vs your own repo; never commit personal photos; commit style; DCO sign-off (`git commit -s`) |
| `CODE_OF_CONDUCT.md` | Contributor Covenant 2.1 |
| `SECURITY.md` | How to report; no pickle/eval of contributed data; where photos go |
| `docs/privacy.md` | What counts as personal; EXIF; practice text rules; consent for fixtures/gallery |
| `docs/quality.md` | Section 10 in full |
| `docs/writer-guide.md` | Kit, photo tips, reading the report, the 4 outcome groups |
| `docs/contributor-guide.md` | Architecture (section 3), adding a style, check or charset |
| `.github/ISSUE_TEMPLATE/bug.yml` | Engine version, OS, command, log, sample (no personal photo) |
| `.github/ISSUE_TEMPLATE/glyph.yml` | Character, style, screenshot, expected vs actual, outcome group guess |
| `.github/ISSUE_TEMPLATE/style.yml` | New style proposal: purpose, preview, accessibility notes |
| `.github/ISSUE_TEMPLATE/gallery.yml` | Repo link, font license, consent checkbox, quality tier |
| `.github/ISSUE_TEMPLATE/config.yml` | Discussions link for questions |
| `.github/PULL_REQUEST_TEMPLATE.md` | What/why; outcome group affected; golden test diff; preview before/after; checklist (tests, docs, no personal data, DCO) |
| `.github/CODEOWNERS` | Engine areas → maintainers; `writers/anna/` → owner |
| `.github/labels.yml` | `auto-fixed`, `fixable-in-code`, `needs-handwriting`, `your-decision`, `engine`, `style`, `capture`, `good first issue` |
| `.github/workflows/ci.yml` | Lint, unit tests, synthetic golden test; Linux/macOS/Windows × Py 3.10–3.13 |
| `.github/workflows/release.yml` | Engine to PyPI on `engine-v*`; example fonts on `anna-v*` |
| `.github/dependabot.yml` | pip + actions |

### 7.2 Template repo (`template-repo/` → `clone-your-handwriting-template`)

| File | Content |
|---|---|
| `README.md` | Your font in 4 steps; filled in by `round.yml` with previews and install links |
| `writer.yaml` | Section 3.1 with placeholders and comments |
| `overrides.yaml` | Empty with commented examples |
| `photos/README.md` | Where to put photos; tips; privacy reminder |
| `FONT-LICENSE.txt` | OFL 1.1 pre-filled from `writer.yaml` |
| `.github/workflows/round.yml` | On push to `photos/**` or `*.yaml`: `cyh round` → PR |
| `.github/workflows/release.yml` | On `v*`: `cyh package` → release zips |
| `.github/workflows/claude.yml.example` | Opt-in agents (rename to enable) |
| `.gitignore` | `dist/`, caches, raw exports |

### 7.3 Writer kit (generated by `cyh kit`)

- `template.pdf`: cells for the charset, 3 copies each, with markers and guides.
- `prompts.pdf`: pangrams + symbol sentences with **no personal data** (dummy
  numbers like `555-0100`, emails at `example.com`).
- `photo-tips.pdf`: one page with pictures of good vs bad photos.

## 8. Privacy clean-up (D5)

Audit done 2026-10-25 (text, metadata, history, photos).

**Photos** (`handwriting/2026-10-10/`, 5 files): the content is pangrams,
alphabets, symbols and dummy text (the "phone number" is the sequence 9876543210,
the email is `hello@mail.com`). There is no EXIF or GPS. Still identifying:
**fingers visible** in IMG_0077 and IMG_0079, a small handwritten word above
the header of IMG_0081, and the handwriting itself. The JPEG comment shows the
photos were re-encoded through Discord.

| Item | Where | Action |
|---|---|---|
| Writer's real name | `README.md:10` | Replace with "Anna" (pseudonym) |
| Photos | `handwriting/2026-10-10/*.jpg` | **Remove**; new photos from the owner in Phase 2 |
| Samples cut from photos | `tools/word_samples.pkl` | Remove (rebuilt from new photos, as PNG + JSON) |
| Fonts and previews from old photos | `fonts/`, `previews/` | Keep until rebuilt from new photos, then replace (the v0.4.0 release stays as it was) |
| Facts with old file names | `iterations/round-1/*` | Keep as history, or remove with the photos (owner's call) |
| Dummy phone, date, price, email | `words.py:60-61,78`, `prev.py:6`, `review.py:10` | Replace with `555-0100`, `example.com` and a neutral date |
| Discord handle in writer instructions | `handover.py:45,97`, `PIPELINE.md:110` | "Send it to the project maintainer" / `@example` |
| PDF author metadata | `handover.py:355`, `write-next.pdf` | Author = "Clone Your Handwriting"; regenerate |
| PDF creation time zone | `write-next.pdf` | Write PDFs without CreationDate (reproducible builds) |
| Commit identity | Git history: a local machine hostname as committer email on ~10 commits | Optional: set a GitHub noreply email from now on; rewriting history is a separate decision |
| Old content in history | Photos, real name, dummy strings in past commits | **Decision P1** |

**Decision P1: rewrite git history?** Deleting files from `main` does not
remove them from past commits, forks or clones. If the old photos or the real
name must be gone entirely, run `git filter-repo` on a fresh clone, force-push
every branch and tag, and re-create the v0.3.x/v0.4.0 releases. That breaks
existing clones and PR links. Recommendation: **yes, once, in Phase 0 before
any announcement**. It needs your explicit go-ahead at the time.

Engine safeguards so this does not recur: `cyh add` strips EXIF; prompts contain
only dummy data; `cyh check --privacy` warns on emails or phone patterns in
`pages.yaml`; CI on upstream rejects new files under `photos/` outside `writers/anna/`.

## 9. Licensing

| What | License | Notes |
|---|---|---|
| Engine code, workflows, templates | MIT | Root `LICENSE` |
| Example fonts (AnnaHand family) | OFL-1.1 | Name table IDs 0, 13, 14 filled; `OFL.txt` shipped in every zip |
| A user's own fonts | Their choice; OFL-1.1 default in the template | `writer.yaml: font_license` |
| Example photos (new) | **Decision P2**: CC-BY-4.0, or "all rights reserved, for this project only" | Never required upstream for other writers |
| Bundled preview font | Its own license (e.g. DejaVu/Bitstream Vera) | Shipped in `cyh/assets/fonts/` with its license |
| Contributions | MIT via DCO sign-off | No CLA |

Also drop `fonts/AnnaHandNerdMono/LICENSE-NerdFonts` along with Nerd Mono (D6).

## 10. What good looks like (quality bar)

Measured by `cyh round` (judge) and shown in every report and round PR.

### 10.1 Per glyph

| Check | Good | Why |
|---|---|---|
| Samples | ≥ 3 copies (letters, digits), ≥ 2 (symbols) | Medoid pick needs choice |
| Pieces | = expected (`i` 2, `%` 3…) | Catches broken or merged strokes |
| Loose ends | ≤ expected + 2 | Hurried or broken strokes |
| Size correction | within ±15% | Bigger means the copy was not typical |
| Baseline | on the writer's line ±3% of cap height; descenders below | Text sits straight |
| Stroke completion | ≤ 10% of the glyph's ink added | Mostly the writer's own ink |
| Stray ink | no component < 2% of glyph area left | Clean outlines |

### 10.2 Per font

| Check | Preview | Release | Example |
|---|---|---|---|
| Charset coverage | ≥ 95% | 100% of `charset` | 100% |
| Judge score | ≥ 60 | ≥ 80 | ≥ 85 |
| High-severity issues | any | 0 | 0 |
| Confusables (O/0, l/1/I, rn/m) | report | pass in Access | pass in Access and Typed |
| Metadata (name, version, copyright, license) | complete | complete | complete |
| Font validity (fontTools + OTS sanitiser) | pass | pass | pass |
| Installs on 6 surfaces | – | checklist | checklist + screenshots |
| Human read test (paragraph at 12 px and 24 px) | – | writer signs off | writer + maintainer sign off |

AnnaHand round 1 scored 44, so it is not yet at Preview. Reaching
**Example** tier with the new photos is the Phase 2 exit goal.

### 10.3 Per contribution

- Golden tests: synthetic fixture exact; AnnaHand metrics within tolerance
  (advance ±2 units, bbox ±5 units, score ±1), unless the PR states the intended change and updates the goldens.
- Before/after preview image in the PR.
- Docs updated when behaviour or commands change.
- No personal data; DCO sign-off.

## 11. Phases

| Phase | Scope | Exit |
|---|---|---|
| **0. Hygiene + privacy** | MIT LICENSE; one version source; remove macOS and `/tmp` paths; bundle preview font; fixtures into `tests/`; dead experiments to `tools/dev/`; **drop Nerd Mono**; privacy fixes (section 8); remove old photos; P1 history rewrite if approved | CI green, no skips; privacy check clean |
| **1. Engine refactor** | `cyh` package + CLI; `writer.yaml`, `overrides.yaml`; PNG+JSON samples; parameterised package/handover/preview; move to `writers/anna/` | `cyh round --writer anna` reproduces current AnnaHand within tolerance (from cached samples) |
| **2. Capture** | Template kit + scan; freeform kit + generalised alignment; `ink.py`; `cyh check`. **Owner supplies new photos** with both kits | New AnnaHand built only from new photos; Example tier |
| **3. Template repo** | `template-repo/`, `round.yml`, release, private default, engine pinning | A new user gets from template to round-1 PR with no local install |
| **4. Community** | All section 7 files, labels, gallery, opt-in agents, PyPI release | First outside contribution merged |

## 12. Still open

- **P1** Rewrite git history to purge old photos and name (recommended: yes, Phase 0).
- **P2** License for the new example photos (CC-BY-4.0 vs project-only).
- **D8** Confirm the v1 charset reading (ASCII + `₹ € £ ¥ —`; accents next).
- Keep or remove `iterations/round-1/` history once the photos are gone.
- Maintainer contact for writer instructions and SECURITY.md (an email or GitHub Discussions).

## Appendix: hard-coding audit (condensed)

- **Names/IDs**: `pipeline.py:46-52`; `package.py:30-47, 380-412, 576-585`;
  `review.py:5-13`; `handover.py:7, 45, 325, 355, 377`; `nerd_mono.py` (to be removed).
- **Paths**: `extract.py:7`, `words.py:21`; make.py reads pickles from the working directory; macOS
  fonts in `handover.py:26`, `review.py:4`, `sheet.py:7`, `cands.py:7`,
  `before_after.py:6`, `words.py:401`, `test_judge.py:164`; `/tmp` in
  `test_geometry.py:11`, `test_judge.py:16`, `prev.py`.
- **Photo data**: `specs.py:8-36`; `words.py:26-89`; `seg.py:54`.
- **Per-letter tuning**: `make.py:18-22, 44-50`; `cleanup.py:29-30`;
  `seg.py:8-10`; `judge.py:41-51` (some thresholds are absolute pixels).
- **Metadata**: `build.py:146-160` (no IDs 0/13/14), vendor `HFNT`; versions in
  `__init__.py:3`, `build.py:236`, `make.py:114`.
- **Charset**: `layout.py:31-35` (94 ASCII); extra symbols only via SPECS;
  backtick missing; `:` and `_` synthesised (`make.py:180-185`).
- **Carried-over font issues**: single-copy symbols; size spread in C V u y 2 4;
  `_` 0 samples; no kerning; round-1 count mismatch (98/99/97).
