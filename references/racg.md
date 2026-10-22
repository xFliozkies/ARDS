# RACG v1.2 — weighted Classic difficulty protocol

Classic RACG retains 100 topic IDs, six difficulty levels, a 15% continuation
branch, and a separate 70% story presentation branch. Its difficulty draw
**is now weighted**; there is no mastery gate or difficulty reroll.

## Exact selection rules

Use independent cryptographic randomness (`secrets.randbelow`) for each roll:

1. Draw `O` uniformly in `[1,100]`. Continuation occurs when `O <= 15`
   **and** a previous eligible challenge exists.
2. For a continuation, reuse the previous topic ID and its actual label, do
   **not** draw `X`, and set the minimum eligible difficulty to the previous
   difficulty. For a fresh topic (including the very first draw), draw
   `X` uniformly in `[0,100000)`; topic ID is `1 + X % 100`. Its
   minimum difficulty is Level 1.
3. Draw one independent `Y` uniformly from **1 through the sum of the
   weights of eligible levels** (inclusive). Select the level by the first
   cumulative eligible weight that contains `Y`. Do not clamp or reroll.
4. Draw `P` independently and uniformly in `[1,100]` **for every
   problem**. Values 1–70 mean story presentation and 71–100 direct.
5. Persist true `O/X/Y/P` rolls, selected topic/level/presentation and
   continuation branch. No arbitrary adjustment for verification convenience.

| Level | Fresh weight | Fresh probability | Fresh Y interval |
|---|---:|---:|---|
| 1 | 30 | 30% | 1–30 |
| 2 | 25 | 25% | 31–55 |
| 3 | 20 | 20% | 56–75 |
| 4 | 12 | 12% | 76–87 |
| 5 | 8 | 8% | 88–95 |
| 6 | 5 | 5% | 96–100 |

For continuations, **renormalize over the eligible tail**. Example: previous
difficulty 4 permits weights (12,8,5) with sum 25: draw `Y` uniformly from
1–25, yielding Level 4 for 1–12, Level 5 for 13–20, Level 6 for 21–25.
Conditional probabilities are therefore exactly 48%, 32% and 20%. Continuing
Level 5 uses 8:5, continuing Level 6 always returns Level 6. No clamping.

`Y` is one-based and its valid range depends on the continuation's minimum
difficulty. This is intentional and unbiased: each weight unit is sampled
uniformly with no rounding, rejection or modulo bias. The overall long-run
difficulty distribution can differ from fresh weights due to continuation.
The 15% continuation branch does not prohibit incidental repeats of a fresh
topic, and a first problem is always fresh even if `O<=15`.

## Difficulty interpretation

1. Basic definitions and direct constraints.
2. Standard single-concept reasoning.
3. Intermediate insight or non-obvious transformation.
4. Advanced single-concept or multi-step reasoning.
5. Difficult combinations and intricate proofs.
6. Expert or highly non-obvious reasoning.

The detailed, level-specific comprehension and authoring obligations are in
`references/specification_comprehension.md`. Every level still requires
precise semantics and rigorous teacher PPC proof; difficulty isn't inflated
by missing definitions. Difficulty remains relative to topic. Assessments
should compare matched distributions rather than uncontrolled random mixes.

## Provenance and historical compatibility

Old challenges and imported legacy records may contain `Y` values from
the **pre-v1.2** protocol (`Y` in `[0,6000)`, difficulty
`1+Y%6`, clamped on continuation). Do not recalculate or overwrite old
recorded difficulties using the new formula. The current generator and batch
validators use v1.2 for **new** draws. The legacy "Missing Elements"
problem once used topic ID 86, now catalogued as "Convex hulls": a
continuation retains its previous actual label.
