# ARDS reference PPC writing style

**Primary source:** the learner's *ARDS — PPC Collection*, six worked examples
(Non-Decreasing Sequence, Broken Telephone, Average Number, Append for OR,
Student Government Election, Smallest Missing Positive Integer) and its
General PPC Writing Template.

**Audience:** the AI author, independent reviewer, and reference-PPC renderer.
A PPC is teacher-only until explicit learner reveal. Do not place P2/C/K in
student statements or previews.

## Style and structure

Use exactly four storage fields—`teacher_ppc.problem`, `procedure`,
`correctness`, `complexity`—for API/database compatibility. Present them
as **P1 — Problem Specification**, **P2 — Proposed Algorithm**,
**C — Correctness Proof**, and **Complexity**. The last field is kept separate
in storage even though the collection puts Complexity at the end of C.

Write like a mathematical solution, not a generic machine-verification report:
precise, compact, self-contained, **problem-specific**, with equations where
they sharpen the claim. Avoid a universal boilerplate or a mandatory fixed
word count. Explain enough reasoning to establish the claim, not just that
the author believes it.

### P1 — Problem Specification

- Introduce the complete admissible input domain (types, bounds, indexing,
  dependencies between variables), and mathematically characterize the
  required output (type, length/range, ordering, and exact relation to input).
  Quantified equations are useful; do not substitute an unexplained array
  slice or ambiguous symbolic shorthand for the actual contract.
- Specify **all and only** applicable feasibility conditions and optimization
  goals, with a precise objective/predicate for deciding correctness.
  For a deterministic output task, an explicit output relation is sufficient:
  do not invent an optimization problem.
- Resolve no-solution, empty-output, tie, and boundary conventions where
  applicable; separate the mathematical output from its stdin/stdout encoding.
- P1 must be independently usable to check a candidate output, *without*
  assuming P2. A one-line answer restatement is not enough if it omits
  admissibility, validity, and relevant boundary conditions.

### P2 — Proposed Algorithm

- Describe the state, initialization, processing steps, updates, and output.
  Use conceptual prose plus equations (such as an assignment or recurrence).
- Use pseudocode only when it improves precision. A list of code statements
  is not inherently a better PPC than a concise conceptual algorithm.
- Make steps implementable, with necessary types/overflow caveats where they
  materially affect correctness.

### C — Correctness Proof

- **State a theorem quantified over all admissible P1 inputs** and identify
  which P2 procedure is being proved. The assertion must cover the *entire*
  P1 output relation, including feasibility and optimality when relevant.
- Select the **appropriate proof method**:
  - greedy optimality / componentwise minimality: Non-Decreasing Sequence;
  - a prefix/counting invariant: Broken Telephone, Student Government,
    Smallest Missing Positive Integer;
  - necessity, sufficiency, uniqueness: Average Number;
  - forbidden-bit impossibility, constructive feasibility and minimality:
    Append for OR.
- Establish each nontrivial implication with reasoning, not an assertion
  that the procedure is "obvious" or "correct by definition". Show why the
  method actually implements the required P1 relation. For an invariant proof,
  state its precise meaning, initialization, maintenance, and its consequence
  when the algorithm finishes.
- For direct algebra or exhaustive cases, **do not force a loop invariant**.
  Prove optimality or uniqueness only when P1 requires them, and justify
  necessary and sufficient conditions in both directions when appropriate.
- Establish termination (finite bounds/decreasing measure or other valid
  reason), and explicitly account for applicable empty, minimum, impossible,
  and tie cases. Do not assert universality based on a finite test suite.
- Perform a **P1-to-C coverage check**: for every distinct P1 obligation,
  identify the step of C that establishes it. If an obligation is missing,
  revise the proof instead of treating the omission as acceptable for an easy
  level.

### Complexity (K storage field)

- State **time** and **auxiliary space** separately. Identify the input size
  and explain the cost briefly: e.g. one array scan yields `O(N)` time and a
  fixed number of counters gives `O(1)` auxiliary space.
- State an assumed cost model only if it affects the claim; explain integer
  widths or big-number costs when relevant. No need for a lengthy generic
  summation for a straightforward linear scan.

## Reference PPC presentation and mathematical typesetting (mandatory)

PPC reference sections are **Markdown with KaTeX math**, not unstructured
plain-text answer keys. The website safely renders Markdown headings,
paragraphs, emphasis, lists, and mathematical expressions. Author and review
the same Markdown/TeX that the learner will see **after an explicit reveal**.

- Delimit **every mathematical expression that needs typesetting** with
  `\(...\)` for inline math and `\[...\]` for prominent, centered display
  equations. Use raw LaTeX commands inside the delimiters: `\leq`,
  `\forall`, `\in`, `\sum`, `\mathbb{Z}`, `\frac{...}{...}`.
  Do **not** write long ASCII formula strings such as
  `a^2+b^2>0`, `K<=N<=1200`, or `T(x,y)=(...)` as prose.
- Use a **separate block equation** when defining the input domain, required
  output relation, central invariant, critical inequality, recurrence,
  optimization objective, or final theorem. Reserve inline math for short
  expressions used in sentences. Display equations should be legible and
  not run into surrounding prose.
- Write **meaningful Markdown paragraphs and proof steps**. Identify the
  theorem/claim, proof method, critical assumptions and steps, termination,
  and the conclusion. For induction/invariant proofs, use actual
  **Initialization**, **Maintenance**, and **Termination** paragraphs.
  For contradiction, exchange or algebraic proofs, use headings that match
  the argument instead; do not mechanically impose an invariant.
- The student-facing statement's difficulty level does **not** relax the
  rigor or typesetting expected of the private teacher PPC.
- Review the rendered output (or a representative local rendering) before
  release. A raw one-paragraph P1 or C without readable mathematical structure
  is a presentation defect even if the proposition happens to be correct.
  Invalid TeX, unescaped Markdown syntax or silently dropped notation must
  be fixed by a versioned package revision and re-reviewed where required;
  **never** modify the canonical teacher answer merely to make the UI look
  better.

**Example of correct source formatting for an invariant:**

```markdown
**Theorem.** For every valid input \(x\in D\), the algorithm
returns an output satisfying the predicate \(Q(x,y)\).

**Proof.** After processing \(i\) elements, let \(E^{(i)}\) be the
sequence emitted so far. We establish the invariant

\[
E^{(i)}=
\begin{cases}
(), & 0\le i\le K,\\
(A_{K+1},\ldots,A_i), & K<i\le N.
\end{cases}
\]

**Initialization.** At \(i=0\), the sequence is empty.

**Maintenance.** Assume the invariant for \(i\). ...
    
**Termination.** The algorithm processes exactly \(N\) elements,
so the invariant at \(i=N\) proves the required output relation.
```

## Authoring quality bar

Before registering any problem, compare the PPC to the six examples: Does P1
define precisely *what* answer means? Does P2 describe *how* to construct it?
Does C establish *why* the procedure always meets P1, with an appropriate
proof technique? Does the complexity follow from the actual operations?

**Do not over-compress:** four unsupported one-sentence summaries are not an
adequate reference. **Do not over-expand:** unrelated lemmas, mandatory
invariants, generic verification disclaimers repeated in every section, and
excessively long pseudocode obscure the reasoning. Keep assurance/evidence
labels separate from the actual mathematical argument.

The student-facing statement remains independent of this PPC and consists of
the necessary task definition, Input Format, Output Format, Constraints, and
sample Input/Output only. No Explanation or Note blocks.

## Required worked example: Ticket Window (Level 1)

This is the minimum **semantic completeness** standard, not a mandatory prose
template, not a required proof technique, and not a minimum length. Lower
problem difficulty never permits a weaker P1 or a missing proof obligation.

**P1 — Problem Specification.** Let
\(D=\{(N,K,A): N\in\mathbb Z,\ 1\le N\le 10^5,\ K\in\mathbb Z,\ 0\le K\le N,\
A=(A_1,\ldots,A_N),\ A_i\in\mathbb Z,\ 1\le A_i\le 10^9\}\).
For every input in \(D\), the required mathematical output is the unique
sequence \(B\) of length \(N-K\) satisfying
\(\forall j\in\{1,\ldots,N-K\},\ B_j=A_{K+j}\).
Thus \(K=0\) yields \(B=A\), whereas \(K=N\) yields the empty sequence.
Its textual encoding is the ordered elements separated by single spaces,
or the literal token `EMPTY` if the sequence is empty. No optimization is
involved.

**P2 — Proposed Algorithm.** Read \(N,K\) and then scan the \(N\) ticket
numbers in original order. For each one-based input position \(i\),
emit \(A_i\) if and only if \(i>K\), retaining output order.
If no number is emitted, print `EMPTY`.

**C — Correctness Proof.** For all \((N,K,A)\in D\), the algorithm
terminates and returns precisely the sequence specified in P1.
After processing \(i\) ticket numbers, define \(E^{(i)}\) as the sequence
of numbers emitted so far. The invariant is
\(E^{(i)}=()\) for \(0\le i\le K\), and
\(E^{(i)}=(A_{K+1},\ldots,A_i)\) for \(K<i\le N\).
Initially \(i=0\), and nothing has been emitted, so it holds.
Suppose it holds after \(i<N\) items. If \(i+1\le K\), the next
number is skipped and the emitted sequence remains empty; otherwise,
the algorithm appends precisely \(A_{i+1}\), extending the stated
suffix in order. Thus the invariant holds after \(i+1\).
The scan runs exactly \(N\) iterations, and \(N\) is finite, so it
terminates. Substituting \(i=N\) into the invariant shows that the emitted
sequence has length \(N-K\), contains exactly \(A_{K+j}\) in each position
\(j\), and preserves order. For \(K=N\), nothing was emitted and the
explicit empty-output branch prints `EMPTY`; for \(K=0\), all input
numbers are emitted. Therefore the entire P1 contract is satisfied.

**K — Complexity.** Scanning the input costs \(O(N)\) time, and a
streaming scan keeps \(O(1)\) auxiliary state when excluding output
buffering; storing the output in memory instead takes \(O(N)\) space.

**Review trace.** P1's admissible domain supports the finite scan; its
elementwise output relation follows from the inductive invariant; its ordering
and empty-output conventions follow from the same invariant and explicit
branch; termination follows from the bounded scan. All conditions are
independently justified, not merely repeated as a claim.

A reference that only says "return A[K+1..N]" for P1, or "the scan is
correct" for C, does not meet this worked standard unless the omitted
domain, relations and proof obligations are supplied elsewhere in those
sections. Reject such shorthand during authoring/review instead of
padding it with generic prose.
