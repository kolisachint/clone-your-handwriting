# Design: Clone Your Handwriting (from one writer to everyone)

Status: **draft for discussion**. No code changes until this is agreed.
Date: 2026-10-25. Base: `main` at v0.4.0 (AnnaHand).

## 1. Goal

Anyone can turn photos of their own handwriting into a set of installable
fonts, round by round, with the same quality loop AnnaHand got.

Hybrid means two ways in, one engine:

- **Local**: install the tool, run it on your laptop. Your photos never leave
  your machine.
- **GitHub**: create your own repo from a template. Push photos, and Actions
  build the fonts, review them, and post the "write next" sheet.

Community contributions improve the **engine**: better segmentation, cleanup,
styles, checks and surfaces. Each person's handwriting stays in their own repo,
unless they choose to add it to the gallery.

Non-goals for v1: cursive and joined-up writing with real ligatures, non-Latin
scripts, a hosted web app.

## 2. Where the repo is today

What already works and carries over as-is:

- A full round loop: build → judge → 4 outcome groups → handover PDF → writer
  writes → next round (`tools/pipeline.py`, `PIPELINE.md`).
- A solid glyph engine: `handfont/vectorize.py`, `handfont/build.py`
  (OTF/TTF/WOFF2/WOFF/CSS), `strokes.py`, `cleanup.py`, `complete.py`,
  `geometry.py`.
- Review and handover: `judge.py`, `handover.py` (report.json is a clean
  contract).
- Packaging for 6 surfaces: `package.py`, including the iOS profile fix from v0.3.1.
- 5 styles, plus Nerd Mono as a post-processor.

What ties it to one writer (full audit: section 11):

| # | Blocker | Where |
|---|---------|-------|
| B1 | Letters are found by **hand-written per-photo specs**: pixel crop, rotation, row index, and token strings that must match the ink-group count exactly | `specs.py`, `extract.py` |
| B2 | Sentence pages need hard-coded transcriptions and assume a two-page spread | `words.py` `PAGES` |
| B3 | Ink mask only sees **blue pen** (hue 100–140). PEN_B and LINE_B were measured on these photos | `seg.py`, `cleanup.py` |
| B4 | Per-letter overrides keyed on file names and row numbers | `make.py` EXCLUDE, BAD_ROWS, OVERRIDE, EXPECT, PREFER_ALPHA* |
| B5 | Name `AnnaHand`, `com.annahand.*` IDs, demo text and blurbs | `pipeline.py`, `package.py`, `nerd_mono.py`, `review.py`, `handover.py` |
| B6 | Scripts do their work at import time and depend on the working directory | `extract.py`, `words.py`, `make.py` |
| B7 | macOS font paths and `/tmp` paths in tools and tests | handover, review, sheet, prev, words, cands, before_after, test_judge, test_geometry, nerd_mono |
| B8 | **Pickle** is the format between stages. It is unsafe to load from strangers and tied to numpy versions | `samples.pkl`, `word_samples.pkl` |
| B9 | Versions in 3 places (0.1.0, 0.3.0, v0.4.0). No root LICENSE. No copyright or license in the font name table | `__init__.py`, `make.py`, `build.py` |
| B10 | No end-to-end test. CI skips the tests that need `/tmp` fixtures | `tools/test_*.py`, `ci.yml` |

Good news: `handfont/layout.py` already describes a **printable template with
ArUco corner markers and fixed cells**. It was never built, but it is exactly
the fix for B1 and B2.

## 3. Target architecture

```
clone-your-handwriting/            ← upstream: engine + docs + gallery
├─ handfont/                       ← installable package (pip install handfont)
│  ├─ cli.py                       ← `handfont …` commands (section 5)
│  ├─ config.py                    ← writer.yaml schema + validation
│  ├─ capture/
│  │  ├─ template.py               ← make printable sheets (PDF) from a charset
│  │  ├─ scan.py                   ← find markers, unwarp, cut cells
│  │  ├─ freeform.py               ← sentence pages + transcription (today's words.py)
│  │  └─ legacy_specs.py           ← today's SPECS path, kept for AnnaHand
│  ├─ ink.py                       ← ink/paper/ruling colour from the photos (replaces blue-only)
│  ├─ samples.py                   ← Sample type, save/load as PNG + JSON (no pickle)
│  ├─ select.py                    ← group, medoid pick, overrides by sample id
│  ├─ normalize.py                 ← deskew, sizing to the writer's lines (geometry + norm_scale)
│  ├─ cleanup.py  complete.py  strokes.py
│  ├─ styles/                      ← one file per style; a registry
│  │  ├─ hand.py paper.py typed.py access.py
│  │  └─ mono.py  (+ nerd icons as an optional add-on)
│  ├─ vectorize.py  build.py
│  ├─ judge.py  handover.py
│  ├─ package.py                   ← takes family name, IDs and blurbs from writer.yaml
│  └─ assets/fonts/                ← bundled open font (e.g. DejaVu Sans) for PDFs and previews
├─ writers/
│  └─ anna/                        ← reference writer + regression fixture
│     ├─ writer.yaml
│     ├─ photos/2026-10-10/*.jpg
│     ├─ capture/legacy_specs.yaml  pages.yaml
│     ├─ overrides.yaml
│     ├─ rounds/round-1/…          ← today's iterations/
│     └─ fonts/…
├─ template-repo/                  ← files copied into "create your own" repos
├─ gallery/index.yaml              ← opt-in list of published writers
└─ tests/  (unit + golden end-to-end on a small fixture)
```

The main idea: **engine code knows nothing about a writer.** Everything
writer-specific lives in `writers/<slug>/`, or in the person's own repo with
the same layout.

### 3.1 `writer.yaml` (the one file a new person edits)

```yaml
slug: anna
family: AnnaHand                  # base family; styles append Paper, Typed, …
display_name: "Anna"              # optional; may be a pseudonym
copyright: "© 2026 Anna"
license: OFL-1.1                  # font license (default)
version: 0.4.0                    # single source of truth
id_prefix: com.annahand           # iOS profile IDs
capture: legacy_specs             # template | freeform | legacy_specs (can list several)
charset: ascii+symbols            # named sets or explicit list
ink: auto                         # or {pen_b: 108, line_b: 114} after calibration
styles: [hand, paper, typed, access, mono]
style_options:
  access: {slashed_zero: true}
  typed:  {prefer_alpha: "tgy"}
sample_text: "Dear reader, …"     # demo page text
```

### 3.2 `overrides.yaml` (replaces the per-letter code in make.py)

Overrides point to **stable sample ids** (`<photo>#<cell or row>`), not to code:

```yaml
pick:     {A: "2026-10-10/IMG_0077#r0"}
exclude:  ["2026-10-10/IMG_0080#r208"]
expect_pieces: {i: 2, j: 2, "%": 3}
prefer_alphabet: [I]
```

The "your decision" outcome in report.md becomes a suggested edit to this file.

### 3.3 Samples without pickle (B8)

`samples/` holds one PNG mask per sample plus `samples.json`, which lists
char, source, row or cell, baseline, cap and slope. The format is safe to
accept in a PR, diffable, and has a `schema_version`. A loader for the old
pickle stays for one release, for migration only.

## 4. Capture: how letters are found

This is the heart of "for everyone". Three paths, which can be combined:

| Path | What the writer does | Labelling effort | Quality |
|------|---------------------|------------------|---------|
| **A. Template** (new default) | `handfont template` prints sheets with corner markers and a grid of boxed cells, each with a faint guide letter and baseline. Write each letter 2–3 times, then photograph | **None**: the cell position says which letter it is | Best. Consistent size and baseline |
| **B. Freeform** | Write given pangrams or sentences on any paper. The transcription is known because the tool supplied the text | Low: text is pre-filled. Words that fail to align are skipped | Adds natural letter shapes from real writing |
| **C. Legacy specs** | Today's notebook flow with SPECS | High | Keeps AnnaHand reproducible |

- Path A uses `layout.py` as the contract: A4/Letter, 300 DPI, ArUco
  DICT_4X4_50, and a page id encoded in the markers. Page id plus cell gives
  the character, so photos can come in any order or rotation.
- The handover PDF (`write-next.pdf`) becomes a Path A sheet with
  only the characters that need more copies. That closes the loop with no
  labelling at all.
- Path B reuses `words.py` alignment, with PAGES moved to `pages.yaml` and
  the two-page-spread and rotation assumptions made into options.
- `handfont label` (optional, later): a small local web page to fix
  mis-detected groups, for people who insist on notebook photos.

### 4.1 Ink and paper (B3)

`ink.py` estimates paper, pen and ruling colours per photo by clustering in
Lab colour space. Pen = darkest and least frequent dense cluster; ruling =
thin, long, periodic lines. It writes the result into the round's facts, and
optionally into `writer.yaml` after the first run. Black, blue and coloured
pens on plain, ruled or squared paper all go through one code path. The
blue-hue mask stays as one detector, for regression testing against AnnaHand.

## 5. Hybrid workflow

### 5.1 Local

```
pipx install handfont
handfont new mywriting           # makes writers/mywriting/ with writer.yaml
handfont template                # → sheets.pdf; print, write, photograph
handfont add photos/*.jpg        # copies into photos/<date>/, strips EXIF
handfont round                   # build → judge → report.md + write-next.pdf
handfont package                 # dist/ zips for every surface
```

`handfont round` is today's `pipeline.py` with no hard-coded families.

### 5.2 GitHub (your own repo)

1. Click **"Use this template"** on a `clone-your-handwriting-template` repo
   (generated from `template-repo/`).
2. Edit `writer.yaml`, then upload photos to `photos/<date>/` through the web
   UI or the mobile app. No local Python needed.
3. The **`round.yml`** Action builds, judges, commits `rounds/round-N/`, opens a
   PR "Round N" with report.md as the body and write-next.pdf attached, and
   uploads preview PNGs.
4. Merging the PR accepts the round. Tagging `v*` runs `release.yml` (today's
   flow, now parameterised by family) and attaches the zips.
5. The template pins an engine version (`handfont==X.Y`). Dependabot or Renovate
   proposes engine upgrades, and the round PR shows a before/after preview.

Privacy: the template repo defaults to **private**. Docs warn that
handwriting can identify a person, and that practice text must not contain real
phone numbers or addresses. Note: `words.py` today contains a phone-number-like
line and other personal-looking text; see section 10.

### 5.3 Contributing upstream (community)

| Contribution | Where | Gate |
|--------------|-------|------|
| Engine fix or feature | PR to `handfont/` | Unit tests + golden e2e (AnnaHand metrics within tolerance) |
| New style | `handfont/styles/<name>.py` + preview | Same, plus a style review label |
| New check in judge | `judge.py` + test | Must map to one of the 4 outcome groups |
| New surface/package target | `package.py` | Install notes + manual test checklist |
| Charset/locale (e.g. Latin-Ext, ₹ €) | `charsets/*.yaml` + template pages | Template renders; judge knows the set |
| Publish my font to the gallery | PR adding an entry to `gallery/index.yaml` (link to their repo/release) | Consent checkbox, OFL, no photos needed upstream |
| Share anonymised samples as a test fixture | `tests/fixtures/<id>/` (PNG + JSON) | Explicit consent, no personal text |

Repo hygiene to add: `LICENSE` (code), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
issue templates (engine bug, glyph looks wrong, new style idea, gallery entry),
`CODEOWNERS`, and labels matching the 4 outcome groups.

## 6. Agent roles (Haiku and Sonnet)

The loop already has human roles: writer, developer, decider and bot. Agents
take the bot work. Proposed default split, used both while building this and inside the
product's GitHub flow:

| Task | Model | Why |
|------|-------|-----|
| Read report.json → write the plain-language round summary and PR body | Haiku | Short, templated, cheap |
| Draft `pages.yaml` transcription or legacy specs from a photo for human check | Haiku | Bulk and mechanical; a human confirms |
| Triage new issues and label them with an outcome group | Haiku | Classification |
| Docs and README updates, changelog entries | Haiku | Low risk |
| "Fixable in code" findings → propose a change to `overrides.yaml` or engine knobs | Sonnet | Needs reasoning over facts + code |
| Engine PRs: refactors, new detectors, review of community PRs | Sonnet | Multi-file code changes |
| Design questions, "your decision" explanations with options | Sonnet | Trade-offs |

The agents are an optional layer. In the template repo they run through the
Claude GitHub Action if the owner enables it, and the whole pipeline works
without them.

## 7. Fonts, naming and licensing

- **Code**: MIT or Apache-2.0 at the root (decision D3).
- **Fonts**: default SIL OFL 1.1, copyright = the writer. `build.py` writes name
  IDs 0 (copyright), 8/9 (manufacturer/designer), 11/12 (URLs) and 13/14 (license),
  all from `writer.yaml`.
- Nerd icons keep their own licenses. The mono add-on downloads the symbols
  file in the build step (pinned URL + checksum) instead of reading `/tmp`.
- **Version**: one source, `writer.yaml: version`, for the font. The engine has
  its own semver. The font records both (`version 0.4.0; handfont 1.2.0`).
- Family names must be unique-ish. `handfont new` checks the gallery for
  collisions and warns about reserved names.

## 8. Quality and testing

- **Golden end-to-end test**: a small cut-down fixture (a few photos or a
  template scan) → build → compare metrics (glyph count, advance widths,
  bbox per glyph, judge score) with stored values and a tolerance. AnnaHand is
  the first fixture, and a synthetic template scan (rendered from a known font)
  is the second, so CI covers Path A with no real person's data.
- Make the judge thresholds relative to the writer's own cap height and stroke
  width (today some are absolute pixels).
- Move all `/tmp` fixtures into `tests/fixtures/`. Bundle a free font for previews.
- CI matrix: Linux + macOS + Windows, Python 3.10–3.13.
- Release: one pinned `requirements.lock`. Pickle disappears.

## 9. Migration plan (phases)

Each phase is a separate PR set. AnnaHand output must stay the same, or
improve on purpose, at every step.

| Phase | Scope | Exit criteria |
|-------|-------|---------------|
| **0. Hygiene** | Root LICENSE, one version source, remove macOS and `/tmp` paths, bundle a preview font, move test fixtures, move dead experiments (`lab.fit`, `cands`, `before_after`, `prev`, `sheet`) to `tools/dev/` | CI green on Linux with no skips |
| **1. Engine refactor** | Turn import-time scripts into functions, add `handfont` package + CLI, `writer.yaml`, `overrides.yaml`, PNG+JSON samples. Move Anna to `writers/anna/` | Golden AnnaHand test passes; `handfont round --writer anna` reproduces v0.4.0 |
| **2. Template capture (Path A)** | Template PDF generator, marker scan, cell cut. Handover PDF becomes a template | A synthetic scan → font in CI. One real non-Anna trial |
| **3. Ink and freeform** | `ink.py` auto-detect, `pages.yaml`, options for spread and rotation | Black pen on plain paper works. Blue-on-ruled AnnaHand is unchanged |
| **4. GitHub template repo** | `template-repo/`, `round.yml`, private by default, engine pinning, round PR | A new user goes from template to round-1 PR with no local install |
| **5. Community** | CONTRIBUTING, issue templates, labels, gallery, optional agents via the Claude GitHub Action | First outside contribution merged |

## 10. Open decisions (need your call)

- **D1. Project name.** The repo is `clone-your-handwriting` and the engine is
  `handfont`. Keep both, or rename the package (PyPI availability needs checking)?
- **D2. AnnaHand's place.** Keep it in this repo as `writers/anna/` (reference +
  fixture + showcase), or move it to its own repo created from the template?
  Recommendation: keep it here for now as the reference writer.
- **D3. Licenses.** Code MIT vs Apache-2.0; fonts OFL-1.1 by default (recommended).
- **D4. Default capture path.** Template (recommended) vs freeform-first.
- **D5. Personal data.** Anna's real name is in the README and personal-looking
  text is in `words.py` and the photos. Pseudonymise before the repo goes
  community-facing? (Git history keeps it unless it is rewritten.)
- **D6. Styles in core.** Are all 5 styles core, or is mono+nerd an add-on
  (it has an external download and its own licenses)?
- **D7. Agents.** Opt-in in the template repo (recommended), or on by default?
- **D8. Scope v1 charset.** ASCII + `₹ € £ ¥ —`, or also Latin-Ext (accents)
  from the start?
- **D9. Committed outputs.** Keep built fonts committed in writers' repos (simple,
  works today), or only publish them as release assets?

## 11. Appendix: hard-coding audit (condensed)

- **Names/IDs**: `pipeline.py:46-52` FAMILIES/MAIN_FAMILY; `package.py:30-47` ORDER,
  BLURBS, SAMPLE; `package.py:380-412` `com.annahand.*`, `AnnaHand.mobileconfig`;
  `package.py:576-585` zip names; `nerd_mono.py:35-51`; `review.py:5-13`;
  `handover.py:7,325,377` default family; `handover.py:45,355` person and bot names.
- **Paths**: `extract.py:7`, `words.py:21` dated photo folder; make.py reads pkl
  from the working directory; macOS Arial in `handover.py:26`, `review.py:4`,
  `sheet.py:7`, `cands.py:7`, `before_after.py:6`, `words.py:401`,
  `test_judge.py:164`; `/tmp` in `test_geometry.py:11`, `test_judge.py:16`,
  `nerd_mono.py:46`, `prev.py`.
- **Photo data**: `specs.py:8-36` SPECS; `words.py:44-89` PAGES; `words.py:26-41`
  spread, rotation and pixel constants; `seg.py:54` pixel constants.
- **Per-letter tuning**: `make.py:18-22,44-50` EXCLUDE, BAD_ROWS, EXPECT,
  PREFER_ALPHA(_CLEAR), OVERRIDE; style multipliers and side bearings in make.py;
  `cleanup.py:29-30` PEN_B/LINE_B; `seg.py:8-10` blue hue window; `judge.py:41-51`
  thresholds partly absolute.
- **Metadata**: `build.py:146-160` has no copyright or license name IDs; vendor `HFNT`;
  versions `__init__.py:3`, `build.py:236`, `make.py:114`; no root LICENSE.
- **Charset**: `layout.py:31-35` 94 ASCII; extra symbols only via SPECS;
  backtick missing; `:` and `_` synthesised (`make.py:180-185`).
- **Known open items carried over**: single-copy symbols, size spread in C V u y 2 4,
  missing backtick, `_` has 0 samples, no kerning, round-1 count mismatch (98 vs 99 vs 97).
