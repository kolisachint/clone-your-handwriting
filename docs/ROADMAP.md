# Roadmap

Plan for turning AnnaHand into **Clone Your Handwriting**. The design is in
[DESIGN.md](DESIGN.md). Each task below is one PR. The model column says which
agent does the work by default (see [AGENTS.md](../AGENTS.md)).

Status key: `todo` · `doing` · `done`.

## Done

- [x] Design agreed (2026-10-25): `docs/DESIGN.md` v3, this roadmap, `AGENTS.md`.

## Phase 0: hygiene and privacy

Goal: a clean, portable, MIT-licensed repo with no personal data in the tree.
AnnaHand's fonts stay unchanged in this phase.

| # | Task | Model | Done when |
|---|------|-------|-----------|
| 0.1 | Add `LICENSE` (MIT) and `writers`-agnostic copyright line | Haiku | File present; README links it |
| 0.2 | Privacy text fixes: `words.py:60-61,78`, `prev.py:6`, `review.py:10` → `555-0100`, `example.com`, neutral date; `handover.py:45,97` → "post in GitHub Discussions" / `@example`; `handover.py:355` author → "Clone Your Handwriting"; drop PDF CreationDate | Haiku | `grep` for emails, phone patterns, `hoo` finds nothing outside history |
| 0.3 | Remove old photos `handwriting/2026-10-10/`, `tools/word_samples.pkl`, `iterations/round-1/` (P3). Keep `fonts/` and `previews/` until Phase 2 rebuild | Haiku | Tree has no photo-derived samples; README "How it was made" says photos are being replaced |
| 0.4 | Drop Nerd Mono (D6): `tools/nerd_mono.py`, `tools/test_nerd_mono.py`, `fonts/AnnaHandNerdMono/`, `previews/nerd-mono.png`, README terminal section, `package.py` ORDER/BLURBS entry; CHANGELOG note | Sonnet | CI green; `package.py` builds 4 families |
| 0.5 | One version source; remove `__init__.py`/`build.py` defaults that disagree with `make.py` | Sonnet | One constant; fonts report it |
| 0.6 | Portability: bundle an open preview font in `tools/assets/fonts/` (with its license); replace macOS font paths (10 files) and `/tmp` paths; move test fixtures into `tests/fixtures/` | Sonnet | Tests run on Linux with **no skips** |
| 0.7 | Move experiments (`cands.py`, `before_after.py`, `prev.py`, `sheet.py`, `lab.fit/label_row`) to `tools/dev/` | Haiku | `pipeline.py` and tests untouched by the move |
| 0.8 | Font name table: copyright (ID 0), designer, license + URL (IDs 13/14) | Sonnet | `fontTools` shows the fields; test added |
| 0.9 | CI: add `ruff` lint, cache pip, run on push to `main` as well | Haiku | CI green |

Exit: CI green with no skips; privacy grep clean; `LICENSE` present.

## Phase 1: engine refactor

Goal: writer-neutral `cyh` package. AnnaHand output reproduced within tolerance.

| # | Task | Model |
|---|------|-------|
| 1.1 | Golden test first: record current AnnaHand metrics (glyph count, advances, bboxes, judge score) from cached samples | Sonnet |
| 1.2 | Create `cyh/` package; move `handfont/` + core modules; `pyproject.toml` (`clone-your-handwriting`, MIT) | Sonnet |
| 1.3 | `writer.yaml` + `overrides.yaml` schema and loader (`cyh/config.py`) | Sonnet |
| 1.4 | Turn `make.py` into functions taking a config; styles into `cyh/styles/` registry | Sonnet |
| 1.5 | PNG + `samples.json` sample format; one-time pickle converter | Sonnet |
| 1.6 | Parameterise `package.py`, `handover.py`, `review.py` (family, IDs, blurbs, sample text) | Sonnet |
| 1.7 | `cyh` CLI: `new`, `round`, `package`; `pipeline.py` becomes a thin wrapper | Sonnet |
| 1.8 | Move AnnaHand into `writers/anna/` | Haiku |
| 1.9 | Docs: README quick start, `docs/contributor-guide.md` | Haiku |

Exit: `cyh round --writer anna` matches the golden test.

## Phase 2: capture (template and freeform) and new photos

| # | Task | Model |
|---|------|-------|
| 2.1 | `cyh kit`: template PDF (ArUco, cells, guides) from a charset | Sonnet |
| 2.2 | `capture/scan.py`: markers → unwarp → cells; synthetic scan fixture in CI | Sonnet |
| 2.3 | `cyh kit --freeform`: prompt sheet + `pages.yaml`; generalise `words.py` alignment | Sonnet |
| 2.4 | `ink.py`: any pen/paper; `cyh check` photo quality + privacy warnings | Sonnet |
| 2.5 | `write-next.pdf` as a template or prompt sheet with only the weak characters | Sonnet |
| 2.6 | **Owner** prints both kits, writes, supplies new photos (MIT) | Owner |
| 2.7 | Rebuild AnnaHand from new photos; replace `fonts/` and `previews/`; release | Sonnet + Owner sign-off |
| 2.8 | `docs/writer-guide.md`, `docs/quality.md` | Haiku |

Exit: AnnaHand at **Example** tier (DESIGN.md section 10) from new photos only.

## Phase 3: template repo

| # | Task | Model |
|---|------|-------|
| 3.1 | `template-repo/` files (DESIGN.md 7.2) | Haiku |
| 3.2 | `round.yml`: build → judge → "Round N" PR with previews | Sonnet |
| 3.3 | `release.yml` for user repos; engine pinning; Dependabot | Sonnet |
| 3.4 | Publish `clone-your-handwriting-template`; dry run with a test writer | Owner + Sonnet |

Exit: a new user reaches a round-1 PR with no local install.

## Phase 4: community

| # | Task | Model |
|---|------|-------|
| 4.1 | `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `docs/privacy.md` | Haiku |
| 4.2 | Issue forms, PR template, labels, CODEOWNERS (DESIGN.md 7.1) | Haiku |
| 4.3 | Enable GitHub Discussions (Q&A, Show and tell, Handover) | Owner |
| 4.4 | `gallery/index.yaml` + gallery page | Haiku |
| 4.5 | Opt-in agents example workflow (`claude.yml.example`) | Sonnet |
| 4.6 | PyPI release of the engine | Owner + Sonnet |

Exit: first outside contribution merged.

## Owner actions

- Phase 2: write both kits and supply new photos.
- Phase 3: create the template repository.
- Phase 4: enable Discussions and private vulnerability reporting; PyPI account.
