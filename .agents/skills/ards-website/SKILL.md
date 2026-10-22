---
name: ards-website
description: Modify, debug, or review the ARDS Studio UI, CodeChef-style statement rendering, local API, or PPC editor.
---

# ARDS Studio website workflow

Use for website code, layout, UX, public-statement authoring, or related server endpoints. Read `website/PROBLEM_AUTHORING_STANDARD.md` when changes touch problem text/rendering. Use `website/README.md` for server startup and local test instructions.

## Product behavior

- The design is **light-only**. Use established product typography and consistent visual hierarchy rather than decorative marketing-style typography.
- The problem library offers pagination, search/filters and similar-problem discovery. Table headings and rows share a consistent column grid at desktop widths with deliberate mobile reduction.
- Student-facing statement quality is level-dependent: follow `references/specification_comprehension.md`. Levels 1–3 must be comprehensible without specialist prior knowledge of the tested topic; levels 4–6 may expect interpretation of mathematical abstractions. At every level, no missing/contradictory rules and no algorithm hints. Render meaningful notation consistently; do not turn an explicit definition into an unexplained symbol. Problem statements use competitive-programming semantic sections with **no Explanation or Note section**. Every rule needed to solve must be in the description, input/output format, or constraints. Samples are input/output only. Author `statement_display` in the newest versioned package; the backend's legacy parser remains read-only but strips archived explanation/note fields from public output. Markdown and math use bundled Markdown-It/KaTeX. Never invent a missing stdin format or sample data.
- Sample input/output cards are side-by-side when space permits, stacked on narrow screens. The problem statement and PPC editor scroll independently on desktop.
- PPC section help opens in a modal; a preview does not reveal solutions or change assessment status. **Reference PPCs are Markdown plus KaTeX**: use `\(...\)` for inline notation and `\[...\]` for prominent display equations; render proof claims/steps as separate paragraphs (or meaningful headings), not one block of unformatted text. The reference modal has a conservative display-only adapter for old ASCII equations, but authors must use real LaTeX delimiters for all new PPCs. Never silently rewrite historical teacher proofs to improve their visual layout.
- **Never surface unreleased batch drafts through the learner library.** Keep registered packages and private PPCs in canonical SQLite for reviewer CLI access only. Only `challenges.statement` after legitimate verification-gated release may appear to the learner; guessable draft IDs must yield 404 for statements, drafts, submissions, or solution reveal.

## Trust and data boundaries

- Student-visible endpoints, library lists and previews must exclude the teacher PPC, reference code/proof, hidden tests, and solution-derived hints.
- Revealing a full reference requires explicit consent and a persistent exposure record **before** the response. Previously graded independent passes retain credit; later attempts do not count independently.
- Preserve `data/ards.db` and prior learner work. Use disposable databases for tests; do not use new demo problems to pollute genuine Classic RACG history.
- The server is local-only. Keep HTML/Markdown and math rendering non-executable; do not regress path sanitization or API token/origin validation.

## Completion checks

Inspect the affected routes and assets, check a desktop and narrow viewport when layout changes, then run relevant website/unit tests. Confirm that public problem responses and previews contain no private fields. Only report browser/test/SQLite checks actually observed.
