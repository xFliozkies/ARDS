# Independent AI-assisted problem review and incremental release

Every generated Classic RACG problem starts as a **private, unassessed draft**.
The student problem library shows only released problems. The review queue is
managed through commands, not a public API route. Do not use a one-click
"approve" or the authoring AI's own sample-checking claim as release evidence.

## Roles and trust

- **Author**: creates the statement, input/constraints/output contract, private
  P1/P2/C/K, reference procedure and supporting sample evidence.
- **Independent AI reviewer**: first audits the actual learner-facing statement under BOTH `references/contest_problem_design.md` (CodeChef examples, RACG-0040 explicit ACCEPT/REJECT, original reasoning and rules-before-input-code) AND `references/specification_comprehension.md` (six level-specific policies): Level 1–3 comprehension must not assume prior knowledge of the tested topic, while Levels 4–6 may require specialist abstraction; all levels must define the problem unambiguously. The reviewer specifically checks symbols, terminology, assumptions, input/output separators, constraints, and edge cases. The reviewer then derives a separate candidate algorithm and a
  brute-force/exhaustive (or otherwise independently justified) oracle from the
  statement, writes runnable Python review code, performs a detailed natural-
  language specification, proof and complexity critique, and identifies limits.
- **ARDS review runner**: executes reviewer code in a bounded, isolated Python
  subprocess, checks official samples plus many deterministic adversarial and
  generated inputs, persists hashes of the exact candidate package/reviewer code/
  written report plus reproducible input/output corpus digests.
- **Release gate**: permits publication when a matching, most-recent review
  passed, the reviewed artifacts remain unchanged, and all normal duplicate and
  recorded-difficulty checks succeed. Database-resident batch membership, not author-supplied `batch_id`, determines whether stricter review and plain-text stdin/stdout are required. First-party family checks alone cannot release queued batches. A failing/stale review never publishes.

**Honesty:** Two differently implemented algorithms can share mistakes; even
hundreds of successful tests plus a written proof critique are not a theorem-
kernel certificate. The "tested_and_ai_reviewed" designation means only the
specific recorded scope. It also does not guarantee an independently audited
human expert has reviewed the code. Reviewer-written Python is trusted local
code (CPU/memory/time limits mitigate runaways but **are not a security
sandbox**). Never execute untrusted uploaded source.

## Review a queued problem

Read the solver-visible statement and its private PPC using authorized local
management access. Do not copy the author's proposed procedure into both
candidate and oracle. For a problem to be independently reviewed, write:

- `reviewers/RACG-XXXX.py`, exporting four functions:
  `candidate(data)` (a reviewer-derived solution),
  `oracle(data)` (separately derived, preferably exhaustive on small cases),
  `edge_cases()` (list of at least three valid JSON-decoded inputs), and
  `generate_cases(seed,count)` (at least `count` deterministic diverse valid
  inputs; 180 requested by runner).
- `reviewers/RACG-XXXX.json` with `reviewer_id`, `decision: "approve"`,
  `independently_derived: true`, and at least 80 characters of substantive
  separate critique in each: `specification_analysis`,
  `correctness_analysis`, `complexity_analysis`, `edge_case_analysis`,
  `independence_statement`, `limitations`. The rubric must discuss real
  problem constraints and concrete possible failure modes.

  **Mandatory specification audit:** In addition, the written report must
  contain `specification_review` with the recorded numerical `difficulty`,
  `comprehension_policy` equal to `accessible_without_topic_prerequisites`
  for Levels 1–3 or `abstract_interpretation_permitted` for Levels 4–6,
  and `verdict: "pass"` only if the learner statement satisfies the
  level-sensitive review in `references/specification_comprehension.md`.
  Supply substantive evidence (at least 80 characters each) in
  `symbols_and_objects`, `terminology_and_prerequisites`,
  `io_and_output_validity`, and `ambiguity_and_edge_cases`.

  **Mandatory CodeChef-style design and spoiler audit:** Before assigning
  `specification_review.verdict: "pass"`, independently examine the *actual*
  description (not just the Input Format or private PPC). It must explain
  the objects, initial state, what each operation or relation **means**,
  changes/timing, objective, and necessary exceptions without requiring
  the reader to decode command codes first. For a Level 1 operation/query
  statement compare directly with the original/revised RACG-0040 examples
  in `references/contest_problem_design.md`: the terse input-code-first
  version **fails** even when mathematical parsing and test cases work.
  Review whether the challenge requires an original reasoning insight
  under its stated constraints without leaking the algorithm in the text;
  reject superficial story reskins and new unused command placeholders.
  Discuss *both* comprehension and mathematical reasoning demand in
  `level_specific_evidence` with a verbatim solver-visible quote. Passing
  samples, a correct PPC, or valid JSON fields does not override a failed
  student-statement design review. This semantic audit is required even
  when structural validation cannot detect missing explanations.

  **Six-specific-level review, not two generic buckets:** Use the exact
  `level_profile` from the six worked examples and pass tests in
  `references/specification_comprehension.md`:
  `L1_plain_foundations`, `L2_concrete_relations`,
  `L3_defined_abstraction`, `L4_standard_domain_terms`,
  `L5_layered_formalism`, or `L6_dense_mathematical_model`.
  Include `student_text_quote` (a verbatim phrase of at least 12 characters
  from the public description, input/output format or constraint) and
  `level_specific_evidence` (at least 160 characters) explaining how this
  particular phrasing satisfies the **exact recorded level**. Repeating
  the rubric or writing “clear for Level 2” is insufficient.
  Missing/mismatched audit fields, non-verbatim quotes, or incorrect profile
  IDs block independent approval. These are auditable reviewer claims,
  **not machine proof** that every ambiguity has been discovered.

The reviewer functions use structured Python values internally for independent differential tests, but **public programming inputs must be stdin text, not JSON**. A text-mode review requires `decode_stdin(raw)` and `encode_stdout(value)` in the reviewer module; official text samples are parsed and the exact plain-text outputs checked. The JSON values inside the reviewer harness are internal test data, never student I/O. A released challenge's format change requires a new hash-bound AI review before `ards2.py amend` can add a new published version; the original and solution exposure record remain immutable.

The runner uses internal structured test values and insists candidate, oracle and official
samples agree *exactly* in JSON type/value; input diversification requires at
least 100 distinct cases. It checks ≥180 deterministic generated cases, ≥3
edge cases, and ≥2 official samples, and records a pass/fail result. It does
not fabricate test coverage or silently infer a successful proof from the
author's P2/C prose.

```bash
# What is waiting? (does not change the database)
python3 scripts/ards_review.py status
# The reviewer must FIRST write a genuine separate module and review notes.
python3 scripts/ards_review.py check RACG-XXXX \
  --module reviewers/RACG-XXXX.py \
  --report reviewers/RACG-XXXX.json
# Inspect the status before attempting release.
python3 scripts/ards_batch.py status
python3 scripts/ards2.py inspect RACG-XXXX
# Releases only with matching, successful review evidence.
python3 scripts/ards2.py release RACG-XXXX
```

The release is per problem: other unreviewed problems stay private. The queued item must pass independently recorded checks and real text-I/O validation even if the author omits or changes its optional `batch_id`. First-party verification alone does not change a batch item to `verified`. The runner
does **not** automatically invoke an LLM, create reviewer algorithms for
unknown families, or execute in the background. Each future AI reviewer
session must actually work through those mathematical obligations and submit
runnable evidence. A reviewer must explicitly report counterexamples and
failed checks; an unreviewable family stays in the queue until a suitable
oracle is constructed.

## Evidence integrity and repairs

Each new review also binds the hash of the executable **review runner**. The release gate checks the exact package, reviewer program, written report, runner version, and cross-record evidence agreement. File integrity does not demonstrate that an AI truly reasoned independently.

The active `data/ards.db` contains immutable `independent_reviews` history
and corresponding `verification_runs`. Each record binds an exact
`problem_packages` or latest `authoring_package_revisions` body hash to
the reviewer Python source, detailed written review, test counts, seed, case
set digest and output digest. A different package, stale code, modified report,
failed run, missing tests or mismatched hashes stops release.

If a sample/specification/proof is found incorrect **before** publication,
use `python3 scripts/ards2.py revise-draft ... --reason ...` to append an
immutable correction and rerun the independent review against its new hash.
After publication, use `ards2.py amend` and preserve previous versions.

A reviewed release does not mean that a universal proof was machine-checked.
Explanations and exact test counts must continue to distinguish bounded
execution evidence, AI proof critique, independent human audit (not performed
here), and formal Lean validation (only where actually implemented).

## Worked case: RACG-0001

**Archived historical worked example only; not an active challenge.** The
mirror-prefix reviewer code and written report are preserved as isolated test
fixtures under `tests/fixtures/reviewers/` (and the full original review state
is in the safety archive). This is not a fresh AI approval and should never
be treated as a current challenge. The example contains a linear prefix-function
solution and a separate direct-prefix palindrome oracle. Its review JSON documents
specification, proof, complexity and edge-case analysis. The recorded check
passed 2 official samples, 13 edge cases and 180 generated tests
(195 checked cases in total) and enabled the first release. This does not
prove correctness for every length-2000 string.

## Mandatory teacher PPC proof review (all six levels)

In addition to the public `specification_review`, every independently
approved batch package must contain a **separate** `ppc_review` object in
the private reviewer JSON. Its required fields are:

- `verdict: "pass"` and `all_p1_obligations_covered: true`, only if the
  reviewer has actually traced every material output, feasibility, optimality,
  boundary and termination obligation. Do not check these boxes without
  reading the full P1, P2 and C.
- `input_domain_quote` and `output_relation_quote`: exact substrings of
  `teacher_ppc.problem` containing the domain and the required output
  predicate; a one-line slogan that omits constraints must be rejected.
- `claim_quote`, `reasoning_quote`, `termination_quote`: exact substrings
  of `teacher_ppc.correctness` showing the quantified assertion, a
  substantive argument and an actual termination reason.
- `domain_and_output_analysis`, `method_and_logical_justification`,
  `termination_and_boundaries`, `math_presentation_analysis`, and
  `limitations`: concrete, independently reasoned paragraphs covering the
  problem, proof method, boundaries, and review limits. The new
  `math_presentation_analysis` must specifically inspect **both P1 and C**
  as reader-visible Markdown + KaTeX: delimit formulae with `\(...\)`
  or `\[...\]`, use display math for substantive equations, and
  separate theorem/proof steps into readable paragraphs. If there is no
  meaningful formula, explain why the proof can remain prose-only. Reject
  unformatted ASCII expressions and single dense paragraphs where they
  obscure reasoning; plain-text formatting compatibility is for old
  already-released references, not a substitute for proper authoring.
- `obligation_mapping`: a nonempty list of objects with `p1_quote` (exact
  substring of P1), `c_quote` (exact substring of C), and `justification`
  (specific reasoning why C establishes this P1 obligation). Include one
  mapping for **each distinct material obligation**; do not repeat an
  irrelevant quote to satisfy the gate. If any requirement lacks support,
  reject and request a corrected version.

Review the entire P1 and C, *not merely the quoted excerpts*. In particular,
an optimizer must prove feasibility **and** optimality, a decision procedure
must prove both applicable directions, and a constructive output must prove
every required element/value/order/convention. Require the actual P2
procedure to match the proven algorithm. Any valid proof technique is allowed;
do not demand invariants for algebraic or case-based solutions. Apply the
same proof standard at Levels 1–6.

The review runner mechanically verifies the presence of these fields, that
quotes actually appear in the stored teacher reference, and a concrete
obligation mapping. It cannot establish that reasoning is logically sound or
that *every* obligation was found. This remains an independent AI/human
semantic audit, not a machine-checked proof. A missing or failed audit blocks
new independent approval and consequently the corresponding batch release.
Read the worked Ticket Window example in
`references/ppc_authoring_style.md`.

## Mandatory learner-rules-to-model semantic witness (post-Batch-8 safeguard)

A matching candidate/oracle pair can agree while both solve a different problem from
the student-visible wording. RACG-0265 previously passed differential checks even
though its two-state "OPEN only while closed" rule forced alternation, whereas
its private formula and samples counted unrestricted nonnegative OPEN/CLOSE
balances. **Passing mathematical tests and matching source quotes alone do not
approve semantic equivalence.**

For every newly drafted problem and every published amendment, the reviewer
must complete these checks *before* approving the specification:

1. **Start from the public statement only.** Independently list the initial
   objects/state, legal actions, state transitions, identity or multiplicity
   convention, failure/tie cases, and final output predicate. Do not infer a
   missing rule from the teacher PPC, samples, or candidate algorithm.
2. **Derive every official sample under those literal public rules.**
   For small inputs, enumerate all possible outcomes or exhibit a concrete
   witness and count. If the sample cannot be obtained under the rules, the
   specification must fail, regardless of how candidate and oracle agree.
3. **Translate those rules to P1 and back.** Verify both directions: every
   publicly legal object or sequence is admitted by P1, and every object
   counted/accepted by P1 is publicly legal. State a minimal counterexample
   for any asymmetry; if none is found, record a checked minimal example and
   explain why the mapping preserves actions, constraints and outputs.
4. **Check the actual task against the stored random selection.** Level 1
   must admit a comprehensible elementary implementation under its maximum
   constraints; do not silently assign a sophisticated exponential
   optimization to a beginner tier. The primary randomized topic must be
   mathematically relevant to the required task, not merely present as input
   decoration. Multiple valid methods are encouraged: never reject a problem
   just because a simpler alternative to the selected topic also solves it.
   Instead, assess whether the topic genuinely fits the task and whether
   the constraints remain appropriate for the recorded difficulty.
5. **Use a separate semantic verifier when practical.** It should encode the
   literal legal moves rather than call the candidate's helper functions or
   restate its recurrence. Compare its results with the published samples
   and the proposed private output relation.
6. **Record limitations honestly.** The reviewer must include the concrete
   sample derivation, a nontrivial public↔P1 equivalence witness, and the
   topic/level assessment in the narrative. An AI self-review is not
   independent human verification or formal proof.

These steps are process requirements; the current JSON schema checker verifies
field presence and source quotations **but does not mechanically prove**
public-rule/P1 equivalence. Do not claim that the schema alone enforces this
semantic safeguard.



## Mandatory archive-novelty and alternative-method check (Batch 9 lessons)

Before registering each new randomized challenge, compare its **required
mathematical output relation**, legal operations and allowable input domain
against the existing canonical released archive. A new title, story, label type,
or tighter numeric bound is not sufficient novelty if the task still asks
for exactly the same computation under the same operations. Search likely
neighbors by conceptual objective, then record what materially differs (e.g.,
exactly-once frequency versus number of distinct values, or collective
three-vertex ancestor and travel cost versus pairwise LCA). A reviewer must
explicitly flag substantially identical tasks, rather than approve them based
on superficial wording distance.

The existence of several correct algorithms is **never by itself a defect**.
A valid O(N) degree solution to a rooted-tree leaf problem does not invalidate
a BFS/DFS solution. Evaluate the recorded topic's real applicability and the
problem's constraint/difficulty calibration, not whether every alternate
algorithm has been excluded. For beginner levels, preserve an understandable
feasible strategy; for higher levels, require meaningful reasoning, not
obscurity introduced by ambiguous text.

For an already **published** overlapping challenge, preserve its initial
released statement, verified answer relation, and assessment history.
Substantive changes to the output predicate and samples require a **separate,
reviewed, versioned amendment** clearly describing why the edition differs;
only do so when the learner authorizes refinement and existing attempts can
be preserved without retrospective grading ambiguity. A whole mathematical
family change requires a new challenge, not a silent revision. Student-facing
statements must not advertise algorithm names or construction hints unless
needed to define the task's actual rules.
