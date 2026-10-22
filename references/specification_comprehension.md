# ARDS — Difficulty-sensitive comprehension & specification correctness

**Required for all new Classic RACG authoring, independent review, and release.**

## Two different kinds of difficulty

A student must discover an algorithm; the student should not have to guess
unstated problem rules. **Conceptual interpretation can legitimately be part of
the task at higher difficulties**, but ambiguity, contradictions, undefined
objects, incomplete I/O, and unstated answer conventions are **never** valid
sources of difficulty.

- **Levels 1–3: comprehension precedes solving.** The reader should be able
  to understand the domain objects, allowed operations, relationships,
  constraints, and required answer from the statement, without having
  previously studied the algorithmic topic being assessed.
  - **Level 1:** Explain topic-specific terms and unfamiliar relationships
    plainly, with ordinary wording. Explicitly define every introduced
    variable/role *when* it first matters. Reading should not require
    knowing graph theory, dynamic programming, greedy algorithms, etc.
  - **Level 2:** Keep the specification independently understandable, with
    straightforward mathematical notation and modest interpretation.
  - **Level 3:** More abstraction and mathematical modeling are fine, but
    necessary subject-specific concepts must be defined or made derivable
    from the text rather than assumed as specialist common sense.
- **Levels 4–6: interpreting the abstraction may be part of solving.**
  Specialist terminology and mathematically dense definitions are permitted
  without beginner-oriented explanations. A learner may need prerequisite
  mathematics or theoretical understanding to *interpret* the model.
  - **Level 4:** Concise, abstract definitions and some prerequisite
    terminology are fine.
  - **Level 5:** Nontrivial modeling, implicit consequences of explicitly
    defined rules, and substantial interpretation can be intentional.
  - **Level 6:** High mathematical abstraction and synthesis may be central
    to the challenge. Do not artificially obscure an otherwise easy problem
    with confusing prose.
- **All six levels:** Every legal input and proposed output must have a
  determinate meaning. Enough facts must be available to judge whether an
  answer is valid. Specialized terms allowed at level 4+ must still have a
  consistent standard meaning or an explicit local definition. All symbols,
  endpoints, indices, conventions and edge cases must be bound to identifiable
  objects; never introduce new variables solely in input syntax while the
  problem description leaves the relationship unclear.

## The six levels: operational profiles and examples

**This section is authoritative for authoring and reviewing.** The short summary
above is not sufficient to approve a problem. Each example below is a
*statement fragment*, not a fully specified problem; complete tasks must also
supply the precise Input Format, Output Format, constraints, and samples.

**Important separation:** These are *comprehension profiles*, NOT algorithms
or ways of choosing RACG difficulty. Writing an easy task in Level 6 jargon
does **not** make it Level 6. The actual mathematical/algorithmic challenge
must independently justify its recorded level. Honor the story/direct draw.

### Level 1 — Plain foundations (`L1_plain_foundations`)

- **Reader can be assumed to know:** Everyday language, counting, integers,
  addition, comparisons. No graph theory, algorithm terminology, or formal
  set notation needed to *understand* the rules.
- **Author must define:** Every object and its role, unfamiliar relationships,
  which actions are allowed, what makes an output valid, and the impossible case.
  Introduce symbols along with the objects they represent.
- **Acceptable:** “There are `N` buildings and `M` possible wires. Wire
  `i` joins buildings `u_i` and `v_i` and costs `w_i`. A wire carries
  messages in either direction. Messages may pass through several buildings.
  Choose the cheapest set of wires that lets every building send a message to
  every other building.”
- **Reject:** “Given a weighted undirected graph, output a minimum spanning
  tree.” Here the reader must already know several graph concepts, and a
  named algorithmic structure is exposed.
- **Pass test:** Without graph theory, can the reader explain both directions,
  indirect connections, what each input value is, and what makes a chosen
  set valid? If not, the statement needs rewriting.

**Additional required Level 1 example:** Compare the original and learner-approved
rewrite of **RACG-0040 — Enough Tokens From the First Bins** in
`references/contest_problem_design.md`. The compressed original gives only
`1 i d` and `2 K 0` operation codes and assumes the reader can infer
"the smallest number of first bins." **Reject that presentation.** The
accepted story separately defines bin numbering and values, addition and
persistent state, a consecutive prefix with no skipped bins, and the
zero-target/impossible outcomes **before** teaching the input command
encoding. It does not teach prefix sums, Fenwick trees, or any algorithm.
Apply this same rules-before-input-codes criterion to other Level 1 problems;
the specific story, data structure, and input codes are NOT a template to copy.

### Level 2 — Concrete relations (`L2_concrete_relations`)

- **Reader can be assumed to know:** Simple sequences, positions, comparisons,
  and one-based/zero-based indexing after the convention is stated.
- **Author must define:** Any *task-specific* relationship, whether a block
  has gaps, whether endpoints are inclusive, and what property a selected
  block must satisfy. Allow modest translation of prose into inequalities.
- **Acceptable:** “You are given `N` numbers `A_1,...,A_N`. A block
  consists of consecutive positions `l,l+1,...,r`, with no skipped
  positions. It is non-decreasing if each later number is at least the
  number immediately before it. Find the greatest number of positions in
  such a block.”
- **Reject:** “Find the largest monotone contiguous subsequence.” It leaves
  the exact comparison and the meaning of subsequence versus contiguous
  segment uncertain.
- **Pass test:** Can the reader decide whether positions may be skipped,
  exactly which inequalities apply, and what length means without studying
  sequence algorithms?

### Level 3 — Defined abstraction (`L3_defined_abstraction`)

- **Reader can be assumed to know:** Algebra, indexed expressions, basic
  inequalities, and simple quantified/set expressions when introduced.
  Constructing the mathematical model can be part of solving.
- **Author must define:** Abstract relationships specific to the problem
  domain, composition of operations, and any property required to judge a
  proposed answer. Do not presume specialist theory of the tested topic.
- **Acceptable:** “There are `N` locations and one-way roads. Road
  `i` travels from `u_i` to `v_i` and takes `w_i` minutes. A route
  from `s` to `t` is a sequence of roads in which each next road starts
  where the previous one ends. Its duration is the sum of those travel
  times. Find the least duration, or `-1` if no route exists.”
- **Reject:** “Given a digraph, return `dist(s,t)`.” Neither the directed
  semantics nor the distance function has been made derivable for a reader
  without graph theory.
- **Pass test:** Can the reader reconstruct direction, allowed route,
  total cost, and result from the given definitions—not from knowledge of
  shortest-path algorithms?

### Level 4 — Standard domain terminology (`L4_standard_domain_terms`)

- **Reader can be assumed to know:** Standard discrete mathematics and
  domain vocabulary, including graph vertices, edges, simple paths, sets,
  summations, and quantifiers. Understanding abstract terminology may be
  a legitimate part of the challenge.
- **Author must define:** Input objects, output conditions, all *nonstandard*
  terminology, exceptional cases, and conventions the domain does not
  uniquely fix. No obligatory beginner glossary for standard terms.
- **Acceptable:** “Given an undirected graph `G=(V,E)` and an integer
  `k`, determine whether some `S ⊆ V` with `|S|=k` has at least one
  endpoint of every edge in `E`.”
- **Reject:** “Find a valid k-cover.” With no predicate for “cover,” a
  reader cannot know what would constitute a correct answer.
- **Pass test:** Are all undeclared specialist terms standard and
  unambiguous in this mathematical domain? Are the special graph features
  (such as loops or parallel edges), output convention, and input syntax
  resolved when material?

### Level 5 — Layered formalism (`L5_layered_formalism`)

- **Reader can be assumed to know:** Formal sets, relations, functions,
  orderings, and related theoretical vocabulary. Combining multiple
  definitions to understand the task is acceptable.
- **Author must define:** New operators/predicates, the domain being counted
  or optimized over, and any output/index/modulus conventions. Standard
  mathematical objects may be referenced without elementary explanation.
- **Acceptable:** “Let `(P,≼)` be a finite partially ordered set.
  A *linear extension* is an ordering of its elements such that
  `x≼y` implies `x` appears no later than `y`. Given
  `z∈P` and `k≥1`, count the linear extensions placing `z`
  at a position divisible by `k`.”
- **Reject:** “Count compatible arrangements.” Compatibility was not
  specified by a predicate, so the objective cannot be evaluated.
- **Pass test:** Can someone with the stated mathematical background write
  a definite validity predicate, without guessing extra conditions?
  Complete problem I/O must specify how `P,z,k` are encoded.

### Level 6 — Dense mathematical models (`L6_dense_mathematical_model`)

- **Reader can be assumed to know:** Advanced domain theory,
  equivalence classes, structured sets, quantified relations, and
  compressed formal definitions. Decoding the abstraction can take
  substantial reasoning.
- **Author must define:** The input universe, all *new* operators, the
  target mathematical object, special conventions, and an objectively
  checkable result. High abstraction should come from the real problem,
  not intentionally cryptic wording.
- **Acceptable:** “Let `P` be a finite poset and `L(P)` its set of
  linear extensions. For `z∈P`, `k≥1`, and prime `p`,
  compute the cardinality modulo `p` of
  `{π∈L(P) : position_π(z) ≡ 0 (mod k)}`,
  where positions start at 1.”
- **Reject:** “Let `F(P,k,p)` denote the answer; output `F`.”
  The meaning of `F` was never given, regardless of abstraction level.
- **Pass test:** Is every novel symbol defined, with a mathematical
  domain and answer relation? The complete input contract must still
  encode `P,z,k,p` and their bounds precisely.

## Cross-level checklist: apply to each proposed statement

| Level | Specialist prerequisite permitted? | What the statement must unpack | Comprehension work expected |
|---|---|---|---|
| 1 | No topic-specific knowledge | All unusual objects, direction/connection/validity rules, symbol roles | Follow rules directly |
| 2 | No topic-specific knowledge | Sequence/block relations, index and endpoint conventions | Translate simple prose to comparisons |
| 3 | No tested-topic theory | Domain relationships and abstract predicates that decide validity | Build a modest mathematical model |
| 4 | Yes, standard terminology | Nonstandard terms, conventions, exact output relation | Interpret standard mathematical abstractions |
| 5 | Yes, layered formal structures | New predicates/operators, quantifier domains and target condition | Combine definitions, derive implications |
| 6 | Yes, advanced mathematics | New symbols, input universe, precise target and output encoding | Substantial formal interpretation and synthesis |

**Never raise difficulty merely by deleting definitions. Never lower the
algorithmic difficulty because its statement is written accessibly.**
Never expose the target algorithm or proof in public text.

## Reviewer: concrete evidence required for the *exact* level

1. Quote one actual **student-visible** phrase and explain whether it meets
   the recorded level's reader baseline; do not repeat a profile label.
2. Identify the specific terminology a reader needs. Levels 1–3: demonstrate
   how the statement defines it without topic prerequisites. Levels 4–6:
   name permissible mathematical prerequisites and distinguish them from
   locally invented terms that still require definitions.
3. Locate the relevant input/output conventions and a concrete way to tell
   if a proposed answer satisfies the statement. Document any corner-case
   interpretation that could produce conflicting outputs.
4. Provide a **level-specific** judgment; explain how this problem meets,
   or fails, that profile. “The statement is clear” is not evidence.
5. Approve only when the level-specific comprehension standard **and**
   universal specification correctness both pass. Otherwise describe a
   counterexample or ambiguous interpretation and require revision.

The review report must include the exact level profile ID and a detailed
`level_specific_evidence` field grounded in the learner-visible statement.
Automated validation can check presence and profile consistency; it cannot
itself guarantee genuine semantic clarity.

## Illustrative example: wires between buildings

**Low-level statement** (without revealing the algorithm):

> There are `N` buildings and `M` possible wires. Each wire `i` connects
> building `u_i` with building `v_i` and costs `w_i` to install. A wire
> connects its two buildings in both directions. After installing some wires,
> buildings can communicate even through several intermediate buildings.
> Choose wires of minimum total cost so that every building can communicate
> with every other building, or print `-1` if this cannot be achieved.

In the corresponding **Input Format**, define the tokens `u_i`,
`v_i`, and `w_i` as two building IDs and the wire's cost. Specify
**space-separated integers**, one wire per line, and one-based IDs; in
**Output Format**, define all line breaks, ordering, and separators. At a
higher level, it may be appropriate to describe the same mathematical task
more tersely using weighted undirected graphs, connectivity, and minimum
spanning structure, provided every convention remains definite.

This is an illustration of **communication quality**, not a rule that
all Levels 1–3 must be written as stories or that the author should reveal
the solution technique.

## Mandatory author self-audit before registration

1. **Objects and symbols.** For each meaningful `N`, `M`, `u_i`,
   `v_i`, `w_i`, set, function, index and relation, locate its role or
   definition in the *learner's* statement. For Levels 1–3, define
   topic-specific semantics early enough to understand the task before
   reading the implementation-focused Input Format.
2. **Terminology and reader prerequisites.** At Levels 1–3, explain
   non-everyday notions needed only to *understand* the task (for example,
   "undirected" means the connection works in either direction; "connected"
   permits routes via intermediate buildings). At Levels 4–6,
   specialized vocabulary and abstraction may be intentional.
3. **Output validity test.** Could a reader given an input and a candidate
   output determine whether the candidate meets every requirement, without
   knowing the efficient algorithm? At Levels 4–6 this reader may need
   relevant mathematics.
4. **Input and output contract.** State the number of cases, token
   separators, line order, indexing, output line structure, tie conventions,
   and possible failure values. Public samples must match the executable
   contract exactly.
5. **Edge cases and consistency.** Confirm all corner conditions,
   including empty/minimum sizes and impossible cases, have unambiguous
   behavior across description, format, constraints, and sample outputs.
6. **Difficulty integrity.** Require reasoning difficulty appropriate to
   the recorded level; never compensate for an easy task by withholding
   definitions, adding irrelevant prose, or deliberately confusing syntax.
7. **Spoiler isolation.** Explain rules and relationships, **never** the
   intended data structure, algorithm, lemma, invariant, proof, or optimal
   construction in the student statement. The P1/P2/C/K reference stays
   private until explicit reveal.

## Independent reviewer acceptance criteria

In its written **specification analysis** the independent reviewer must
explicitly examine the learner-visible description, all mathematical
symbols, specialized terminology and level-appropriate comprehension,
input/output interpretation, corner-case semantics, and whether the task can
be evaluated without the intended solution. Review with the actual
registered difficulty and actual rendered public statement, not just the
internal model.

Reject or request a **versioned draft correction** for any ambiguity,
conflicting interpretations, missing definitions (relative to level), or
sample/contract mismatch. Record the reason; do not silently repair it in
display rendering. For higher-level tasks, do not reject mathematical
abstraction merely because a novice cannot decode it.

Human/AI prose review cannot guarantee semantic correctness. The reviewer
must document its reasoning and remaining assumptions, and executable
verification remains a separate required release gate.
