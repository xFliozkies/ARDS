# ARDS Studio UI/UX Implementation Spec

*Audience: an AI coding agent working in `~/MyFiles/AI/ARDS`. Source: a design review of `website/public/` (index.html, app.js, typography.css, workspace.css) plus the repo's README.md, AGENTS.md and `.agents/skills/ards-website/SKILL.md`. The reviewer did not run the site in a browser; items marked **VERIFY** must be confirmed in code or a browser before you build on them.*

## 0. How to use this document

1. Read section 1 (constraints) and section 3 (pre-flight) first. Do not skip them.
2. Work package by package (section 4), in the order given in section 5. Each package lists files, tasks and acceptance criteria.
3. After each package, run the completion checks in section 6. Report only checks you actually observed.
4. If a task conflicts with a constraint in section 1, the constraint wins. Stop and note the conflict instead of working around it.
5. If something is marked VERIFY and turns out false, adapt the task and record what you found in your final report.

## 1. Non-negotiable constraints

These come from the repository's own instructions. Violating any of them is a failed implementation.

- **Light-only theme.** No dark mode, no system-dark toggle, no dark skin.
- **No external runtime dependencies.** No CDN scripts, fonts or images. The app works offline with bundled Markdown-It and KaTeX in `website/public/vendor/`. Any new library must be vendored locally and justified.
- **Functional typography.** Keep the system font stack and the type scale in `typography.css` (16px body, 14px UI, 12px captions, 24 to 40px headings). No marketing-style effects, stamps or decorative type.
- **Local-only server.** It binds to 127.0.0.1 only. Keep the ephemeral session token (`X-ARDS-Session`), origin validation on writes, strict CSP and path sanitization intact. Do not regress them.
- **Non-executable rendering.** Markdown rendering keeps HTML disabled and remote images excluded. Student text never becomes executable HTML.
- **Privacy of teacher material.** Student-visible endpoints, lists, previews and any new UI must never include the teacher PPC, reference code or proof, hidden tests, or solution-derived hints.
- **Unreleased drafts stay hidden.** Registered-but-unreleased batch problems must not appear in the library, and guessable IDs must keep returning 404.
- **Reveal gate.** Revealing a reference PPC requires explicit consent and a persistent exposure record written **before** the response is returned. Do not weaken or reorder this.
- **Assessment honesty.** A submission is saved, not auto-graded. The UI must never fabricate independent status, hint counts or a correctness grade. "Undetermined" must remain a distinct state and never be rendered as pass or fail.
- **Data safety.** Never modify `data/ards.db` or `data/ards-studio.db` for testing. Use disposable databases. Do not create demo problems in the real Classic RACG history. Do not run `scripts/reset_ards.py --confirm-reset` for any reason.
- **Do not rewrite historical content.** Do not edit canonical statements or old teacher proofs to improve layout; the read-only adapters (`statement_format.py` and the display-only math adapter) are the only allowed route.

## 2. File map

| Path | Role |
| --- | --- |
| `website/public/index.html` | Single-page shell: sidebar, library, problem workspace, manual, overview, dialog and command overlay |
| `website/public/app.js` | Main app state, API calls, library, editor, drafts, submit |
| `website/public/workspace-ui.js` | Dialogs, previews, reveal flow, workspace helpers |
| `website/public/statement-renderer.js` | Statement and Markdown/KaTeX rendering |
| `website/public/guide.js`, `guide-content.html`, `guide.css` | PPC Field Manual |
| `website/public/app.css`, `typography.css`, `workspace.css` | Styles; `typography.css` loads after `app.css`/`guide.css` and `workspace.css` loads last |
| `website/server.py` | Local API server |
| `website/statement_format.py`, `validate_display.py` | Statement adaptation and display validation |
| `tests/` | Existing tests; put new UI checks here |

Read `server.py` before adding or changing any endpoint. Read `workspace-ui.js` and `guide.js` before editing dialogs or the manual; the reviewer did not read them.

## 3. Pre-flight verification (do this before coding)

Confirm each item and write down the answer.

1. **Routing.** Does the app use URL hashes for the library and problem views, or only for `#/method`? Does the browser Back button work from a problem to the library?
2. **My PPC workspace.** What does the `nav-drafts` button actually open? Is there a drafts list page, or does it just open the last problem?
3. **Narrow layout.** `#view-problem` is `height: calc(100dvh - 66px)` with `overflow: hidden`. At about 375px and 768px wide, do the stacked statement and editor panels clip or become unreachable? Check the media queries in `workspace.css` and `app.css` (only the first part of `workspace.css` was reviewed).
4. **Tab keyboard support.** Does the `role="tablist"` editor support Arrow, Home and End keys? Do dialogs trap focus and return it on close?
5. **Undo and state on tab switch.** When switching between sections 01 to 04, is the textarea's value swapped in place (losing native undo history)?
6. **Session expiry.** What does the user see if the server restarts and the token becomes invalid while a tab is open and autosave fires?
7. **API surface.** List the endpoints in `server.py` (problems, facets, drafts, revisions, submit, reveal, stats). Note which already return revision history and assessment data.
8. **Library search.** Confirm the library page has no inline search input (only the sidebar command palette).
9. **Existing tests.** Run the existing website tests once, unchanged, to record the baseline before you change anything.

## 4. Work packages

### WP1. Editor core (highest value)

**Goal:** make writing a PPC feel like writing a proof, not typing into a blank box.

**Files:** `index.html`, `app.js`, `workspace.css`, `statement-renderer.js` (reuse its Markdown/KaTeX pipeline).

**Tasks**

1. **Write / Preview toggle.** Above the textarea, add a two-state control. Preview renders the current section with the same Markdown-It + KaTeX configuration used for reference PPCs: `\\(...\\)` inline and `\\[...\\]` display, HTML disabled. The preview is read-only and updates on toggle, not on every keystroke, unless performance is clearly fine. Replace the footer text "Markdown & mathematical notation supported as text" with accurate wording.
2. **Symbol palette.** A compact, keyboard-reachable popover or row inserting at the caret: ∀ ∃ ∈ ∉ ⊆ ≤ ≥ ≠ ⇒ ⇔ Σ ∏ ∧ ∨ ¬ and LaTeX snippets `\\( \\)` and `\\[ \\]`. Insertion must preserve undo (use `setRangeText` or `execCommand('insertText')` where available) and caret position.
3. **Per-section progress.** On each tab (01 Problem, 02 Procedure, 03 Proof, 04 Complexity), show a small indicator for empty versus has-content, plus a character count in the tab's accessible name. Do not use color alone.
4. **Save state.** Replace the static "Not saved yet" with: `Unsaved changes`, `Saving…`, `Saved just now / N min ago`, and `Save failed – retry`. Add a `beforeunload` warning when there are unsaved changes. Autosave behavior and timing stay as they are.
5. **Submit confirmation.** Reuse the dialog from `workspace-ui.js`. Show: which sections are filled and which are empty; whether "Independent, without hints" is ticked; and a plain statement that submitting records an attempt (first submission = original attempt, later = revision) and is not auto-graded. Require an explicit confirm button. Do not change what the submit API sends.
6. **Per-section skeleton insert.** A button inserting only the current section's skeleton (P1: domain, preconditions, output relation; P2: initialization, steps, termination, return; C: Claim / Proof / Termination; K: input measure, time, space). Use the manual's existing skeleton text as the source; insert only when the section is empty, or ask before replacing.
7. **Text behavior.** Tab inserts spaces instead of moving focus (with Escape then Tab to leave, for accessibility). Enter continues numbered and bulleted lists. Preserve per-section undo if feasible (VERIFY item 5); if not feasible, at least do not lose text.

**Acceptance criteria**

- Switching sections and toggling Preview never loses or alters text.
- KaTeX in preview matches how the same text renders in the reference modal.
- The save-state label is always accurate, including after a forced failure (simulate by blocking the request).
- Submit sends the same payload as before; confirmation can be cancelled with no side effects.
- Everything is operable by keyboard alone.

### WP2. Accessibility and contrast

**Files:** `typography.css`, `workspace.css`, `app.css`, `index.html`, `app.js`, `workspace-ui.js`.

**Tasks**

1. **Contrast.** By the reviewer's calculation `--text-muted` (#738374) is about 3.8 to 4:1 on the page background, `#748275` (nav labels) is similar, and the placeholder `#8a968a` is about 3:1. Target at least 4.5:1 for all text under 18px. Candidates (verify by computing): muted text near `#5a6a5c` (about 5.7:1 on white), placeholder near `#66756a` (about 4.9:1). Keep the existing green-gray look. Audit every hardcoded text color in the three stylesheets, not only the variables.
2. **Small text.** Raise the 12.5px `.independent-attestation` label to at least 13px. Keep 12px only for non-essential captions.
3. **Tabs.** Implement Arrow Left/Right, Home and End with roving `tabindex` and `aria-selected`; connect each tab to a `role="tabpanel"` with `aria-labelledby`.
4. **Dialogs.** Trap focus, restore focus to the opener on close, close on Escape, set initial focus sensibly, and keep `aria-modal` accurate. Apply to preview, reveal confirmation and the new submit confirmation.
5. **Focus styles.** Provide a visible `:focus-visible` outline on `.problem-item` row buttons, nav links, tabs, chips and all new controls, not only the row action icons.
6. **Motion.** Add `@media (prefers-reduced-motion: reduce)` disabling the sidebar transition and any new animation.
7. **Status and level are not color-only.** Any color scale added elsewhere must also carry text or an icon.

**Acceptance criteria:** an automated axe-core run (see WP10) reports no serious or critical issues on the four main views; manual keyboard walk-through passes for library, problem, manual and dialogs.

### WP3. Library page

**Files:** `index.html`, `app.js`, `workspace.css`, `typography.css`.

**Tasks**

1. **Inline search.** Add a visible search input at the top of the table, wired to the existing `q` parameter of `/api/problems` with a short debounce. Keep `/` and Ctrl+K opening the command palette.
2. **Simplify filters.** Keep Level, Progress and Sort visible. Move Topic, Family, Format, Similar-to into a "More filters" popover. Show removable chips for every active filter and a "Clear all" action. Show the result count.
3. **Merge overlapping status filters.** "Status" (Ready/Evaluated/Attempted) and "Progress" (Not attempted/Attempted/Passed/Not revealed/Revealed) overlap. Design one lifecycle filter. Before removing either, check what each maps to server-side; if the API needs both, keep the API and change only the UI.
4. **Readable topic and family labels.** Replace `id · label` and `Family · Topic N` with the human label as primary text. Show the ID as secondary text only where needed.
5. **Level scale.** Add a subtle six-step visual (for example filled pips or a graded neutral-to-green tint) next to "Level N". It must stay legible in grayscale.
6. **Continue card.** Above the table, show the last opened problem (from `ards-last-selected`) with title, level, and a Continue button, if it still exists in the library. Trim or reduce the four-number stats strip so the page is not heavier overall.
7. **Persist view state.** Remember filters, sort, page and per-page for the session, and restore them when returning from a problem (see WP4).

**Acceptance criteria:** the filter row fits on one line at 1280px; every active filter is visible as a chip and removable in one click; returning from a problem restores the same page, filters and scroll position.

### WP4. Routing and navigation

**Files:** `app.js`, `index.html`, possibly `server.py` if static-route handling needs it.

**Tasks**

1. **Hash routes** (only if VERIFY items 1 and 2 show they are missing): `#/` library, `#/problem/<ID>`, `#/drafts`, `#/overview`, `#/method` (keep as is, including its chapter links). Back and Forward must work. Opening `#/problem/<ID>` directly must load that problem, and show the existing 404-style message for unknown or unreleased IDs.
2. **Drafts page.** If "My PPC workspace" has no list page, create one: a table of problems with a saved draft, showing problem title and ID, last saved time, and which of the four sections have content, each row opening the problem. Source the data from existing draft endpoints; add a read-only endpoint only if needed and only if it returns student-visible fields.
3. **Nav highlighting.** Highlight "Problem library" when a problem was opened from the library and "My PPC workspace" only when opened from the drafts page, or relabel so the nav matches reality.
4. **Command palette.** Extend Ctrl+K with actions (Open drafts, Open manual chapter N, Save draft, Go to overview), recent problems first, and highlight matched text. Search results must still use only student-visible fields.

**Acceptance criteria:** refreshing on any route restores that view; Back returns to the previous view with its state; no route reveals an unreleased problem.

### WP5. Problem workspace

**Files:** `index.html`, `workspace.css`, `app.js`, `statement-renderer.js`.

**Tasks**

1. **Copy buttons on samples.** Each sample input and output card gets a Copy button (copies exact text, with a brief "Copied" state, accessible label naming the sample).
2. **Statement mini-nav.** A sticky header with ID and level, plus jump links to Input Format, Output Format, Constraints and Samples (only for sections that exist).
3. **Resizable split.** A draggable and keyboard-operable divider between statement and editor (Arrow keys adjust, with sensible min widths). Remember the ratio. Add a Focus mode that collapses the statement and restores it.
4. **Narrow screens.** Below the existing breakpoint, replace stacking with a two-tab switch (Problem | Write) that preserves each panel's scroll and the editor's text. Fix any clipping found in VERIFY item 3.
5. **Reading controls.** Optional text-size and line-width controls for the statement, remembered locally. Defaults stay as they are.
6. **Copy as Markdown.** Copy the statement (student-visible content only) as Markdown.
7. **Scratch notes.** A separate per-problem notes box, stored locally with drafts, never included in the submission payload, clearly labeled "not submitted". If stored server-side, use the same studio DB and session/origin protections; if that needs a schema change, stop and propose it first.
8. **Section prompts panel.** `SECTION_PROMPTS` exists in `app.js` but no UI uses it. Add a collapsible "Self-check questions" panel beside or under the textarea, collapsed by default and remembered.
9. **Shortcuts.** Alt+1 to Alt+4 switch sections, `?` opens a shortcut overlay. Do not break existing `/`, Ctrl+K and Ctrl+S.

**Acceptance criteria:** at 375, 768 and 1280px nothing is clipped or unreachable; both panels remain independently scrollable on desktop; copied sample text is byte-identical to what is displayed.

### WP6. Data safety and robustness

**Files:** `app.js`, `server.py` (read it first), `workspace-ui.js`.

**Tasks**

1. **Export drafts.** A "Download my drafts" action (all drafts, or per problem) producing Markdown and JSON. Contents are the student's own text only. Implement client-side from existing endpoints where possible; if a new endpoint is needed, make it read-only, GET, token-protected, and student-data-only.
2. **Local mirror.** Keep the latest unsaved text per problem and section in localStorage so a failed save or expired session does not lose work. On load, if the mirror is newer than the server draft, ask which to keep. Clear the mirror after a successful save.
3. **Session expiry.** Detect token or origin failures on write and show a persistent banner ("Session expired. Reload to continue. Your text is kept locally.") instead of a generic toast. Do not log or expose the token.
4. **Skeleton loaders** for library rows and the problem panel in place of "Loading your archive…", with fixed row heights to avoid layout shift.
5. **Print stylesheet** for the statement and the reference modal: hide chrome, readable width, avoid breaking math and sample cards across pages.

**Acceptance criteria:** with the server stopped mid-edit, no typed text is lost after reload; an export round-trips (contents match what the editor shows); no export or banner includes teacher material.

### WP7. Assessment view and learning flow

**Files:** `index.html`, `app.js`, `workspace-ui.js`, `workspace.css`, `server.py` (read first).

**Tasks**

1. **Assessment page or panel.** For problems with a recorded assessment, show P1, P2, C and K findings, each with the reviewer's finding, evidence and stated uncertainty, as recorded. Use a distinct neutral style for `undetermined`, never green or red. Show a plain note that an assessment is a reviewer's critique, not a machine proof. Use only fields the existing API already exposes to the student; if more are needed, stop and propose the API change.
2. **Before-reveal reflection (optional field).** In the reveal confirmation dialog, add an optional "What is still unresolved in your proof?" text field saved with the student's own notes. It must not change eligibility rules or the exposure record.
3. **After-reveal comparison.** After a successful reveal (exposure recorded first, as today), offer a side-by-side view of the student's latest sections next to the revealed reference sections, rendered as Markdown + KaTeX. No comparison UI may exist before reveal.
4. **Copy and labels.** Keep wording accurate about credit rules: an independent first attempt already passed before reveal retains credit; later attempts are practice-only.

**Acceptance criteria:** before reveal, no network response or DOM contains reference material; after reveal, the exposure record exists before the content is returned (confirm in the server code path, do not weaken it); `undetermined` is visually distinct from both pass and fail.

### WP8. Overview page

**Files:** `index.html`, `app.js`, `workspace.css`.

**Tasks**

1. Replace the key-value list with: progress by level (1 to 6) showing released, attempted and passed counts; progress by topic (collapsible); and the existing counts as a compact summary. Charts are simple HTML/CSS or inline SVG built locally. No chart library.
2. **Empty state** for a fresh database (zero problems): explain what will appear and link to the manual. Do not imply problems exist.
3. Keep the existing wording about local-only privacy and not certifying unverified proofs.

**Acceptance criteria:** correct with zero, few and many records; all numbers come from the existing stats and problem endpoints (no invented data).

### WP9. Microcopy

**Files:** `index.html`, `app.js`, `guide-content.html`.

**Tasks:** replace system jargon with plainer labels where meaning is unchanged (for example "Reasoning attempts" to "Submitted PPCs", "Assessments" to "Reviews", "Reference opened" to "Reference viewed"). Keep terms that map to assessment policy where precision matters ("Independent", "Undetermined"). Update every occurrence consistently, including toasts, filters and the overview.

### WP10. Maintainability and tests

**Files:** `typography.css`, `app.css`, `workspace.css`, `guide.css`, `tests/`.

**Tasks**

1. **CSS tokens.** Move repeated hardcoded colors (the many greens and grays in `workspace.css`), radii and spacing into `:root` variables in one place. Fold overrides into their source rules where safe, but preserve the load order unless you have confirmed the visual result is unchanged by screenshots. Do this **last**, after the features above, to avoid conflicts.
2. **Automated UI checks.** Add a Playwright script (if an installed Playwright suite already exists use it; otherwise write the script but do not download browsers or dependencies without telling the owner) that runs against a disposable database, captures screenshots of library, problem, manual and overview at 375, 768 and 1280px, and runs axe-core from a vendored copy. Place it under `tests/`.
3. **Privacy test.** Add or extend a test asserting public problem responses, previews, drafts export and the library list contain none of: teacher PPC, reference solution, proof text, hidden tests.

## 5. Recommended order

1. Pre-flight (section 3).
2. WP2 (accessibility and contrast), because later work builds on it.
3. WP1 (editor core), then WP6 tasks 1 to 3 (export, local mirror, session expiry).
4. WP5 (workspace) and WP4 (routing), since routing affects state restoration.
5. WP3 (library), then WP8 (overview).
6. WP7 (assessment and reveal flow). This is the largest piece and touches the trust boundary, so go slowly and read `server.py` reveal and assessment paths first.
7. WP9 (microcopy), WP6 remainder (skeletons, print), then WP10 (tokens and tests).

Commit or checkpoint after each work package so changes can be reviewed and reverted individually.

## 6. Completion checks (after every work package)

- Start the server with `python3 website/server.py --port 8765` against a disposable database, not the real one.
- Check affected views at about 375, 768 and 1280px wide.
- Keyboard-only pass over every new or changed control.
- Run the existing website and unit tests and the new checks; compare to the pre-flight baseline.
- Confirm public problem responses and previews contain no private fields.
- Confirm there are no new external requests (CDN, fonts, images) in the browser network log.
- In your report, separate **observed** results from **assumed** ones. Do not claim a browser, test or SQLite check you did not run.

## 7. Out of scope

- Dark mode or any theme switching.
- Multi-user accounts, authentication or any non-local deployment.
- Changing problem authoring, generation, review or release rules.
- Editing canonical problem statements or historical teacher PPCs.
- Auto-grading, proof checking or any new correctness claims in the UI.
- Resetting, importing or restoring any database.

## 8. Questions to put to the owner (ask only if blocking)

1. If an API change is needed for the assessment view or drafts page, may the agent add a read-only student-data endpoint?
2. Should scratch notes be local-only (browser) or stored in the studio database?
3. For the merged status and progress filter, which wording does the owner prefer?
4. May a Playwright and axe-core dev dependency be installed locally for tests, or must everything be vendored?
