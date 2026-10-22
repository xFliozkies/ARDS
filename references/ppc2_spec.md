# PPC 2.0 — Problem, Procedure, Correctness
Status: formal-methods specification v2.0 (human-reviewable; machine-readable *structural* checker)
Scope: finite-input algorithms and explicitly stated computational models.
PPC is independent of ARDS; ARDS may attach PPC certificates to problem packages.

## 0. What PPC is, and what it is NOT
PPC is a contract language and a proof-obligation protocol grounded in standard program logic.
A filled-out certificate is **not** automatically a theorem: the current ppc2.py checker checks completeness, dependency integrity, model binding and finite model-specific tests, not validity of arbitrary natural-language inference. No result is called "machine-proved" without a trustworthy external proof-checker artifact.

## 1. Formal core

A *problem* is a tuple `P=(X,Y,D,Q,K)`.
- X and Y: input and output types, including encodings (e.g., strings, finite arrays).
- D subset X: admissible inputs (precondition).
- Q subset D x Y: required output relation; for optimization Q includes admissibility AND the universal comparison to all feasible candidates.
- K: computational cost model (e.g. unit-cost RAM, with word widths and memory accounting).

An *algorithm* is a (potentially nondeterministic) transition system
`A=(Sigma, Init, step, Halt, Out)` with initial states `Init(x)`,
a transition relation `step(s,s')`, terminal predicate Halt(s), and an output map Out(s).

TOTAL correctness requires:
For all x in D, for every valid initial state and every maximal execution,
the execution is finite, ends in a terminal state s, and Q(x, Out(s)) holds.
For a deterministic program this reduces to:
`forall x in D: Terminates(A,x) AND Q(x,A(x))`.
Partial correctness requires Q only for *terminating* executions.

If an input is outside D, PPC makes no claim unless separately specified.
If Q is nondeterministic or has multiple solutions, PPC does not demand a unique output.
For infeasible inputs, Q must explicitly define a permitted error/sentinel output.
Input parsing, integer overflow, indexing and resource limits are proof obligations whenever relevant.

## 2. PPC pipeline
### P1 — Specification
Declare type/representation, valid domain, exact output relation, all quantifiers, mathematical units and cost model. Classify objective as function, decision, enumeration, counting, construction or optimization. Record edge cases. Hidden witnesses MUST be quantified explicitly (exists/forall).

### P2 — Procedure
Declare state, initialization, transition or recursion, termination condition, returned value, tie behavior, and dependencies. Pseudocode is admissible if operationally unambiguous. If the claim concerns implementation, explain numerical types, parsing, memory allocation and exceptional behavior.

### C — Correctness + complexity
Supply checkable numbered claims with assumptions and supporting lemmas. Discharge the REQUIRED obligations for the chosen proof technique. No inference from limited testing to universal correctness is accepted.

Common obligations:
- specification_total: inputs, output relation and assumptions defined, including infeasible instances.
- algorithm_defined: initialization and transitions are well-defined over reachable states.
- termination: establish finite execution; for loops/recursion give a well-founded variant/ranking function or another complete termination argument.
- partial_correctness: show Q for every terminating run.
- complexity: define input size and cost model; account for all loops, preprocessing and extra memory.
- optimality: REQUIRED if Q specifies an optimum; prove feasibility and global dominance, not merely local plausibility.
- existential_witness: REQUIRED where Q uses an existential statement; either construct a witness or prove existence, and address the negative case.

Proof-technique-specific obligations:
- case_analysis: coverage, correctness_each_case.
- loop_invariant: initialization, preservation, exit_implies_post; ranking argument for termination.
- induction: base_case, inductive_step.
- exchange_argument: feasibility, exchange_step, global_optimality.
- graph_reachability: encoding_equivalence, exploration_complete.
- combinatorial_bound: lower_bound, upper_bound_achievable.
- prefix_aggregation: prefix_invariant, query_identity.
- search_exhaustion: search_complete, witness_or_counterexample.

Proof obligations may be addressed by other sound methods if an explicit reviewed extension is recorded.
Every natural-language lemma must state its scope and assumptions. Circular dependencies are invalid.
Adding a "proof" paragraph without the corresponding derivation does NOT discharge an obligation.

## 3. Inference discipline
Permitted foundations: classical first-order logic with equality; integer, real, set and finite combinatorial semantics as stated; sound algebra; definitions; explicitly proven lemmas; well-founded induction; invariants; Hoare-style composition.
PPC does not introduce unproved axioms. Any additional axiom must be identified and independently justified. Universal claims require proof; existence requires a witness or logically valid existence argument.
For an iterative proof, `I(s0)`; `I(s) and Guard(s) and step(s,s') => I(s')`; `I(s) and not Guard(s) => Q(x,Out(s))`. For total correctness prove a rank into a well-founded order strictly decreases on every relevant transition.

## 4. Confidence and status (do not conflate)
- drafted: assertions assembled, may be false.
- structure_checked: metadata, obligation keys and dependency graph valid; reasoning NOT validated.
- bounded_tested: finite oracle or property tests passed, with stated domain; NOT a universal proof.
- human_reviewed: identified reviewer checked mathematical argument, with scope and open assumptions; still not machine-checked.
- machine_checked: independent trusted verifier confirms a formal proof artifact (NOT supported by this first release).
Multiple statuses/evidence can coexist; they are not ordered as if testing implies proof.

## 5. PPC 2.0 machine-readable certificate
One JSON object under `ppc` bound to the SHA-256 canonical digest of the ARDS problem model. Required:
- `version`: `"2.0"`
- `model_hash`: hex SHA-256 of canonical model
- `problem`: domain, codomain, postcondition, objective_kind
- `algorithm`: state, initialization, transition, halt, output, cost_model
- `technique`: a registered proof style
- `obligations`: list of {id, claim, argument, depends_on}. IDs unique; dependencies known and acyclic. All required IDs must appear.
- `complexity`: input_measure, time_bound, space_bound, derivation
- `asserted_status`: `drafted` or `structure_checked` ONLY. Machine never elevates a natural-language proof above structural verification.

The linter rejects missing obligations, cyclic lemmas, invalid or misleading status, empty arguments and certificate/model mismatch. It CANNOT assess logical truth from arbitrary prose.

## 6. ARDS integration and stress protocol
- Generate deterministic fixture *problems* in a dedicated validation corpus, not the live RACG challenge ledger.
- Every new fixture carries its model, PPC certificate, registered-reference binding, statement and test samples. The binding identifies the tested first-party reference; it is not a mathematical proof of authored prose.
- Validate PPC structure AND call the independent ARDS family reference-oracle checker.
- Record failures, family coverage, random seed, hashes and negative controls.
- A 100-problem corpus is a robustness test, not 100 mechanically established proofs or coverage of the 100 RACG topics.
- In case of failure, minimize the counterexample; fix the mathematical model, validator or required obligations; rerun regression tests.
- Preserve original production challenges and their statuses. Synthetic stress fixtures stay in the validation archive.

## 7. Design rationale and external references
PPC builds on ordinary total-correctness program logic, not a new theorem:
- Hoare-style pre/post reasoning and loop invariants.
- Well-founded variants for termination (e.g. Dafny documentation, https://dafny.org/latest/DafnyRef/DafnyRef.html).
- Correctness proofs for greedy choices, finite combinatorial arguments, and graph reachability.
The only claim of originality is the PPC contract format, organization and application workflow, not the underlying logic.

## 8. Known limitations
The structural checker and bounded tests do not prove consistency or soundness of a general-purpose deductive calculus. Proof-soundness depends on external mathematics and future independent reviewers or formal proof assistants. Complexity annotations are checked for presence, not asymptotic truth. Generated story/statement alignment to formal models requires review. The first corpus samples seven explicitly supported families rather than 100 topic types.

## 9. Audit hardening

All new package/certificate/sample JSON loading is bounded and rejects duplicate object members, NaN and Infinity; integer range-sum answers require exact integer types. Malformed techniques/dependencies return a structural rejection instead of leaking type/recursion exceptions. Obligation dependency checking is iterative. See `hardening.md` for limits, the new reference release gate, exact evidence subjects, and benchmark source manifests. Old reports are immutable and are not retroactively relabeled.
