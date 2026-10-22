# PPC/ARDS audit hardening

This is the operational contract after the independent audit in `audit/independent-20261020/AUDIT.md`. The original report, benchmark archives and learner records are preserved. Implementation evidence for the repairs is under `audit/remediation-20261020/`.

## What the checks establish

`structure_checked` checks obligation structure, not the truth of arguments. `test_verified` checks the registered first-party reference functions and the provided samples on the reported bounded domains. It does not execute or approve an authored algorithm or arbitrary code. `fragment_machine_checked` and `finite_domain_machine_checked` apply only to the exact sequent or explicit graph. Lean evidence names the precisely checked declarations, sources, expected types and axiom dependencies. None of these statuses proves refinement of the Python checker or a Java implementation.

## New release and amendment workflow

Prepare a new file explicitly before registration:

```sh
python3 scripts/ards2.py prepare-reference --file authored.json --out reference.json
python3 scripts/ards2.py register RACG-XXXX --file reference.json
python3 scripts/ards2.py verify RACG-XXXX
python3 scripts/ards2.py release RACG-XXXX
```

Preparation substitutes the registered family's explanation for `reference_solution` and `proof`; it does not approve the submitted prose. It never edits the input file and refuses to overwrite an existing output. It does not open the learner database. Unsupported families have no registered explanation and remain experimental.

The package's `reference_binding` identifies its exact model, registered explanation and registry definition. Release and amendment require this binding and exact registered explanation text, so calculating a hash over “return WRONG” does not authorize publication of that proposal. Verification records separately retain the source hashes of the actual checker/reference modules. A changed implementation invalidates an old verification receipt; verifying again can refresh the receipt without rewriting the immutable package when its registered explanation still matches. Changes to the explanation/model require a new prepared package or the normal immutable amendment workflow.

An unbound authored proposal returns `experimental`, with any successful built-in reference tests separately labeled `reference_test_outcome: test_verified`. It cannot acquire the package-level `test_verified` outcome or authorize release by calculating a hash.

Verification returns the tested subject, source-bound reference identity, whether the authored text matches the registered explanation, and explicit `statement_correspondence: requires_review`, `ppc_argument_semantics: unverified`, and `implementation_refinement: unproved` fields. Teacher exports retain those distinctions. A registered reference explanation is not a formal proof of the story or arbitrary prose in a PPC 2.0 certificate. Story/domain/objective correspondence still requires actual mathematical review. The code does not invent reviewer identity or silently mark it reviewed.

Older releases are not rewritten or retroactively promoted. New publication cannot rely on an old receipt that lacks the current reference identity. Historical teacher exports warn when their authored explanation is not currently bound. No new SQLite schema or production data migration is needed for these repairs.

## Fragment correspondence

`ppc3.model_hash` is an integrity attachment, not a proof of interpretation. Its checked result, certificate fingerprint and scope are now retained in verification evidence.

- `auxiliary_propositional_lemma`: a sequent only; no algorithm correspondence asserted.
- `auxiliary_finite_model`: the exact graph only; no problem correspondence asserted.
- `explicit_finite_model`: requires a supported specification adapter. Pricing is currently the only adapter. The input IDs must be exactly every integer from `min_n` to `max_n`, and each allowed-output set must equal the pricing function's singleton answer. A valid graph with a different domain or Q is rejected. Other families must use the explicitly auxiliary scope or provide a separately reviewed adapter.

Even the pricing adapter checks the finite specification relation, not equality between a separate program's execution and that graph. A graph that immediately returns the correct preencoded answer is a correct finite model, not a verified implementation of a general algorithm.

## Strict JSON and work limits

`scripts/strict_json.py` is used at the package, certificate and nested-sample input boundaries. It rejects duplicate object members at every depth, NaN, Infinity, overflowing non-finite floating values, cyclic Python objects, non-string object keys and non-JSON types. Valid legacy canonical JSON encoding is retained (`strict-json-v1`); IDs and outputs are compared by that serialization identity. Integer samples require `type(value) is int`, so booleans and floats cannot masquerade as integer answers. JSON numbers are not arbitrary-precision real arithmetic.

Default file/text-payload budget is 16 MiB, input structure budget 200,000 nodes, and raw nesting budget 256. Propositional certificates have a stricter 10,000-node budget; formula/proof nesting is capped at 100. Finite certificates allow at most 1,000 input cases and 10,000 states per case, subject also to the global input budget. Limits count object keys as well as values. File reads are bounded before parsing; evidence hashes the exact bytes parsed rather than rereading a possibly changed file.

Normalized formulas remain shared DAGs. Equality, atom collection and evaluation visit those DAGs with memoization; no expanded-tree equality/hash traversal is used. Structural comparison has a 40,000-pair budget. The optional Boolean audit is limited to 12 atoms and an estimated 2,000,000 node-valuation evaluations; larger secondary audits are explicitly skipped while the derivation must still type-check. This audit is not an intuitionistic proof search engine.

Finite graph traversal and PPC 2.0 obligation dependency checks are iterative. A 10,000-state valid chain is within the supported state limit and does not depend on Python's recursion depth. Reachable nondeterministic cycles, deadlocks and wrong outputs still fail. A `resource_limit` result issues no certification and is distinct from an invalid inference or semantic counterexample. PPC 2.0 and ARDS wrappers expose resource failures as rejected/failed results with a `reason_code`, consistent with their existing status vocabulary.

## Isolated Lean evidence

The bridge executes only sources approved by `references/ppc3_lean_manifest.json`, copied into a unique run directory. The approval list pins the exact example, independent expected statements and abstract calculus source. It rejects altered sources before execution, checks the Lean 4.35.0/Lake 5.0.0 toolchain, chooses its bundled checker, and verifies hashes again before issuing evidence. Pins are reviewed inputs, not signatures against an attacker who can edit the verifier and its approval list.

Compilation and replay run under offline bubblewrap isolation with private home/tmp, only the toolchain and run directory restored, 64 MiB runtime thread stacks, two workers and a 4 GiB address-space cap. There is no fallback that disables sandboxing. Changing a source pin alone does not suffice to substitute `True` for a theorem: the independently pinned `PPC3Expected.lean` also checks the expected types and definitions. The bridge audits axiom reports and replays the modules through `leanchecker`.

```sh
python3 scripts/ppc3_lean.py
python3 scripts/ppc3_lean.py --fresh
```

`--fresh` requests a separate full-import replay with a 180-second timeout; ordinary operations have a 60-second timeout. Timeouts do not issue Lean certification. Every invocation retains copied source bytes, compiled artifacts and a result/command log in a new run directory. The three original examples have the same precise scope as before. The abstract soundness theorem/helper have no reported axiom dependencies. The pricing theorem permits `propext`. This does not prove that Python realizes the formal derivation datatype; that refinement remains open. No new external multi-kernel acceptance is implied by a bundled replay.

## Benchmark provenance and history

New CLI defaults write to `data/validation/ppc2/hardened-v1/` and `data/validation/ppc3/hardened-v1/`; `--out` selects a separate corpus root. Reports record Python version, canonical/report schema, generator/checker source hashes, seeds, exact counts and scope. Equal reruns are allowed. Every existing output is checked before any new member is written; mismatches preserve the corpus and require a new namespace/output directory. A source change can legitimately invalidate byte-for-byte report reproduction; that is exposed rather than silently replacing history.

The older 20261020/20261021 PPC 3.0 archives remain evidence for their original generators. The historical version drift cannot be undone by rewriting their reports. Rechecking old proof/model artifacts and regenerating the current version are separate operations. Seven algorithm families, two archived propositional templates, finite model tests, and parameter counts must remain separately reported.
