# AGENTS.md

Guide for coding agents (Claude, Codex, others) working in this repository.

## What this repo is

**Clone Your Handwriting**: turn photos of handwriting into installable fonts,
improved round by round. AnnaHand is the example writer.

- Design (agreed): [docs/DESIGN.md](docs/DESIGN.md)
- Plan and current phase: [docs/ROADMAP.md](docs/ROADMAP.md)
- How a round runs today: [PIPELINE.md](PIPELINE.md)

Before starting, read the roadmap and find the task you are doing. One task = one PR.

## Rules

1. **No personal data, ever.** Do not commit photos outside `writers/anna/`,
   real names, emails, phone numbers or addresses. Use `555-0100` and
   `example.com` in samples. Strip EXIF from any image.
2. **Engine code knows nothing about a writer.** Names, IDs, paths and
   per-letter choices belong in `writer.yaml` / `overrides.yaml`, not in code.
3. **Never guess handwriting.** Report findings in "Needs handwriting" and
   "Your decision" to the human. Do not invent glyphs or pick styles for them.
4. **Golden tests protect AnnaHand.** If a change moves its metrics, say so
   in the PR and update the goldens on purpose.
5. **No pickle, eval or exec** on contributed data.
6. Keep the four handwriting styles: hand, paper, typed, access. No monospace.
7. Do not rewrite git history. Do not push to `main` or open PRs unless asked.
8. Code is MIT. Fonts are OFL-1.1. Add a license file next to anything bundled.

## Which model does what

Use the cheapest model that can do the job well.

| Work | Model |
|------|-------|
| Read reports, summarise a round, write PR bodies | Haiku |
| Search the code, list files, audits that only read | Haiku |
| Docs, changelog, templates, issue triage and labels | Haiku |
| Mechanical edits across files (renames, text fixes, moves) | Haiku |
| Code changes with logic: refactors, new detectors, styles, CI | Sonnet |
| "Fixable in code" findings → knob or `overrides.yaml` change | Sonnet |
| Reviewing a PR, design trade-offs, "Your decision" options | Sonnet |

A manager agent splits the work, gives read-only tasks to Haiku workers and edit
tasks to Sonnet workers, and checks results (tests + previews) before any PR.

## Setup and checks

    python3 -m venv .venv && . .venv/bin/activate
    pip install -r tools/requirements.txt pytest reportlab pymupdf
    python -m pytest tools -q

Run the tests before every push. For a font change, look at
`previews/styles.png` and the round report before and after.

## Layout today (until Phase 1)

- `tools/`: pipeline scripts and `tools/handfont/` (vectorize, build, layout)
- `fonts/`: built fonts (committed)
- `previews/`: preview images
- `docs/`: design, roadmap, session notes

The target layout (`cyh/`, `writers/anna/`, `template-repo/`) is in DESIGN.md section 3.

## Asking the human

Questions, handovers and "Your decision" items go to the owner in the PR or
in GitHub Discussions. Keep them short, with the options and a recommendation.
