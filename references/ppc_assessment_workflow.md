# Evidence-backed PPC assessment

The goal is to evaluate **the learner's own mathematical reasoning**, not to
award credit merely because the submitted algorithm resembles a teacher PPC.

A P1/P2/C/Complexity submission in ARDS Studio is always archived as an
**ungraded attempt**. Grading requires a separate human/AI review, which is
only as trustworthy as the mathematical evidence the reviewer supplies.

## Prepare a review packet

```bash
python3 scripts/ppc_assess.py packet 123
```

This reads an existing attempt and returns its verbatim submission and the
public problem statement, without revealing the private reference PPC.
An AI reviewer must reason through P1 validity, P2 execution, C proof, and
the time/auxiliary-space analysis. Consider valid *alternative* algorithms,
edge cases, overflow, termination, and counterexamples.

## Structured review report

A review file supplied to `ppc_assess.py record` must be JSON with:

- `reviewer_kind`: `ai` or `human`; `reviewer`: nonempty identity.
- `verdict`: `correct`, `incorrect`, or `undetermined`.
- `proof_assurance`: `reasoned_review` or
  `executed_counterexample` (with reproducible input, expected, actual,
  reproduction). **Do not claim formal proof** through this command.
- `sections`: exactly `problem`, `procedure`, `correctness`, and
  `complexity`; each records a `status` of
  `supported`/`incorrect`/`incomplete`/`uncertain` plus a
  **problem-specific** finding and mathematical evidence.
- Optional `scores` only for the eight rubric dimensions from
  `references/assessment.md`, values 0–4 or null (unobserved).
- A correction of an earlier assessment must explicitly cite its
  `supersedes_assessment_id`, preserving the original assessment record.

The recorder rejects `correct` unless all four sections are `supported`,
and refuses `incorrect` unless at least one section is explicitly shown
incorrect. It preserves an `undetermined` verdict as NULL/unknown. A
report's prose can still be wrong: **structure validation is not proof**.

```bash
python3 scripts/ppc_assess.py record 123 --file report.json
```

The command stores the complete evidence report with its reviewer label,
and the public UI continues to distinguish submission from verified grading.
Do not fabricate a timer, hint history, confidence measurement, or successful
independent assessment. Revealing the reference PPC follows the separate
append-before-disclosure policy.

## Remaining work

- The local Python process does **not** call a language model to grade PPC
  submissions. An available AI reviewer must produce the evidence report.
- There is no generic mechanical proof checker for arbitrary Java or natural-
  language PPCs. Only restricted formal fragments can be kernel checked.
- The UI currently stores attempts; it does not provide the full interactive
  grading/appeal workflow. Add one only when there is a trustworthy assessment
  service and auditable evidence trail.
