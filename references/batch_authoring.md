# Classic RACG batch authoring (verification-safe)

This document is for the AI carrying out a user's request such as **"generate 100 new Classic RACG practice problems with their PPCs."** It defines a two-stage pipeline: complete **authoring**, then independent **verification and publication**.

**Do not stop at the first unsupported verifier.** A problem can be fully authored, with a complete private PPC, and remain unreleased under review. This must not block the remaining 99 problems.

## 1. Authoritative queue: reserve first, never re-roll

From the ARDS repository root:

```bash
python3 scripts/ards_batch.py status
# If there is no batch yet, exactly once:
python3 scripts/ards_batch.py create --count 100
python3 scripts/ards_batch.py status
python3 scripts/ards_batch.py next
```

**Normally, if a batch already exists, resume it instead of starting a new one.** When the learner explicitly requests an **additional, separate batch while an earlier batch remains unfinished**, use `python3 scripts/ards_batch.py create --count 20 --parallel` exactly once. The older unfinished batch remains the implicit default of `status` and `next`, protecting a concurrent Codex authoring session. Work on the additional batch with explicit `--batch ID` for `status`, `next`, and `sync`; do not take over the older queue. The parallel draw sequence begins from the last reserved RACG selection, not the last released challenge, and preserves the authentic continuation rule. Independently register and verify each item with its own challenge ID; *reserving* 20 items does not mean 20 published problems. The queue is in canonical `data/ards.db`; it records a unique `batch_id`, 1-based ordinals, challenge IDs and statuses, and the true Classic RACG O/X/Y/P rolls on each challenge. Z and the eligible/selected reasoning pattern are stored in `reasoning_plans`.

Any single **unbatched, already selected** challenge is adopted as the first of the requested 100; no reroll and no extra challenge. Example: if `RACG-0002` already exists, a 100-item batch can reserve that exact selection plus 99 additional genuine rolls. The former first-ID bug has been fixed for genuinely empty databases: the first draw is `RACG-0001`. Existing IDs must **never** be renamed.

The within-batch "previous challenge" for the 15% continuation branch is the previous **queued selection**, not the previous released problem. This is intentional: 100 independent selections must be possible without forcing a release between them. X is absent for continuation; every problem has its own O, Y, P and Z. No modulo bias, fabricated draws or convenience rerolls.

You must not use the legacy `python3 scripts/racg.py` drawing command to generate further selections while a batch is pending. Instead use `ards_batch.py next` and the recorded selections.

## 2. Author ALL slots (the 100-problem output)

For each `next` item with `stage=drawn`:

1. Read the queued challenge/topic/difficulty/presentation and immutable primary pattern. These are authoring constraints. **Read and apply BOTH `references/contest_problem_design.md` (the CodeChef-based original problem design procedure, exact RACG-0040 reject/accept worked case and nonspoiler checklist) AND the SIX operational profiles and accept/reject examples from `references/specification_comprehension.md` for the exact rolled level.** Levels 1–3 must be understandable without knowing the tested topic; Levels 4–6 may make mathematical comprehension part of the challenge, but cannot omit rules or introduce ambiguity. Do not raise apparent level by replacing plain language with unexplained technical terms. The author must explicitly define low-level topic-specific concepts, introduce new symbols and roles, and explain operations and objectives without algorithm hints. Build an **original**, mathematically well-defined reasoning challenge with a meaningful objective (possibility, construction, optimality, inference, counting, transformations, etc.), then write its **learner description BEFORE encoding operations as command tokens**: define the objects and state, what each action does and when, what output is correct, and relevant exceptions. The RACG-0040 original one-sentence command-code-first description is **not acceptable as a new Level 1 task**; its worked rewrite in the design standard is the reference. For new problems, avoid artificial unused input fields, cosmetic data-structure stories, inadvertent solution hints and near-duplicate task designs. Give explicit input/output semantics, constraints and diverse independently checked examples. Observe the Classic RACG story/direct draw; never adjust the rolled difficulty to fit an easier verifier family.
2. Construct a complete **private teacher PPC** in the same package, following `references/ppc_authoring_style.md` (the learner's six PPC examples), with concise problem-specific formal reasoning rather than fixed boilerplate: four nonempty sections `teacher_ppc.problem`, `teacher_ppc.procedure`, `teacher_ppc.correctness`, `teacher_ppc.complexity`. The correct solution, algorithm details and proofs must not leak into public statements or previews. The model, samples, and reference should be rigorous; creating a PPC is **not** proving it.
3. Make the student-facing statement follow `website/PROBLEM_AUTHORING_STANDARD.md`: **no per-sample Explanation and no Note section; move all necessary rules into description, Input Format, Output Format, or Constraints**. Store `statement_display` as structured fields; validate it with `python3 website/validate_display.py PACKAGE.json`.
4. Before registration, perform BOTH the **reasoning-design and meaning-before-encoding audit** in `references/contest_problem_design.md` and the reader-facing six-level specification audit from `references/specification_comprehension.md`: check that the **description alone** introduces what exists, how actions/conditions work, what changes, and the required result; codes merely encode those rules. Check that the challenge genuinely fits the recorded level and is not an algorithm prompt or a disguised previous problem. Confirm unfamiliar terms are defined for Levels 1–3, all I/O semantics and impossible cases are decidable, and the visible statement agrees with the internal model. Repair unclear statements **before** registration. Independently confirm the reference solution produces each sample output using a real execution/oracle when possible; save the command, seed and oracle scope. For exhaustive reasoning problems, explicitly state how the exhaustive reference was checked. A prose-only sample guess is not a verified oracle.
5. Save the *draft* package at `data/authoring/<challenge-id>/package.json` and call `python3 scripts/ards2.py register <challenge-id> --file <path>` only after all required fields are complete. Registration stores the package as immutable experimental teacher material; it does **not** release the problem. It blocks missing or incomplete PPCs.
6. If the selected domain currently lacks a reviewed verifier, **do not abandon the selection or quit the batch**. Mark it for review:
   `python3 scripts/ards_batch.py review <challenge-id> --reason "No reviewed family-specific independent oracle yet"`
   and continue to the next `drawn` item.
7. Save a progress/checkpoint after each problem or small chunk. For long sessions, periodically report counts, but continue rather than asking the user whether to produce real problems versus a validation corpus. The user has already explicitly requested actual practice problems.

For a registered problem, the queue dynamically reports `drafted` even if not yet explicitly synced. A draft **does not** show as a student practice problem.

## 3. Independent verification/review (per item)

For each registered package, try the applicable verification path:

```bash
python3 scripts/ards2.py verify RACG-XXXX
python3 scripts/ards_batch.py status
```

Current first-party bounded reference verification supports **seven model families**, not all 100 topics or every randomized difficulty. When the result is `experimental` or `failed`, the queue stage becomes `under_review` (not published); note why, then proceed to other items. Do not modify draws to make the problem fit the seven families.

For every queued batch item, a `test_verified` first-party run alone is **not** sufficient for `verified` queue status or publication. An independent AI reviewer must provide separately authored executable candidate and oracle, realistic stdin/stdout parsing, differential tests, and substantive written findings as defined in `references/independent_review.md`. The release gate checks hashes of the package, reviewer source, report, and review runner before publishing:

```bash
python3 scripts/ards2.py release RACG-XXXX
python3 scripts/ards_batch.py sync
```

Registered batch drafts and their PPCs remain **private to the review CLI**, not visible in the learner website. Follow `references/independent_review.md` to construct and execute separate reviewer algorithms and written analysis; only successfully and independently reviewed releases are visible/assessable. Never mark generated proofs as kernel-certified without Lean evidence of the exact theorem. Missing independent verification never converts into success because a model confidently asserted its proof.

Reject a genuinely incorrect authored problem with a justified reason; keep its immutable draws and package. For a correction **before first release**, write a full corrected package with all four private PPC sections and append an immutable revision:

```bash
python3 scripts/ards2.py revise-draft RACG-XXXX --file data/authoring/RACG-XXXX/corrected.json --reason "Fix the statement, sample, or proof gap"
python3 scripts/ards2.py verify RACG-XXXX  # old verification is now stale
```

The original draft is preserved and **no previous verification evidence can release the corrected package**; evidence must be collected for its new hash. The queue can then resume independently. Corrections **after release** use the existing `ards2.py amend` workflow. Avoid treating `rejected` as permission to reroll.

## 4. Status and recovery

```bash
python3 scripts/ards_batch.py status
python3 scripts/ards_batch.py status --full
python3 scripts/ards_batch.py next
python3 scripts/ards_batch.py next --stage under_review
python3 scripts/ards_batch.py review RACG-XXXX --reason "Proof obligation still open"
python3 scripts/ards_batch.py reject RACG-XXXX --reason "Counterexample invalidates stated output"
python3 scripts/ards_batch.py reopen RACG-XXXX --reason "Explicitly reviewed correction planned"
python3 scripts/ards_batch.py sync
```

Stages have exact meanings:

| Stage | Meaning |
| --- | --- |
| `drawn` | Genuine topic/difficulty/presentation/pattern saved; problem not yet registered |
| `drafted` | Registered complete package including private P1/P2/C/K, not verified |
| `under_review` | Unsupported verifier, failed evidence, or explicitly identified proof gap |
| `verified` | Matching independent executable review and evidence integrity checks passed; **not a theorem** |
| `released` | All current release gates passed; appears in student library |
| `rejected` | Explicit recorded rejection; no silent reroll |

Verification does not block authoring other items. The workflow should aim to have all 100 slots at least `drafted` or `under_review` with complete private PPCs. Release only what has genuine matching evidence. Never stop the 100-slot authoring pass after the first experimental verification result.

## 5. Completion contract for the implementing AI

When the user asks for 100 problems, the batch is **not completed** merely because `create --count 100` reserved 100 selections. Report distinctly:

- number of genuine selections queued
- number of problems whose **complete statements + private PPCs** are registered
- number still awaiting authoring
- number under review (and why)
- number passing current verification
- number actually released
- exact validation/test commands executed, and known unverified claims

Do not describe `drafted` as `released`, `test_verified` as a universal proof, or a story-selection as a finished problem. Keep the user's existing answer-reveal and independent-score preservation behavior.

See `.agents/skills/classic-racg/SKILL.md`, `references/racg.md`, `references/ards2_workflow.md`, and `website/PROBLEM_AUTHORING_STANDARD.md` for details.
