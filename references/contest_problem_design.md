# ARDS — contest problem design and presentation protocol

**Mandatory for new Classic RACG authoring and for statement revisions.**
This is the **student-facing** problem design standard, separate from the
private PPC. Read with the six profiles in
references/specification_comprehension.md, which remain authoritative.

**Reference:** The learner-supplied collection of 48 CodeChef problem
statements (CodeChef Problems.txt) and the learner-approved proposed rewrite
of RACG-0040, Enough Tokens From the First Bins. Learn design principles;
never copy the source's problem text, characters, branding, exact tasks or
unverified math extraction artifacts. Some original TXT equations were
garbled during extraction; do not reproduce those defects.

## Principle: understand the rules without being given the insight

The student must be able to say **what an answer means and whether it
satisfies the stated rules** before discovering **how to compute it**.

- Reading comprehension and algorithmic problem-solving are **separate**.
  A short statement is not automatically accessible; making prose long
  does not make a problem deeper. Use enough words to define what matters.
- A story is useful when the objects and narrative **carry actual rules**.
  Do not merely rename an array as bins or a graph as towns and then
  dump operation codes. A direct presentation is equally valid when the
  saved RACG draw chooses direct style. Do not add narrative filler.
- At Levels 1–3 the reader needs no prior study of the *tested algorithmic
  topic* to understand the objects, operations and goal. At Levels 4–6,
  specialized mathematical language and interpretation may legitimately
  form part of the challenge. Every level must remain decidable and free
  from missing rules.
- Defining **problem operations** is not spoiling the solution. A brief
  illustration of a new operation, rotation or resource-consumption rule
  is acceptable. Giving the prefix-sum identity, optimization strategy,
  invariant, algorithm, data-structure choice, pseudocode *for the
  solution*, or correctness argument is not.

## Mandatory two-phase generation procedure

### Phase A — Invent a mathematical challenge, not an algorithm prompt

1. Load the **real saved** RACG topic, primary reasoning pattern, difficulty,
   and story/direct draw; do not substitute, redraw, or change difficulty.
   Treat the topic as private authoring guidance, not a word to expose
   in the student's statement.
2. Design a distinct **reasoning objective**: minimize/maximize a value,
   count feasible objects, decide existence, recover hidden information
   from constraints, construct any valid object, reach a state, find the
   earliest failure, evaluate repeated interactions, etc. Match the
   recorded pattern, but **vary the actual reasoning task** across the
   archive instead of repeating maximum-of-array, update/query and
   budget templates with cosmetic new stories.
3. Form the underlying mathematical model, identify hard cases and a
   plausible correct solution privately. Check that the computational
   effort arises from that model rather than deliberately cryptic phrasing
   or inflated input sizes. Compare previous challenges for near duplicates.
4. If the chosen model does not justify the drawn difficulty, redesign the
   model or its challenge, **not the recorded random difficulty**. Do not
   inflate difficulty by removing definitions, inventing jargon, or
   forcing the algorithm name into the public problem.

### Phase B — Present a clear independent contest question

5. Write the **description first**, before the input format. Introduce
   every object, index convention, meaningful variable, permitted action,
   relationship, initial condition and requested output in natural order.
   For multiple operation types, define what they **mean in the problem
   world** before introducing command tokens such as 1 i d or 2 K 0.
   The description alone should let an appropriate reader reconstruct
   the rules and understand what a correct result would be.
6. Specify state transitions and timing if relevant: whether operations
   happen sequentially or simultaneously, what persists, what is
   consumed, whether actions can be repeated, whether gaps or intermediate
   steps are allowed, and the stopping or failure condition. State
   direction, reachability, equality/tie behavior, modulo, rounding,
   empty-state behavior, and impossible cases whenever their omission
   would change the answer.
7. Give precise **Input Format**, **Output Format**, **Constraints**, and
   at least two trustworthy **Samples** for executable new batch tasks.
   Use normal stdin/stdout with natural line/token layouts. Never
   introduce a leading T unless there are genuinely T cases. For NEW
   tasks do not add useless trailing tokens just to give unrelated
   commands the same number of fields. Every listed input variable must
   already have a meaningful role in the model or be clearly marked
   as a required historical placeholder for an existing judge contract.
8. Match bounds to the *proved* difficulty and efficient implementation.
   Explain one-based/zero-based indexing, total input-size constraints
   across test cases if used, ties, impossible answers, and whether any
   or all satisfying constructions are accepted. Sample I/O must be
   exact and independently evaluated. A small description illustration
   may explain a *new rule*; no solution walkthrough in the statement,
   no separate sample Explanation or Note sections.
9. Run the **reader test** and proof/verification gates. Independent of the
   teacher PPC, a reviewer should be able to state:
   - What objects exist before operations begin?
   - What changes after every action, and in what order?
   - What constitutes a valid answer, including exceptions/ties?
   - Can someone with the exact level's allowed prerequisites interpret
     the whole description without knowing the algorithm?
   - Does the description disclose an algorithmic shortcut or name?
   - Is the reasoning demand and design genuinely distinct from neighbors?
   Correct any failed answer **before** registration or release.

Use a natural reading flow: **title → explanation/model → conditions and
operations → exact question and special cases → Input Format → Output
Format → Constraints → Samples**. This is an ordering principle, not
a mandatory number of paragraphs. Concise direct tasks stay concise.

## Grounding examples from the learner's CodeChef collection

These are examples of **problem design**, not their algorithms or editorial
solutions:

- **International Gym Day:** define session cost, discount and total
  budget, then ask for the minimum sessions *without teaching algebra*.
- **Christmas Candy / How Many Maximums:** ask which recipients qualify
  under a relation or which maxima are possible given incomplete evidence;
  do not collapse every problem into direct array aggregation.
- **Chef and String / Table Strength:** define unusual transformation or
  equal-load rules clearly, with small non-solution illustrations.
- **Staircase Edits / Dividing by 2:** define legal modifications and ask
  for a minimum number; let the solver discover a useful structural fact.
- **Odd Repeat / Sum to 0:** one problem recovers hidden information;
  the other asks for **any** valid construction, not a unique optimum.
- **Chef Diet / Jumping in the hills:** explicitly describe state
  carry-over, left-to-right order and one-time resources.
- **Coupon System / Packaging Cupcakes:** ties and preference order are
  part of output correctness, not optional details.

No example implies every problem needs a story, a leading test-case count,
a particular difficulty level or a named algorithm.

## Worked ACCEPT/REJECT comparison: RACG-0040

The original RACG-0040 was drawn **Level 1 / story** under topic
Fenwick trees. The topic is private metadata; there is no reason for a
Level 1 student to recognize that name or the intended solution algorithm.

### REJECT: compressed, input-code-first description

> A game stall has N bins in a row, each holding a nonnegative number of
> tokens. Two kinds of operation arrive in order: 1 i d adds d tokens to
> bin i; 2 K 0 asks for the smallest number of first bins whose combined
> tokens reach at least K.

**Why:** the actual question is buried in command syntax; the learner is
left to unpack the meaning of "first bins", that no bin in between may be
skipped, how changes persist, and special cases. Headings alone do not
repair this. The original released statement also uses a historical
trailing zero in a type-2 command: do not replicate that artificial
token choice in fresh problem interfaces.

### ACCEPT: describe the meaning before the encoding

**Enough Tokens From the First Bins**

A festival game stall has \(N\) bins in a straight line, numbered from
\(1\) through \(N\). Initially, bin \(i\) contains \(A_i\) tokens.

Throughout the festival, \(Q\) operations occur **in order**:

- **Add tokens:** Add \(d\) tokens to bin \(i\). All tokens already in
  the bin remain there.
- **Find enough tokens:** Given \(K\), find the **smallest number of
  consecutive bins beginning with bin 1** whose combined tokens total
  at least \(K\). You may consider bin 1, the first two bins, the first
  three bins, and so forth; you may **not skip** any bin.

If \(K=0\), the answer is 0 because no bins are needed. If even all
\(N\) bins combined have fewer than \(K\) tokens, the answer is -1.
Questions do not change the bins. Each operation observes the changes
made by all preceding operations.

**Input Format**

- The first line contains two integers \(N,Q\), the number of bins
  and operations.
- The second line contains \(N\) integers \(A_1,\ldots,A_N\), the
  initial token counts.
- The following \(Q\) lines are either the addition command
  **1 i d** or the query command **2 K 0**. The trailing **0** in
  the existing RACG-0040 judge contract is a required placeholder with
  no effect.

**Output Format** — For each question, print the minimum required
number of bins, or -1 if impossible, on its own line.

**Constraints** — The current published RACG-0040 uses
\(1\le N,Q\le1000\), \(0\le A_i,d\le10^9\),
\(1\le i\le N\), and \(0\le K\le10^{15}\);
at least one question is guaranteed.

**Sample 1**

Input:

~~~text
3 3
1 0 2
2 2 0
1 2 4
2 4 0
~~~

Output:

~~~text
3
2
~~~

**Sample 2**

Input:

~~~text
1 2
0
2 0 0
2 1 0
~~~

Output:

~~~text
0
-1
~~~

This accepted description **does not** mention Fenwick trees, prefix
sums, binary search or any solution procedure. It explains *what to
compute* instead of *how*. The rewrite is an example to imitate, not
authorization to mutate the released RACG-0040 statement or judge
contract. If a live challenge is changed later, use a **versioned,
re-reviewed amendment**; never silently overwrite its canonical data.

## Rejection conditions for the independent statement review

**Fail** rather than merely suggesting a stylistic improvement if:

- A Level 1–3 reader must know the *tested topic* to understand the
  question; input codes are given without the underlying operation rules.
- Core initial state, update persistence, action order, direction,
  boundary, permitted gaps, or validity condition is omitted.
- An arbitrary story is added solely to rename data structures, or a
  direct draw is improperly converted to story form.
- There are conflicting valid interpretations of an answer; impossible
  cases, ties or accepted constructions are not resolved.
- A NEW problem has unused synthetic input tokens or contradicts its
  official plain-text judge interface.
- The problem's recorded difficulty is justified only by obscure jargon,
  not mathematical or algorithmic reasoning.
- The public text gives away the solution technique or decisive insight,
  or samples and stated constraints conflict.

The reviewer must quote a genuine **solver-visible** phrase and compare
its clarity and risks with the particular six-level profile and this
RACG-0040 worked case. The report should explicitly distinguish
**comprehension quality** from **reasoning quality**, and verify that
the public statement matches the private P1 contract without revealing
the teacher solution to learners.

## Preserve existing safeguards

Keep the weighted 30/25/20/12/8/5 difficulty draw, 15% continuation
with eligible-level renormalization, O/X/Y/P/Z provenance, and original
topic/presentation decisions. Maintain ordinary stdin/stdout, proper
KaTeX, protected PPC, separate candidate/oracle verification, and
immutable historical releases. This document does not call for any
database reset, regenerated challenges, or alteration of completed work.
