# ARDS — Algorithmic Reasoning Development System

## Instructions for coding agents

This repository uses Codex-compatible instructions: a small root [AGENTS.md](AGENTS.md) and task-specific Markdown skills in `.agents/skills/<name>/SKILL.md`. Do not load every workflow into every task. Select `classic-racg` when generating/publishing problems, `ppc-verification` for formal proofs, `learner-assessment` for grading/exposure, or `ards-website` for UI and server work. Technical specifications remain in `references/` and authoritative live records remain in `data/ards.db`.

The previous oversized root instructions were archived under `audit/instruction-refactor-20261020/`. The old root `SKILL.md` is retired in favor of discoverable skill folders. This follows OpenAI's guidance on focused skills, progressive disclosure, and minimal globally applied instructions: https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra and https://developers.openai.com/blog/skills-agents-sdk.


## Comprehension and specification correctness (required)

**Authoring and independent reviewing use
[the six-level comprehension standard and worked examples](references/specification_comprehension.md).** Each level has a separate list of assumed prerequisites, explanation obligations, acceptable and rejected statement fragments, and an explicit comprehension test.
Levels 1–3 must communicate the problem's objects, operations, relationships,
and goal without requiring previous study of the algorithmic topic.
In particular, Level 1 explanations define technical relationships in
ordinary words rather than presuming graph-theory background. Levels 4–6
may make mathematical interpretation and specialist language part of the
challenge. **All levels** must have unambiguous rules, symbols, edge cases,
and complete stdin/stdout formats, without disclosing the algorithm.

An approving independent review now needs a structured
`specification_review` matched to the recorded difficulty and concrete
evidence for notation, prerequisites, I/O, and ambiguities. It remains an
AI/human audit rather than a machine proof of clarity. See
[the review protocol](references/independent_review.md).

## CodeChef-style problem design — required for new RACG problems

Before new Classic RACG authoring or statement review, read
[the contest problem design protocol](references/contest_problem_design.md).
It translates the learner's 48 CodeChef examples and the **RACG-0040
ACCEPT/REJECT rewrite** into a concrete workflow: design a distinct reasoning
challenge, explain the objects/operations and valid answers **before**
introducing judge command tokens, preserve meaningful difficulty, and never
leak the algorithm. For Levels 1–3, the reader must understand the rules
without already knowing the tested topic. The six-level comprehension profiles
and the private PPC standards remain mandatory in addition to this protocol.

These are **future-generation instructions**, not retroactive edits to the
130 already released challenge packages or their judge input contracts.

## Multi-problem Classic RACG batch authoring

Use the persistent **batch queue** for requests such as “generate 100 new problems.”
The full implementing-agent procedure is in [references/batch_authoring.md](references/batch_authoring.md).

```bash
# Read before creating another batch; never reroll an existing queue:
python3 scripts/ards_batch.py status
# Only when no batch exists:
python3 scripts/ards_batch.py create --count 100
# Author all selected slots, each with a private four-part PPC:
python3 scripts/ards_batch.py next
# See counts across drawn/drafted/under_review/verified/released/rejected:
python3 scripts/ards_batch.py status --full
```

**Reservations are not finished problems.** Each selected slot must receive a
complete student statement **and** private P1/P2/C/K; its registered package is
independent from verification and publication. An unsupported model family
stays under review while the AI continues authoring other problems. No
unverified draft is exposed in the learner website. Independent AI-assisted
review requires separately authored executable candidate and oracle,
reproducible tests, written proof critique and immutable evidence before each
release: see [references/independent_review.md](references/independent_review.md).
A single unbatched pending challenge is adopted as the first batch item without
rerolling. Brand-new databases number the first RACG selection `RACG-0001`.

## Safe future resets

The maintenance command is **preview-only by default**. Stop the local ARDS
website first, review the reported counts, and confirm explicitly:

```bash
python3 scripts/reset_ards.py                              # preview: no changes
python3 scripts/reset_ards.py --confirm-reset              # archive state, initialize empty DBs
python3 scripts/reset_ards.py --confirm-reset --no-backup  # delete active state permanently; no new archive
```

Backups are checksum-verified and saved outside the repo in the sibling
`ARDS-reset-backups/` directory, including registered problems, draft PPCs,
independent reviewer files, exports, and history. Tests use disposable
databases and do not restore archived challenges.

## Formal reference PPC standard (P1 and C)

For all newly generated problems, Codex must follow
[the PPC authoring specification and Ticket Window worked proof](references/ppc_authoring_style.md).
P1 defines the full admissible input domain, constraints and exact output
relation, plus applicable feasibility/optimization and boundary conventions.
C states a quantified claim about the actual P2, proves the P1 obligations
with a suitable argument, and justifies termination and edge cases. Levels
1–6 share the same requirement for mathematical rigor.

Teacher PPCs must be authored as **Markdown with KaTeX**, using `\(...\)`
for inline math and `\[...\]` for centered equations. Show meaningful proof
steps in separate paragraphs rather than a flat block. The reference modal
renders these formulas offline; its legacy ASCII conversion improves old PPCs
only when an expression is unambiguous and does not edit stored references.
A fully reformatted historical PPC requires a versioned correction and
appropriate re-review.

For independent batch publication, `scripts/ards_review.py` now requires
a separate private `ppc_review` with quoted domain/output and
claim/reasoning/termination evidence, substantive analysis, and an explicit
P1-to-C obligation mapping. Missing or unsupported evidence blocks approval.
See [the independent-review contract](references/independent_review.md).
This checks report structure and source traceability, **not** mathematical
truth or completeness; AI review and bounded tests are not theorem proofs.
Previously released packages are not silently rewritten.

## PPC assessment (review required)

A learner submission is **saved, not auto-graded**. The separate assistant
reviewer can load the verbatim attempt and prepare a P1/P2/C/K critique:

```bash
python3 scripts/ppc_assess.py packet 123
# An AI or human reviewer independently writes a JSON report with a reasoned
# finding, evidence and uncertainty for each of the four sections.
python3 scripts/ppc_assess.py record 123 --file review.json
```

The recorder checks evidence and rubric structure and writes a versioned
assessment but does **not** calculate mathematical correctness by itself.
`undetermined` remains unknown; formal proof must use an actual proof checker.
See `references/assessment.md` and `references/ppc_assessment_workflow.md`.

## Fresh ARDS baseline — 2026-10-21

On 2026-10-21 the learner authorized another full reset **without a new backup**. The 10 active challenges (8 released), nine independent reviews, one authoring batch, and two solution reveals were permanently discarded. The active `data/ards.db` and `data/ards-studio.db` were initialized with empty schemas, and per-challenge reviewer/authoring files, exports, and active data validations were cleared. The four older external archives were not touched and are **not active inputs**. Never import or reuse previous challenge records unless explicitly requested; the next Classic RACG selection starts at `RACG-0001`. `python3 scripts/memory.py init` creates an empty schema without importing legacy examples. Tests use isolated fixtures under `tests/fixtures/legacy/`, not production history.

**New-problem invariant:** register/release a complete Classic RACG problem
only with its private four-section `teacher_ppc` (P1/P2/C/K). Every queued batch problem must also pass the database-backed text stdin/stdout gate and a separate, hash-bound independent review. A first-party test pass alone is insufficient. The private
reference accompanies the package but does not appear in the public problem
until the learner explicitly reveals it. Verification scope must be reported
honestly.

Historical examples and old descriptions below document former workflows,
not current saved learner progress.

## PPC 3.0 restricted formal verification (October 2026)

PPC 3.0 is available via `references/ppc3_spec.md`, `scripts/ppc3.py` and `scripts/ppc3_stress.py`. This implements two explicitly scoped **machine-checked mathematical fragments**: natural-deduction propositional proofs and exact total-correctness checks for fully enumerated finite transition systems. It is NOT an unrestricted theorem prover or a proof of the correctness of arbitrary Java programs. An optional fragment proof may be attached to an ARDS problem package; ARDS does not promote the entire problem to machine-proved based on that fragment. A Lean 4 example/bridge is prepared (`references/PPC3Examples.lean`, `scripts/ppc3_lean.py`), and was verified with installed Lean 4.35.0 and bundled `leanchecker`: all three specifically named example theorems compile and pass standard kernel replay. The pricing theorem uses standard `propext`. This is not a proof of correctness of generic ARDS or Java code. The archive at `data/validation/ppc3/seed-20261022-n100/` holds 100 verified propositional templates and 100 finite-state models. This benchmark did not draw new RACG challenges or modify learner history.

The hardened Lean bridge also checks `PPC3Expected.lean` and the abstract soundness theorem in `PPC3RuleSoundness.lean`. It pins reviewed sources, requires offline bubblewrap isolation, limits thread stacks to 64 MiB and address space to 4 GiB, and records each run separately. Use `python3 scripts/ppc3_lean.py --fresh` only when requesting a separate import replay; no external-checker result is inferred. The abstract theorem does not verify the Python implementation.

Strict JSON rejects duplicate members and non-finite numbers; resource-limit outcomes are distinct from mathematical rejection. New benchmark outputs live under `data/validation/ppc2/hardened-v1/` and `data/validation/ppc3/hardened-v1/`, with checker/generator hashes and Python versions. Earlier archives are preserved.

Quick commands:

    python3 scripts/ppc3.py lean-status
    python3 scripts/ppc3_stress.py --count 100 --seed 20261022
    python3 -m unittest discover -s tests -v

## ARDS 2.0 verified workflow (October 2026)

Classic RACG (Randomized Algorithmic Challenge Generator) remains the default random difficulty mode, without any Level 2 mastery cap. ARDS 2.0 adds 30 reasoning patterns, an auditable Z pattern roll, formal mathematical problem packages, test-gated release for seven built-in mathematical families, append-only corrections, evidence-only pattern statistics, and student/teacher archive exports. Historical challenges, attempts, assessments and the original random O/X/Y/P remain preserved.

**Start here:** See [ARDS 2.0 workflow](references/ards2_workflow.md), then run `python3 scripts/ards2.py archive` and `python3 -m unittest discover -s tests -v`.

New releases require a source-bound registered reference, prepared explicitly with `ards2.py prepare-reference --file authored.json --out reference.json` before registration. Unbound authored solutions remain experimental. The tested subject is the built-in reference and samples; authored algorithms, story/model correspondence and implementation refinement are not proved. See [hardening and migration](references/hardening.md).

The strict bounded oracle verifier is currently limited to seven first-party families; generated problems outside those families remain experimental until separately validated. PPC 3.0 adds optional fragment-level checking but does not remove this restriction. Passing finite tests does not establish a universal formal proof. Older `memory.py present` remains for backward compatibility, but is not a verification-gated publication path.


Persistent offline learner records with a SQLite database, FTS5 challenge search, randomized practice selections (RACG), a proof-oriented assessment protocol (PPC), and conservative analytics.

**Primary data location:** data/ards.db (SQLite). No external cloud account, network service, or vector database is needed. Python 3.12+ standard library is sufficient.

## Open an existing ARDS session

Run from this directory:

    python3 scripts/memory.py status
    python3 scripts/memory.py list
    # The archive starts empty; use show only after generating a new challenge.
    python3 scripts/racg.py --status
    python3 scripts/analytics.py

For coding assistants, the concise repository policies live in [AGENTS.md](AGENTS.md). Task-specific workflows are in [`.agents/skills/`](.agents/skills/): `classic-racg`, `ppc-verification`, `learner-assessment`, and `ards-website`. Open only the relevant skill and references for the current task. Inspect the current challenge without drawing a new random problem; retrieve it from SQLite using the `show` command when appropriate.

## Legacy memory lifecycle (not an ARDS 2.0 verified release)

1. **Draw, if requested**: python3 scripts/racg.py
   - Draws O and P for every new random selection, Y always, X only on the new-topic branch.
   - Stores the selection with status "selected", a unique ID, and original rolls in SQLite.
   - Won't draw another while an unpresented "selected" record is pending.
   - A selection is NOT a verified challenge statement. Don't claim otherwise.

2. **Author and present the full problem**: an assistant must create an original, internally checked statement whose category, difficulty, and story/direct style match the saved draw. Use the full statement (including constraints and examples), not just a summary:

       python3 scripts/memory.py present RACG-0003 --title "Example Challenge" --stdin

   Pass complete problem text on stdin; or use --file path/to/statement.md. Optional --constraints-file constraints.json and --notes. Check history FIRST:

       python3 scripts/memory.py search "candidate keywords"
       python3 scripts/memory.py near --file proposed_problem.md

   "near" is a lexical TF-IDF cosine similarity check, not neural semantic embeddings. The presentation command itself also returns exact-duplicate and lexical-candidate warnings; human judgment is required. Do not change randomized topic/difficulty to avoid a duplicate. For a genuinely unusable *unpresented* draw, retain an audit reason:

       python3 scripts/memory.py abandon RACG-0003 --reason "Reason"

3. **Capture the user's original solution verbatim** before giving feedback:

       python3 scripts/memory.py attempt RACG-0003 --stdin --stage first --hint-level 0 --independent yes --confidence 85

   Use --independent yes ONLY when justified. If independence is unverified, omit it; it defaults to false. Confidence is valid only when supplied before feedback. Optional --minutes 9.6 --time-source self-reported. Never invent timing. For revision, use --stage revision; original first attempt cannot be replaced. If the original text is unavailable, use --provenance summary_only with accurate qualifiers.

4. **Grade with explicit evidence**, not just a score:

       python3 scripts/memory.py assess ATTEMPT_ID --reviewer assistant --correct yes --optimality yes --time-complexity "O(N)" --space-complexity "O(1)" --evidence "Proof/verified cases and explanation."

   Use --correct unknown / --optimality unknown for unavailable evidence. Optional --scores-file rubric.json with only genuinely observed fields from the 8-dimension rubric (values 0–4). Unobserved scores must remain NULL.

5. **Record grounded learning observations**, not personal guesses:

       python3 scripts/memory.py observe RACG-0003 --kind insight --concept "Prefix constraints" --evidence "Observed in learner's first attempt ..."

   A review can append a new assessment without erasing the original evaluation.

## Search, health, backup, tests

    python3 scripts/memory.py search "smallest missing number"
    python3 scripts/memory.py near --file proposed_problem.md
    python3 scripts/memory.py doctor
    python3 scripts/memory.py backup
    python3 -m unittest discover -s tests -v

Backups are timestamped under data/backups/. Backups are not automatically scheduled; run the backup command before high-risk maintenance and periodically. The built-in SQLite online backup API creates a consistent snapshot even in WAL mode.

## Data model and provenance

- challenges: IDs, original roll O/X/Y/P, canonical or historical topic label, difficulty, statement and content hash, status, presentation, source provenance.
- attempts: immutable original first response plus append-only revisions/follow-ups; explicit hints, confidence, time and provenance.
- assessments: append-only correctness and optimality judgments with evidence and eight optional 0–4 rubric dimensions.
- observations: strengths/weaknesses/insights/uncertainty only with supporting evidence; never freely infer an internal trait.
- challenge_fts: indexed FTS5 full-text search over titles, topic names and statements.
- analytics: first-attempt independence and success reported separately from assisted revisions; no fabricated metrics. Confidence calibration is withheld for very small samples.

**Historical records imported:** B1 (Non-Decreasing Sequence) is a summary-only independent success with earlier self-reported 9:36, confidence 95%, and provisional 21/24 score on a legacy scale. The imported snapshot described RACG-0002 (Missing ID) as unanswered. Current SQLite records mark it evaluated; RACG-0003 (Lanterns for the Night Market) remains presented and unanswered. Query SQLite instead of using that snapshot as current state. Historical roll X=757785, Y=75816 and topic label #86 "Missing Elements" are preserved verbatim even though the v1.1 canonical catalog calls #86 "Convex hulls".

Legacy data/progress.csv, data/last_challenge.json and data/draws.jsonl are kept for provenance; SQLite is authoritative going forward. RACG mirrors current selections to racg_state.json/draws.jsonl for compatibility when possible. "last_challenge.json" is an imported historical snapshot, not always the latest challenge.

## Boundaries

- All code uses local SQLite and Python's standard library; no network calls or external AI embeddings.
- Search is word/lexical similarity, not semantic reasoning. Future embeddings should be a replaceable index keyed by challenge ID, never the source of truth.
- This is performance tracking, not a validated standardized intelligence assessment. Avoid claims of objective certainty from AI grading.
- Longitudinal comparisons require matched topics, difficulties, help levels and comparable conditions; random RACG outcomes alone do not measure growth fairly.
- Local assistant filesystem access remains subject to MCP permissions. Ordinary ChatGPT memory does not automatically update this directory; the assistant must explicitly read/write via the connected filesystem integration on each supported session.
