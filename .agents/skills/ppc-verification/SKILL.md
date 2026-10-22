---
name: ppc-verification
description: Formalize or assess an algorithm PPC proof, its complexity, and the exact scope of verification evidence.
---

# PPC proof and certification workflow

Use for mathematical proof development, proof review, verification tooling, or Lean artifacts. Read `references/ppc2_spec.md` for the general certificate and `references/ppc3_spec.md` for the restricted soundness-oriented checkers. These are separate from problem generation.

## Required depth for reference PPCs

The learner's six-example ARDS PPC Collection is the **primary style reference**.
Follow `references/ppc_authoring_style.md`: concise, mathematically precise,
self-contained P1/P2/C with a short justified complexity analysis. Keep K as
a separate stored field for compatibility. Use the **proof method appropriate
to the task**—an invariant for a stateful scan, greedy minimality for a greedy
construction, necessity/sufficiency/uniqueness for algebra, or exhaustive cases
for bitwise logic. Do not require an invariant where it makes no sense, or
prove optimality when the task is not optimizing. Include full reasoning, not
four unsupported sentences; avoid excessive generic proof boilerplate.
Use Markdown mathematics safely and never call unverified prose a theorem.

## Proof obligations

- **P1 — Problem:** Specify input domain, preconditions, output/codomain, and required relation or objective, with quantified conditions.
- **P2 — Procedure:** Define an executable or unambiguous algorithm, initialization, transitions, termination conditions, and outputs.
- **C — Correctness:** Establish termination and correctness, including feasibility, completeness, or optimality when required. Use an invariant, induction, construction, contradiction, necessity/sufficiency, or another suitable justified argument; invariants are not mandatory for algebraic or direct proofs.
- **K — Complexity:** Specify input measure and cost model, then derive time and auxiliary-space bounds from actual operations. Distinguish worst/average case and input/output storage where relevant.

Seek concrete counterexamples and unresolved assumptions. Don't manufacture a proof from a plausible implementation.

## Evidence labels must remain narrow

- `scripts/ppc2.py`: structural/dependency/model-binding checks, **not proof of semantic correctness**.
- ARDS bounded oracle tests: empirical coverage under a particular reference model, **not a theorem**.
- `scripts/ppc3.py`: restricted intuitionistic propositional proof terms or exhaustive, explicitly finite transition systems. It does **not** certify arbitrary algorithms.
- `scripts/ppc3_lean.py`: only the specific Lean statement, assumptions, source bytes, and replay/kernel-check scope actually verified. A checked auxiliary lemma does not establish whole-program correctness.

Use `references/hardening.md` for audited checkers, limits, trust assumptions, and isolation. Report exact tool invocation and observed results; if Lean, Lake, or an external kernel is unavailable, state the limitation instead of claiming success.

Do not modify learner attempts, RACG draws, or historical certificates merely to satisfy a checker.
