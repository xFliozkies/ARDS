# PPC method: Problem specification → Proposed algorithm → Correctness proof

**PPC 2.0 authoritative specification:** See [ppc2_spec.md](ppc2_spec.md) for the formal semantics, correctness and termination obligations, inference discipline, proof-technique requirements, typed certificates, confidence labels, and dual stress-test contract. This page remains a short pedagogical introduction, not a substitute for the PPC 2.0 specification. Machine-readable PPC certificates are structurally checked by `python3 scripts/ppc2.py check --file PACKAGE.json`. The checker does not prove natural-language arguments.

## P1: Problem specification
Define input, bounds, required output, allowed operations, optimization objective, and feasibility requirements. Formalize what a valid answer must satisfy.

## P2: Proposed algorithm
Explain initialization, maintained state, transitions, data structures if useful, termination, and returned answer. A conceptual explanation or pseudocode suffices.

## C: Correctness proof
Prove the algorithm achieves P1. Useful proof tools: induction, loop invariant, exchange argument, greedy stay-ahead, contradiction, case analysis, graph invariants. Include feasibility and optimality proofs as appropriate; complexity belongs after correctness.

Optional CLEAR mnemonic:
- Claim
- Logical invariant
- Establish and preserve the invariant
- Argument for optimality (if applicable)
- Result at termination

CLEAR is a tutoring mnemonic, not an established theorem. Closed-form modeling questions do not always need invariants.

**Non-decreasing sequence example:** For each i, choose B[i]=max(A[i], B[i-1]) (and B[1]=A[1]); accumulate B[i]-A[i]. Inductively, every feasible solution C has C[i]>=B[i], thus the chosen solution minimizes increments. O(N) time and O(1) auxiliary space.
