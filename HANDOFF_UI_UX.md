# ARDS Studio UI/UX — Handoff

*Written 2026-10-22. Repo: `~/MyFiles/AI/ARDS`. Task: implement `ARDS_Studio_UI_UX_Implementation_Spec.md` package by package.*

## 0. Read these first, in this order

1. `ARDS_Studio_UI_UX_Implementation_Spec.md` (the task; **save a copy into the repo root if it is not there**). Section 1 constraints beat everything else.
2. `AGENTS.md` and `README.md` (project invariants: privacy, reveal gate, no DB resets).
3. This file.

## 1. Hard rules (from spec section 1, abbreviated)

Light-only, no external runtime deps (no CDN/fonts/images), local-only server with session token + origin checks + CSP, Markdown never executes HTML, **never expose teacher PPC/reference/proof/hidden tests**, unreleased problems stay 404, reveal needs consent and the exposure record is written **before** the response, never fake grades/status ("Undetermined" is its own state), **never modify `data/ards.db` or `data/ards-studio.db`**, never run `scripts/reset_ards.py --confirm-reset`, never edit historical statements/proofs. Use `--db` and `--draft-db` with temp files for any manual server run.

## 2. Status

| Package | State | Commit |
| --- | --- | --- |
| Pre-flight (spec s3) | **Partly done by reading code** (see s4). Browser items still unverified | - |
| WP1 Editor core | Done in code: Write/Preview, symbol palette, per-section outlines, save states, submit confirmation, tab arrows, Tab/Enter list behaviour (`editor.js`) | `ede6c0f` |
| WP6 tasks 1-3 | Done in code: export drafts, localStorage mirror, session-expired banner | `ede6c0f` |
| WP2 Accessibility | Done in code: AA contrast on all text, dialog Tab trap + focus restore (workspace dialog and search palette), focus-visible rings, reduced motion, 13px attestation label | `606066d` |
| Startup bug fix | Done (see s3) | `566d0b2` |
| WP3 Library | **Markup exists in `index.html` but is NOT wired** (filter collapsing, chips, continue card). Inline search, merged status filter, label cleanup, level pips, view-state persistence not done | - |
| WP4 Routing | Not started (see s4: hash routes partly exist) | - |
| WP5 Workspace | Not started. Statement mini-nav markup exists, unwired | - |
| WP6 remainder | Not started: skeleton loaders, print stylesheet | - |
| WP7 Assessment/reveal flow | Not started (largest, touches trust boundary) | - |
| WP8 Overview | Not started. Level-progress markup exists, unwired | - |
| WP9 Microcopy | Not started | - |
| WP10 Tokens + Playwright/axe + privacy test | Not started | - |

Recommended order for what is left: finish pre-flight, **WP5 + WP4**, **WP3** (wire existing markup), **WP8**, **WP7** (read `server.py` reveal/assessment paths first, go slowly), **WP9**, WP6 remainder, **WP10 last**.

## 3. The bug that was just fixed (and a trap to avoid)

Symptom: library showed "Could not connect to ARDS: Cannot read properties of undefined (reading 'bindTextarea')".
Cause: the already-running server process predated the `/editor.js` route in `server.py`, so it returned 404 for it (`window.ARDSEditor` undefined). Static files are read from disk per request, but **Python routes only change after a server restart**. The new `app.js` loaded, the old server did not know `editor.js`.
Fix applied: editor helpers are now optional in `app.js` (plain textarea fallback, clear toast), and startup errors are no longer mislabeled as connection errors.
**Rule: after any `server.py` change, restart the server, then hard-refresh (Ctrl+Shift+R).** The owner must restart their running server once for the real fix to show full editor features. Any new static file needs a route in `server.py` (it whitelists files).

## 4. Pre-flight findings so far (observed in code, not in a browser)

- **Routing:** hashes exist for `#/` (library), `#/problem/<ID>`, `#/overview`, `#/method[/chapter]`. `goLibrary()` uses `history.replaceState`, so Back from a problem likely does not return to the library (**VERIFY in browser**).
- **`nav-drafts` ("My PPC workspace")** has no list page: it opens `state.lastSelected` or shows a toast "Open a problem to start your PPC draft."
- **Endpoints seen in tests/code:** `GET /api/session`, `GET /api/facets`, `GET /api/overview`, `GET /api/problems` (params: `q`, `page`, `per_page` in allowed sizes, `difficulty`, `topic`, `sort`, `progress`, `status`, `presentation`, `similar_to`), `GET /api/problems/<id>`, `GET /api/problems/<id>/similar`, `GET|POST /api/drafts/<id>`, `POST /api/submissions/<id>`, `POST /api/reveal/<id>`. Read `server.py` before adding any endpoint.
- **Library search:** only the command palette (`/`, Ctrl+K) uses `q`; verify there is no inline search.
- **Not yet checked:** narrow-layout clipping (spec s3 item 3), textarea undo on tab switch (item 5), what the user sees when the token expires mid-autosave (item 6; WP6 banner exists, never exercised in a browser).

## 5. How to work and verify

```
cd ~/MyFiles/AI/ARDS
python3 -m unittest discover -s tests -p "test_*.py"      # baseline: 165 tests OK, 1 skipped
node --test tests/editor_logic.test.mjs                    # baseline: 8 pass
node --check website/public/app.js                         # syntax check after edits
# manual run, DISPOSABLE data only:
python3 website/server.py --port 8765 --db /tmp/ards-test/ards.db --draft-db /tmp/ards-test/studio.db
```

Python tests use temp databases, so they are safe. `tests/test_accessibility.py` enforces text contrast >= 4.5:1 (decorative marks >= 3:1), focus and reduced-motion rules, and no dark theme: do not weaken it. Commit after each package with a message naming the WP.

Tool notes for this environment: the scoped-commander MCP (`run_command`, `read_file`, `edit_file`, `write_file`, ...) is guarded. Allowed binaries: node, npm, npx, git, python3, grep, iptables, wget, dpkg, apt, sudo. `cwd` must be inside allowed paths. Do not repeat the binary name inside `args`. Python can be run via `args:["-"]` with the script in `stdin`. Playwright browsers must not be downloaded without asking the owner.

## 6. Verification that has NOT been done (do not claim it)

No real-browser run of anything built so far. Specifically unverified: Write/Preview KaTeX parity with the reference modal, save-state labels after a forced failure, submit-confirmation cancel path, keyboard-only walkthrough, layout at 375/768/1280px, axe-core, network log showing zero external requests, privacy of the new export and mirror. Treat these as owed to WP1, WP2 and WP6 acceptance criteria. Final reports must separate observed from assumed results.

## 7. Open questions for the owner (ask only when blocking)

1. May a read-only, token-protected student-data endpoint be added (assessment view, drafts page)?
2. Scratch notes (WP5.7): browser-only, or in the studio DB?
3. Preferred wording for the merged lifecycle filter (WP3.3)?
4. May Playwright and axe-core be installed as local dev deps, or must they be vendored (WP10)?

## 8. Starter prompt to give the new AI

> You are continuing a UI/UX implementation in `~/MyFiles/AI/ARDS` (a local, light-only, offline algorithm-practice website in `website/public/`). Read, in order: `ARDS_Studio_UI_UX_Implementation_Spec.md`, `AGENTS.md`, `README.md`, then `HANDOFF_UI_UX.md`. Constraints in spec section 1 override everything; never touch `data/*.db` or run `reset_ards.py`. Check `git log` and the handoff status table, run the baseline tests in handoff section 5, then continue with the next package in the recommended order (WP5 + WP4). Restart the local server after any `server.py` change. Commit after each package, run the completion checks in spec section 6, and report only checks you actually observed. Ask me only the owner questions in handoff section 7 that actually block you.

## Continuation checkpoint — WP5 (2026-10-22)

WP5 is implemented in `app.js`, `workspace-ui.js`, `statement-renderer.js`,
`index.html`, and `workspace.css`: exact sample copy, sticky section navigation,
keyboard/pointer split (30–65%, persisted), existing Focus mode, narrow Problem /
Write switching, persisted reading size/width, student-only Markdown copy,
browser-only per-problem scratch notes (never submitted), self-check questions,
and Alt+1–4 / shortcut dialog. Scratch storage failures show an explicit message.
Mobile PPC tabs now wrap into two rows rather than clipping the fourth section.
No API or canonical data changes. The pre-existing untracked `studio-logic.js`
was preserved and is not loaded or changed by this package.

Observed baseline and post-change suite: 165 Python tests OK (one skipped), 8 editor tests passed.
Browser checks used a temporary Playwright installation in `/tmp/ards-ui-check`
and the already cached Chromium; no browser downloaded. The synthetic disposable
website fixture was used at 375, 768 and 1280px. Checks passed for mobile panel/text
preservation, no page horizontal overflow, divider keyboard adjustment, scratch
persistence, self-check list, byte-exact sample clipboard content, statement
Markdown copy, draft save/reload, no page errors and no external requests.
Screenshots are temporary under `/tmp/ards-ui-check/`. Screenshot inspection found
and corrected desktop footer overlap and narrow tab clipping.

Repeat browser checks: start `python3 tests/workspace_fixture.py`, then set
`ARDS_UI_TEST_URL` to the printed URL and run `node tests/workspace_browser.mjs`.
If Playwright is outside normal module resolution, set `ARDS_PLAYWRIGHT_MODULE`
to its `index.mjs`; set `ARDS_CHROMIUM_PATH` to the cached executable if needed.
Optional `ARDS_SCREENSHOT_DIR` selects an existing screenshot directory.
This is a WP5 smoke test, not the complete WP10/axe suite. Full keyboard-only
walkthrough and axe remain outstanding. Routing (WP4), library (WP3), overview,
assessment/reveal, microcopy, remaining WP6 and WP10 still need implementation.
