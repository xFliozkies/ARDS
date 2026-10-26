# ARDS Studio — dedicated problem & PPC website

**Coding-agent workflow:** Use the repository's concise [AGENTS.md](../AGENTS.md) and the task-triggered [ARDS website skill](../.agents/skills/ards-website/SKILL.md). General agent guidance is not duplicated here; the source of truth for public problem formatting is [PROBLEM_AUTHORING_STANDARD.md](PROBLEM_AUTHORING_STANDARD.md).

**Authoring standard (mandatory):** [PROBLEM_AUTHORING_STANDARD.md](PROBLEM_AUTHORING_STANDARD.md). New statements have no sample explanations or Note sections; all necessary rules belong in the task description, input/output contract and constraints. Reference PPC style follows [the learner's PPC examples](../references/ppc_authoring_style.md). New problems must provide a solver-only `statement_display` package, with real CodeChef-style Input Format, Output Format, Constraints, sample pairs and optional explanations. `python3 website/validate_display.py PACKAGE.json` validates the public format. Older Markdown remains read-only and is adapted by `statement_format.py`; do not modify the canonical archive to repair layout. The browser uses bundled Markdown-It and KaTeX locally with HTML disabled and remote images excluded.

**Theme:** light-only. No system-dark toggle and no dark UI skin.

**Typography refinement (October 2026):** `public/typography.css` is the last-loaded stylesheet. It establishes a consistent 16px body, 14px UI/supporting text, 12px captions and restrained 24–40px headings across the library, PPC editor, reference manual, and overview. It removes superfluous marketing-style typographic effects, faux editorial stamps, the four-label manual strip, and the sidebar version/device copy. This is a functional study interface, not a marketing landing page. Reference sources: GitHub Primer typography (https://primer.style/product/getting-started/foundations/typography/), Vercel Geist typography (https://vercel.com/geist/typography), and Notion writing style guidance (https://www.notion.com/help/customize-and-style-your-content). Responsive math wrapping is specifically tested in a narrow-screen browser.

## Design references (adapted, not copied)

- **GitHub Primer** — light interface primitives, accessible contrast, quiet dividers, typographic hierarchy:
  https://primer.style/product/getting-started/foundations/
  https://primer.style/primitives/
- **Exercism Online Editor** — problem/editor split, separate solve and submit actions:
  https://exercism.org/docs/using/solving-exercises/using-the-online-editor
- **Linear light workspace** — compact product navigation, restrained status hierarchy:
  https://linear.app/
- **Notion light editorial writing** — long-form composition, readable content width and minimal formatting chrome:
  https://www.notion.so/

ARDS has an original wordmark and brand typography; no third-party screenshots,
logos, fonts or proprietary assets were copied. The application has no CDN
runtime dependencies and works offline.

## Start

From the existing ARDS project root:

```sh
python3 website/server.py --port 8765
```

Open **http://127.0.0.1:8765/** in a browser on the same computer.

The server intentionally binds ONLY to 127.0.0.1; it must not be exposed on a
public network without authentication, HTTPS, auditing and a deployment review.

## What works

- Browse and filter the **canonical ARDS SQLite challenge archive** by level and status;
  search by title, topic, or statement; keyboard search shortcut `/` or `Ctrl+K`.
- Read existing problem statements in a dedicated reading panel.
- Write PPC's four sections independently: problem specification, proposed
  procedure, correctness proof, and complexity.
- Automatic draft saving after a pause, manual Save Draft, Ctrl+S, tab switching
  and persistence across browser reloads.
- A submission action that uses the original ARDS `memory.add_attempt` pipeline:
  first submissions become original attempts, later submissions revisions.
  The site NEVER fabricates independent status, hint count or a correctness grade.
- A concise overview showing canonical challenge/attempt/assessment counts.
- **PPC Field Manual** (`#/method`): eight navigable chapters covering the formal specification, precise algorithm descriptions, correctness obligations, proof-technique selector, asymptotic complexity, searchable mathematical notation, a full prefix-sum PPC example, and a pre-submission self-review checklist. The manual is available offline, has a chapter-specific link from each PPC editor section, and includes a copyable PPC skeleton. The self-review is not a proof certificate.

## UI/UX implementation (2026-10-22)

Studio now supports shareable hash routes and browser Back/Forward, a saved-drafts
page with student-only Markdown/JSON downloads, persistent library filters and
pagination, progress by level/topic, and recorded review findings. The review
endpoint is read-only and session-token-protected; it preserves `Undetermined`
and never returns raw private reports or teacher packages. Opening the reference
still records exposure before returning its content. Optional reflection and
scratch notes are browser-only and never enter the PPC submission.

The workspace includes Markdown/KaTeX preview, accessible section controls,
keyboard/pointer resizing, narrow-screen Problem/Write switching, sample and
statement copying, reading preferences, local unsaved recovery, and print styles.
Alt+1–4 changes PPC sections; `?` shows shortcuts. A server restart and hard refresh
are required after upgrading the Python routes.

Development checks use synthetic temporary databases only:

```sh
node --test tests/editor_logic.test.mjs tests/studio_logic.test.mjs
node tests/studio_browser.mjs
```

The browser suite requires a development Playwright installation and an installed
Chromium. Set `ARDS_PLAYWRIGHT_MODULE` to Playwright's `index.mjs` and
`ARDS_CHROMIUM_PATH` to the browser executable when outside standard locations.
With no `ARDS_UI_TEST_URL`, it starts and cleans up its own disposable fixtures.
It captures five views at 375/768/1280px, runs vendored axe, and verifies navigation,
privacy, review/reveal, exports, recovery and print behavior. Artifacts default to
`/tmp/ards-studio-ui`; override with `ARDS_SCREENSHOT_DIR`. No browser download or
external runtime resource is required by the suite. See `tests/vendor/README.md`.

## Persistence and safety

- Production problem archive: `data/ards.db`, unchanged during browsing or draft edits.
- PPC drafts and revisions: `data/ards-studio.db` (separate SQLite database).
- Actual PPC submissions: canonical `attempts` table via the existing persistence API.
- Data are stored locally; browser search and solution entry do not require any
  cloud service or external CDN.
- HTTP API requires an ephemeral session token and origin validation on write
  requests, and sets a strict Content Security Policy.
- **Only one local user is supported**. Do not treat local access as authenticated
  multi-user deployment.

## Classic RACG authored editions and teacher PPCs

**Latest reset 2026-10-20:** The user explicitly reset the active learning data again **without creating a new backup**. The immediately preceding 10 released problems, their independent-review files, and batch records were discarded. Both active databases retain empty schemas. Older separately archived histories remain outside the project and must not be silently imported. Newly released problems
must include private P1/P2/C/K teacher PPCs alongside the authored package.

The website reads the most recent `classic_authoring_editions` entry per challenge
without altering its original immutable statement. For those entries it obtains
all four teacher PPC sections from the corresponding bound `package_json`:
P1 model/problem specification, P2 `reference_solution`, C `proof` plus explicit
`termination`, K structured `ppc.complexity`. These are labeled **drafted,
not independently or mechanically verified**, as recorded by Codex.
Teacher PPCs are never part of normal problem endpoints; only explicit reference
reveal returns them and records permanent assessment exclusion first.

### Registered batch drafts in the library

**Registered but not released** batch problems remain outside the learner-facing
library and all problem/detail/reveal routes. Their full packages and teacher PPCs
are in canonical `problem_packages` and optional `authoring_package_revisions`;
only a successful gated release populates `challenges.statement`. The AI review
queue is managed through `scripts/ards_review.py`, with the requirements in
`references/independent_review.md`. Students see only released problems;
unreleased guesses of problem IDs return 404, not previews.

Returning to the problem library or pressing **Refresh** loads new challenges and
newly authored editions. No extra copying or hand-import is necessary for this
canonical edition-based workflow. The separate JSONL importer remains available
if a future agent supplies teacher PPCs without embedding them in the archived edition.

For each new Classic RACG challenge Codex must:

1. Use the existing `scripts/racg.py` / `scripts/ards2.py` machinery to draw
   and persist the actual O, X (when applicable), Y and P rolls and reasoning
   pattern planning. Do NOT fabricate draws or treat synthetic fixtures as new
   student challenges.
2. Generate and independently check the statement, constraints, tests and
   expected reference algorithm according to ARDS verification rules.
3. Attach the complete **teacher-only** `teacher_ppc` object to the same
   registered ARDS package, in addition to any machine-readable PPC proof
   obligations:

   ```json
   {
     "teacher_ppc": {
       "problem": "Domain D, outputs Y, preconditions, quantified postcondition Q",
       "procedure": "An unambiguous algorithm with initialization and termination",
       "correctness": "Lemmas/invariants, preservation, exit, termination; optimality if required",
       "complexity": "Input-size definition, cost model, derived time and space bounds"
     }
   }
   ```

4. Prefer registering, verifying and **releasing** through the canonical ARDS
   pipeline. This lets the website show the complete released reference with
   its appropriate assurance label. Never treat a human-written proof as a
   machine proof simply because sample tests passed.
5. If Codex has already recorded the Classic RACG problems but wrote teacher
   solutions to a separate JSONL file, use the **hash-bound teacher import**
   instead. No existing challenge records or actual RACG rolls are rewritten.
   Create a JSONL with one object per line:

   ```json
   {"challenge_id":"RACG-0004","statement_sha256":"64 lowercase SHA-256 hex characters","teacher_ppc":{"problem":"Full P1","procedure":"Full P2","correctness":"Full C","complexity":"Full K"}}
   ```

   For unchanged canonical challenges, the statement hash is SHA-256 of
   `challenge.statement.strip()` encoded as UTF-8. For revised
   `classic_authoring_editions` statements, hash the *exact stored edition
   text* (including its final newline) as UTF-8; use the latest edition.
   Codex must read the actual canonical statement, not guess its hash.
   Then, from the ARDS root, run:

   ```sh
   python3 website/import_teacher_ppcs.py /path/to/codex-ppcs.jsonl --expected 100
   python3 website/import_teacher_ppcs.py /path/to/codex-ppcs.jsonl --expected 100 --apply
   ```

   The first command is a non-mutating dry run; `--apply` imports all records
   atomically or none. Existing references are immutable, and the import
   rejects duplicate IDs, incomplete PPCs, wrong hashes and missing challenges.
   Imported PPCs are **AI-authored, unverified teacher candidates**, visibly
   labeled as such when revealed. An import never falsely creates a verified
   ARDS release record.

Teacher PPCs are never included in student-facing problem endpoints, library
listings, or ordinary statement requests.

### Reveal = permanent independent assessment exclusion

The website shows the reference PPC only after an explicit confirmation and
writes `solution_reveals` to the canonical database **before** returning it.
Once revealed, later attempts cannot earn independent credit. An earlier
independent first attempt that was already graded correct **before** reveal
retains its earned credit; earlier ungraded or failing attempts become excluded.
Past attempts and assessments are never deleted. The website does NOT
automatically grade PPC submissions: it can record an explicitly attested
independent original submission, but separate evidence-based assessment is required.

If ChatGPT, Codex, or another AI reveals the teacher PPC **outside the website**,
it must mark the exposure before showing the answer:

```sh
python3 scripts/solution_exposure.py mark RACG-XXXX --provenance chat
```

Do not silently flip independent status on existing attempts; analytics uses
immutable exposure records and their preserved, already-passed first-attempt IDs.
The UI also supports collapsible navigation, independently scrolling desktop
statement/editor panels, on-page PPC reference dialogs, CodeChef-inspired
constraints and horizontal sample cards, problem previews and schema-based
filters (topic, family, difficulty, status, format, progress, similar-to, order).
The similar-to picker searches challenge names and RACG numbers as you type;
select a match with the mouse or arrow keys and Enter, and clear it with ×.
Progress values use plain text without a leading circle.

## Testing

```sh
python3 -m unittest discover -s tests -p test_website.py -v
python3 -m unittest discover -s tests -q
```

Site tests use a temporary SQLite copy, so tests can submit example PPCs without
changing your actual challenge state.

## Existing benchmark vs genuine practice challenges

This website currently lists actual **presented** ARDS challenge statements.
The 100 PPC 2.0 stress-test packages are parameterized test fixtures from only
seven families, *not* 100 new Classic RACG problems, and are not silently added
to your live practice history.

The next phase is generating 100 independently reviewed, diverse ARDS challenge
packages with matching PPC teacher solutions and explicit verification scopes,
then surfacing them in the website without spoiling student-facing statements.
Creating that set must not automatically resolve `RACG-0003`.

The workspace's **Back** button opens My PPC workspace. **Next** browses existing
released problems using 30% recorded continuation, 40% same-topic, and 30% random
selection pools, excluding the current problem and all problems whose reference
has already been viewed. Unavailable pools are omitted
and remaining weights renormalized. This never creates or rerolls a RACG draw.
The library shows an animated result count only while search text is nonblank.
The screenshot refinement regression suite is `node tests/polish_browser.mjs`
(with the same development Playwright/browser variables described above).

## Java practice

Use the **PPC editor / Code editor · Java** picker at the top of the solution workspace. Only the selected editor and its actions are shown. Your choice is remembered in this browser, and both drafts survive switching. Left/Right arrows and Home/End operate the picker. The Java timer appears in its navigation button. Write a complete
`Main.java` program (`public class Main`, no package declaration). The editor
supports Java syntax coloring, automatic bracket/quote pairs, paired deletion, brace indentation, line numbers, local autosave, browser recovery, and Java
file downloads. **Run tests** uses official samples or custom stdin; custom
runs show output without a correctness verdict. **Submit Java** checks official
samples plus the current hash-bound reviewer suite's edge and generated cases.
Whitespace between output tokens is ignored; token spelling and order must match.
A failed submission shows the first failing test number, input, expected output,
actual output and runtime errors. These details persist with the submission.
Acceptance means passing this finite suite, not a mathematical proof or PPC grade.
Java submissions and source/version hashes are recorded separately in
`ards-studio.db`; the canonical learner challenge and PPC assessment records are
not changed by Java runs or submissions.

**Start time**, beside **Focus** in the navigation bar, starts an optional server-persisted timer. It continues
across navigation, browser closure, runs, compilation errors and failed submissions.
The button displays elapsed time; click it to pause or resume, or use the adjacent
**Stop** button to finish. Paused time is excluded, and pause/stop state survives
reloads. The first accepted Java submission also finishes the timer. Stopped
timers cannot be restarted; untimed practice remains available until you opt in. Code and timing are
per problem, shared by this installation's single local user.

Execution requires a local JDK (`java` and `javac`) and Linux `bubblewrap` (`bwrap`).
The runner fails closed if these are unavailable. Java compiles with UTF-8,
annotation processing disabled, and a 256 MiB compiler heap. Programs use a
256 MiB Java heap, two active CPUs, a five-second wall limit per case, bounded
output/files and process counts, and a 60-second overall test execution budget.
These are local practice limits, not original contest hardware limits. A budget
exhaustion is not acceptance. One judge job runs at a time. Each job has an
isolated temporary workspace and no network or learner-archive filesystem access.
Java programs are not allowed to depend on files outside that workspace.

Legacy structured test fixtures use private stdin adapters. Every input must
round-trip through the hash-bound reviewer's decoder; sample-derived layouts also
must match the official sample tokens. Missing/stale reviewer evidence or an
unsupported encoding blocks Submit with an explanation, while custom runs remain
available. No reference algorithm enters the browser; only the first failing case is returned
for a failed submission.

Additional disposable-fixture checks:

```sh
python3 -m unittest discover -s tests -p test_java_judge.py -q
node tests/java_browser.mjs
```

The Java browser check uses the same Playwright/Chromium environment variables
as the existing browser suite and writes screenshots to `/tmp/ards-java-ui`.

The workspace picker follows the [W3C APG tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/)
with one selected tab, linked panels, roving keyboard focus, and keyboard selection.
[Exercism's online editor](https://exercism.org/docs/using/solving-exercises/using-the-online-editor)
informed the separation of editing, test runs, and submission. The picker stays
visible while the editor scrolls; PPC-only toolbar actions disappear in Java mode,
and Ctrl+S saves the active editor. Alt+1–4 explicitly returns to the selected PPC
section. Changing editors never submits work, starts a timer, or pauses one.
