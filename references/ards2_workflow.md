# ARDS 2.0 — verified archive workflow

## PPC 2.0 integration (October 2026)

PPC 2.0 is a stand-alone formal specification and structural contract-checking protocol. Read `references/ppc2_spec.md`. For new ARDS problem packages, include a `ppc` certificate bound by the canonical SHA-256 model hash, and validate the proof obligations before differential testing. All seven first-party families now support bounded oracle tests: tiered_price, opposite_rotations, comparison_maxima, missing_positive, range_sum, interval_lamps, graph_reachability.

Commands:
- `python3 scripts/ppc2.py check --file PACKAGE.json` — check PPC structure, obligation coverage, dependence cycles and model hash.
- `python3 scripts/ppc2.py stress --count 100 --seed 20261020` — regenerate the 100 deterministic validation packages, 7-family oracle comparisons and five negative controls. Archives are versioned by seed and problem count under `data/validation/ppc2/` and identical reruns are accepted without overwriting old results.
- `python3 -m unittest discover -s tests -v` — full regression tests.

**Crucial distinction:** `structure_checked` means the required statements have been provided but their logical truth has not been independently checked. `test_verified` means bounded oracle testing passed. Neither is a formal proof, and no `machine_checked` claims are supported. These 100 synthetic benchmark problems are distinct parameterized packages, NOT new Classic RACG lottery draws or the 100-topic catalog. They do not contaminate the production challenge archive. Teacher materials can include the certificate and its limited status; student materials must not reveal it.


## Status and scope

**RACG = Randomized Algorithmic Challenge Generator.** Classic RACG remains the default selector with 100 topics and six levels. As of v1.2 the difficulty weights are **30%, 25%, 20%, 12%, 8%, 5%** for Levels 1–6; continuation (15%) samples only levels at least as difficult as the prior one, renormalizing eligible weights **without clamping**. The 70% story rule and O/X/Y/P provenance remain. See `references/racg.md` for exact Y ranges. No mastery gate is in force.

This upgrade adds:
- Thirty typed reasoning patterns in three layers (see references/reasoning_patterns.json).
- Audited secondary Z pattern selection through the new plan command (never changes O/X/Y/P).
- Structured mathematical packages with an objective, constraints, reference solution, correctness argument, samples, estimated difficulty, provenance and reasoning patterns.
- Immutable package history, bounded differential verification, release history, versioned corrections, student/teacher exports, and observed per-pattern assessment statistics.
- Additive SQLite migration. All existing challenges, attempts, assessments, FTS5 search and original analytics remain compatible.

**Limits:** This is an AI/human-assisted authoring pipeline, not an autonomous theorem prover. Trusted automated reference-oracle validation covers seven mathematical families: tiered_price, opposite_rotations, comparison_maxima, missing_positive, range_sum, interval_lamps, and graph_reachability. Other topics may be selected and models stored as experimental, but cannot be automatically released by the strict 2.0 verifier without implementing a family-specific, independently reviewed oracle. Bounded tests are evidence, not a proof of correctness. Proof review and originality still require human judgment.

The original memory.py present command remains for legacy compatibility. It is not equivalent to the new verification-gated release path.

## Commands

Run commands from the project root.

- Inspect and back up: python3 scripts/memory.py status ; python3 scripts/memory.py doctor ; python3 scripts/memory.py backup
- Find history: python3 scripts/ards2.py archive
- Inspect a challenge: python3 scripts/ards2.py inspect RACG-0003
- Show reasoning catalog: python3 scripts/ards2.py catalog
- Inspect evidence profile: python3 scripts/ards2.py profile
- Run all tests: python3 -m unittest discover -s tests -v

## New verified challenge lifecycle

1. Draw exactly once: python3 scripts/racg.py. This persists the selected O/X/Y/P in SQLite.
2. Plan: python3 scripts/ards2.py plan RACG-XXXX. This draws and records Z and the eligible reasoning patterns without changing the original RACG draw. Never draw to merely inspect status.
3. Author a package as structured JSON, consistent with the actual selected topic, selected primary pattern and difficulty. See the two illustrative files under templates/. They do not grant permission to alter randomized metadata to match a template.
4. Prepare the registered reference in a NEW file: `python3 scripts/ards2.py prepare-reference --file my-problem.json --out reference-problem.json`. This explicitly replaces the proposed solution/argument with the registered family explanation and records its source binding; it does not validate arbitrary prose. Statement-to-model correspondence remains a review obligation.
5. Register: python3 scripts/ards2.py register RACG-XXXX --file reference-problem.json
6. Verify: python3 scripts/ards2.py verify RACG-XXXX. The result is failed, experimental or test_verified; test_verified means finite bounded oracle and sample checks passed, not a machine-checked universal proof.
7. Release: python3 scripts/ards2.py release RACG-XXXX. This publishes the statement and matching release record in one database transaction. Exact statement duplication blocks release; lexical neighbors are advisory.
8. Present the complete problem and Generation Report, without solution hints. Record attempts and assessments through memory.py.

A historically presented challenge (including the unresolved Lanterns for the Night Market) is not automatically retroactively marked ARDS 2.0 verified. Its original status remains untouched.

## Teaching exports

Student: python3 scripts/ards2.py export RACG-XXXX --edition student --out exports/RACG-XXXX-student.md

Teacher: python3 scripts/ards2.py export RACG-XXXX --edition teacher --out exports/RACG-XXXX-teacher.md

Student editions include the latest verified public problem text, original source, challenge ID, and revision number if amended. Teacher editions additionally include the reference solution, correctness argument, formal model, patterns, and sample cases. Teacher exports require a released ARDS 2.0 package. Existing export files are never silently overwritten.

## Corrections

python3 scripts/ards2.py amend RACG-XXXX --file corrected.json --reason "Clarified boundary case"

Amendments must carry a current registered-reference binding (prepare a new file before submitting the amendment). They must preserve difficulty, the selected primary pattern and problem family, and independently pass the corresponding first-party oracle. The original full statement and original package remain immutable, while exports pick up the latest published verified revision.

## Preservation, confidence and known gaps

- SQLite storage remains in data/ards.db. Use online SQLite backups before modifications and periodically. Backups are local, not automated off-device copies.
- New reasoning, package, verification, release and revision records are protected from updates/deletes by SQLite triggers.
- Recorded O/X/Y/P values and selected difficulty remain the source of truth. Difficulty uses the weighted v1.2 mapping for fresh new draws; historical old-version draw records are never reinterpreted. Z remains independent additional metadata.
- The descriptive pattern profile uses only known, graded first attempts on released v2 challenges. It does not infer IQ, mastery, or psychometrically calibrated ability.
- Generated or learner-submitted solver code is never executed. Automated verification uses only reviewed first-party Python functions.
- The existing FTS5 lexical search remains. Structural or semantic similarity detection across arbitrary mathematical models is still incomplete; there is no vector database.
- Proof review by another independent agent/human is not yet automated. Do not describe test_verified as formal proof.
- The full general-purpose generator/solver for all 100 topics is not implemented; generation beyond the first-party families remains AI-assisted and requires independent verification before publication.
- Source provenance should be retained; externally provided problems must not be represented as newly authored ARDS problems.

## Verified subject and immutable migration

See [audit hardening](hardening.md). `test_verified` describes the registered reference implementation and supplied samples. Verification records now include the exact source-bound reference identity, fragment fingerprint and attachment scope, and explicit unproved correspondences. An unbound authored solution remains `experimental`; any passing reference tests are separately labeled evidence and cannot authorize a new answer-key release. Older releases and assessments are not rewritten. A stale verification receipt cannot authorize a new release; rerun verification on the current checker. Benchmark provenance is versioned separately from historical archives.
