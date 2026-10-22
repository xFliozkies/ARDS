# PPC 3.0 — Soundness-oriented, proof-carrying algorithm framework

**Version:** 3.0.0, experimental verification protocol  
**Canonical phases:** P1 Problem Specification → P2 Proposed Algorithm → C Correctness Proof  
**Independence:** PPC can certify claims independently of ARDS. ARDS only supplies tasks and metadata.  
**Trust warning:** The Python proof checker below is *not itself formally verified*. Its rule set has a mathematical soundness argument, and its interpreter is independently tested. The abstract derivation-soundness theorem is now encoded in `PPC3RuleSoundness.lean` and checked by the isolated Lean bridge. There is still no refinement proof between that datatype and Python's parser/interpreter. Distinguish Python fragment checking, Lean theorem checking, and concrete implementation verification.

## 1. Goal and non-goal

PPC certification must never follow merely from fluent explanation, filled-in proof sections, randomized testing, or a favorable AI grade. A proof must be an explicit derivation in a formally specified sound calculus or an exhaustively validated *finite* transition system with its entire domain encoded.

We do not claim completeness for arbitrary mathematical facts or automatic termination verification for unrestricted programs. Undecidability prevents a decision procedure for arbitrary algorithm correctness. PPC 3.0 supports two **precisely delimited formal fragments** and an isolated Lean bridge for pinned example declarations. Unrestricted implementation correctness remains outside these fragments.

## 2. Semantic foundation of PPC as a whole

A problem is `(X,Y,D,Q,K)`: type of inputs X; outputs Y; admissible domain D ⊆ X; required relation Q ⊆ D × Y; computational cost model K.

An algorithm is a transition system `(Σ, Init, →, Halt, Out)`. **Total correctness** means that every maximal execution from each admissible input and each allowed initial state is finite, ends halted, and satisfies Q with the terminal output. For nondeterminism it is not sufficient that *some* branch terminates.

For unbounded implementation correctness, the relation between a reference mathematical model and the actual executed implementation must itself be proved or checked. A theorem about a mathematical `cakeCost` function is not, without an additional refinement proof, a theorem about an independently implemented Java method.

## 3. Fragment A: intuitionistic propositional natural deduction

Formal grammar after normalizing `not P` to `P → false` and `P ↔ Q` to `(P→Q) ∧ (Q→P)`:
```
Formula ::= var(name) | top | bot | and(Formula,Formula)
          | or(Formula,Formula) | imp(Formula,Formula)
```

Assumptions Γ map unique names to formulas; derivability `Γ ⊢ P` is witnessed by a recursively typed proof term. Only these rules are implemented:

| Rule | Conclusion | Condition |
|---|---|---|
| hyp | P | named hypothesis P ∈ Γ |
| top_intro | ⊤ | unconditional |
| and_intro | P∧Q | both P and Q independently derived |
| and_left/right | P or Q | derive P∧Q first |
| or_left/right | P∨Q | derive the selected disjunct |
| imp_intro | P→Q | derive Q under *fresh* local assumption P |
| imp_elim | Q | derive P→Q and P |
| or_elim | R | from P∨Q, derive same R under P and under Q |
| bot_elim | R | derive ⊥ first |

There is no axiom rule, `sorry`, arbitrary theorem import, or unchecked semantic assertion. The checker verifies exact formula identity, freshness, scoping, and recursive proof structure. No evaluation of submitted source code is performed.

### Soundness theorem (mathematical argument)

Let v be a Boolean valuation, and `v ⊨ Γ` mean every assumption evaluates to true under v. For each derivation accepted by the syntax-directed kernel, prove by induction on its construction that `v ⊨ Γ ⇒ v ⊨ P`.

- `hyp`: immediate by the meaning of `v ⊨ Γ`.
- `top_intro`: true for any valuation.
- `and_intro`: induction hypotheses give truth of both conjuncts; `and_left/right` projects a true conjunct.
- `or_left/right`: a true disjunct makes the disjunction true.
- `imp_intro`: under any valuation making Γ true, if P is false then P→Q is true; if P true then the induction hypothesis for Γ,P makes Q true. Therefore P→Q is true.
- `imp_elim`: truth of P→Q and P entails Q.
- `or_elim`: if P∨Q true, at least one disjunct holds; its branch's induction hypothesis yields the common conclusion R.
- `bot_elim`: no valuation satisfying Γ can make an already derived false formula true, so any conclusion follows vacuously under the premise.

Every rule preserves semantic entailment; hence any *mathematically correctly implemented* proof checker accepting a term establishes Γ ⊨ P. The matching abstract rule schemas now have an axiom-free Lean soundness theorem over proposition interpretations in `PPC3RuleSoundness.lean`. This does not certify the Python implementation or its name-map/list-context correspondence. For formulas involving at most 12 distinct atoms and within the secondary semantic work budget, PPC separately enumerates the truth table and rejects any contradiction of the acceptance claim. If the optional audit exceeds its work estimate, it is explicitly skipped; acceptance still requires a fully typed derivation. Normalized formulas are treated as DAGs in equality, atom collection and evaluation, without exponential unfolding of nested iff.

**Scope:** proposition-level entailment only. A proof of `P∧Q → Q∧P` does not prove that a graph traversal is correct.

## 4. Fragment B: exhaustive total correctness of explicitly finite transition systems

A certificate declares a nonempty, exactly enumerated list of input IDs and one transition graph per input. All initial states, terminal states, edges, permitted outputs and outputs are explicit.

The checker requires:
1. Every declared input has exactly one case; no extra case exists. This defines the *entire* claimed input domain. There is no assertion about any larger domain.
2. Initial states exist and are nonempty; every transition target is declared.
3. No reachable nonterminal state is a deadlock; terminal states have no successors.
4. The reachable transition graph has **no directed cycle** (all nondeterministic paths must terminate).
5. Every reachable terminal state's output is in that input's allowed-output set (the encoded postcondition).

### Soundness theorem (mathematical argument)

For any declared input x and initial state s, all transitions stay in its finite state graph. The reachable graph contains no cycle, so no infinite path is possible: an infinite path through a finite set would repeat some vertex, creating a directed cycle. Every maximal path must therefore be finite. Since no reachable nonterminal state is without a successor, every maximal path ends in a terminal state. By the output check, every such state's output satisfies the encoded required relation Q. Thus total correctness holds for the **explicit domain and graph semantics**.

This is a mathematical proof for the finite model, not a proof that some unmodeled real-world program has identical transitions or that a larger input domain is covered.

## 5. Certification statuses

- `drafted`: informal assertion, no independent proof evidence.
- `structure_checked`: PPC 2.0 fields are complete, not mathematically checked.
- `test_verified`: registered first-party reference functions and provided samples passed bounded comparisons; authored prose, story/model correspondence and implementation refinement remain separate unproved obligations.
- `fragment_machine_checked`: PPC 3.0 natural-deduction kernel accepted a proposition proof (specific conclusion and assumptions).
- `finite_domain_machine_checked`: PPC 3.0 fully checked a declared finite transition system (exact declared domain).
- `lean_kernel_checked`: RESERVED. Only assign after an actual trusted Lean invocation, inspecting the axiom dependency report, independently confirming the theorem's intended statement and recording the toolchain plus proof hashes. The bridge emits `lean_example_checked` with a true `lean_kernel_checked` flag only for its pinned, explicitly inspected declarations; it never upgrades an ARDS release to that status.
- `resource_limit`: no certification issued because an input, normalized-work, or process resource budget was exceeded; this is distinct from an invalid derivation or counterexample.
- `implementation_verified`: RESERVED until proof/refinement relates semantics of actual program to its formal model. No current PPC module returns it.

Statuses are **not an ordered ladder**: a Lean proof of a logical tautology does not imply an implementation is correct. Every record includes the exact theorem/model fingerprint and proof scope.

## 6. Lean integration contract

The shipped `references/PPC3Examples.lean` uses only `Init` and defines a piecewise cost function and a mathematical specification. It includes three example theorems and `#print axioms` commands. The three specific example theorem declarations have now successfully compiled with Lean 4.35.0 and replay-checked with bundled `leanchecker`. The pricing theorem uses the standard logical axiom `propext`, while the other two are axiom-free. This verification does not extend to arbitrary student algorithms. Re-run `python3 scripts/ppc3_lean.py` for the current, file-hash-bound result.

For current reproducible evidence, use the isolated bridge (Lean 4.35.0 and bubblewrap required):
```sh
python3 scripts/ppc3_lean.py
python3 scripts/ppc3_lean.py --fresh
```

The second command requests a separate, bounded full-import replay. Both compile independent type ascriptions in `PPC3Expected.lean`, use approved source hashes from `ppc3_lean_manifest.json`, audit the named axiom sets, and retain unique evidence directories. A pin change is a review action, not an automatic approval. The bridge also checks the abstract soundness theorem/helper. It sets 64 MiB stacks, two workers and a 4 GiB address-space cap inside an offline sandbox; no fallback disables isolation.

Inspect `#print axioms` output for `sorryAx`, custom axioms, native compiler trust, or anything beyond standard Lean logical axioms. Bundled `leanchecker` uses Lean's own kernel; independent external checking requires a separate successful sandboxed `lake check --paranoid` run with its actual checker outcomes recorded. Do not run arbitrary untrusted Lean scripts on a privileged host: Lean metaprogramming can execute code. Use an isolated, resource-limited environment for untrusted submissions.

Formal correctness of the *framework* is conditional on the underlying proof checker semantics, its implementation, standard logical foundations, and correct alignment of theorem statements to intended real-world algorithms. It is not a claim of an absolutely infallible tool.

## 7. PPC 3.0 to ARDS 2.0

ARDS may attach optional `ppc3` evidence to a challenge package, but must not relabel its `test_verified` release as `lean_kernel_checked`. `auxiliary_propositional_lemma` and `auxiliary_finite_model` are explicitly auxiliary. `explicit_finite_model` requires a checked specification adapter; currently only pricing is supported, with exact full input-domain and postcondition matching. This establishes a relation for that finite graph, not refinement of separately implemented code. Unsupported adapters are rejected instead of implying correspondence from a hash. Existing PPC 2.0 and ARDS records remain unchanged.

The PPC 3.0 proof certificates and finite model representations are independent artifacts. Their checker CLI is:
```sh
python3 scripts/ppc3.py proposition --file proposition.json
python3 scripts/ppc3.py finite-machine --file finite-model.json
python3 scripts/ppc3.py lean-status
```

PPC 2.0's earlier 100-case archive remains a seven-family **parametric bounded test**, not a theorem test over all RACG topics. PPC 3.0 separately tests 100 generated propositional proof terms and 100 finite models plus malicious/incorrect mutations. A high pass count is evidence about the checker implementation, not an argument that every arbitrary algorithm is now decidable.

## 8. Required further work before universal claims

- Keep independently reproducing pinned Lean checks and axiom reports in isolation. The local toolchain and the five specific named declarations have been checked; this is not a framework-wide proof.
- Convert representative family-specific mathematical algorithms into typed Lean definitions and prove their genuine functional correctness (not only abstract propositional tautologies).
- Prove correspondence between the already formalized abstract derivation system and the Python checker, or replace the trusted interpreter with kernel-checked proof export. The abstract metatheorem alone does not discharge this obligation.
- Prove refinement between the mathematical model and concrete Java implementations, including integer overflow, resource model and input parsing where applicable.
- Expand beyond the seven built-in ARDS families and independently audit statement-to-model correspondence, negative cases and actual proof validity.

## 9. Strict input and resource contract

See `hardening.md`. Duplicate JSON object members, non-finite numbers and non-JSON Python values are rejected before checking. Canonical encoding of valid legacy JSON is preserved. Finite input/output IDs use canonical serialization identity, not implicit Python bool/int/float coercion or arbitrary real arithmetic. Finite traversal is iterative and handles chains up to the declared state cap. Bounded loaders hash the exact bytes parsed; normalized comparison/semantic-audit budgets and resource-limit results prevent unchecked work from being reported as a counterexample. New benchmark reports include source/version provenance in a fresh namespace; historical reports are preserved.
