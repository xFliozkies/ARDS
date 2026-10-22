---
name: learner-assessment
description: Record an ARDS learner's algorithm attempt, evidence-based feedback, rubric assessment, or reference-PPC exposure.
---

# Independent attempt and assessment workflow

Use only when assessing user work, recording feedback/progress, or disclosing an answer. See `references/assessment.md`, `references/ppc.md`, and `scripts/memory.py` help for current interface details.

## Protect the independent attempt

1. Identify the challenge in canonical `data/ards.db` without rolling another problem or conflating old JSON/CSV snapshots with live state.
2. Capture the learner's original explanation **verbatim** before supplying hints, corrections, or solutions. Record stage, hint level, provenance, independence, and time **only when supported by evidence**.
3. Evaluate the proposed algorithm against the formal specification: find counterexamples where applicable; check invariants, termination, feasibility, optimality, and complexity. State uncertainty if a proof remains incomplete.
4. Append evidence-backed assessments and later revisions; do not overwrite the initial attempt. Use `references/assessment.md`. `python3 scripts/ppc_assess.py packet ATTEMPT_ID` retrieves the verbatim learner answer without exposing the teacher PPC; after an external AI/human reasoned review, `ppc_assess.py record ATTEMPT_ID --file REPORT.json` validates and records an uncertainty-aware four-section assessment. This CLI does not autonomously prove correctness. A new draft is not automatically passed or machine-verified.
5. Report observed strengths and weaknesses without claiming unsupported psychometric precision or fabricated timing.

## Answer exposure and preserved credit

A complete teacher PPC is private. If an AI shows it outside the website, **record exposure before showing it**:

`python3 scripts/solution_exposure.py mark RACG-XXXX --provenance chat`

The website records its own persistent exposure on explicit user confirmation. After reveal, subsequent attempts are practice-only, not independent assessment. An earlier **independent first attempt that had already been graded correct before disclosure** keeps its existing credit; ungraded/failed attempts do not gain that protection. Do not retroactively rewrite attempts to approximate this policy; use the existing immutable exposure record and its preserved attempt pointer.

Never reveal protected reference material casually during previews, hints, or list views. The learner's independent solution can be discussed and corrected without revealing the full teacher PPC unless requested.
