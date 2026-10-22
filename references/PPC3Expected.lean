import PPC3Examples
import PPC3RuleSoundness

/- Independent expected statements. Source bytes are pinned by the bridge. -/
example : PPC3.cakeCost = fun (n threshold full discounted : Nat) =>
    if n < threshold then n * full else n * discounted := rfl
example : PPC3.cakeSpecification = fun (n threshold full discounted result : Nat) =>
    (n < threshold ∧ result = n * full) ∨
    (¬ n < threshold ∧ result = n * discounted) := rfl
example (n threshold full discounted : Nat) :
    (n < threshold ∧ PPC3.cakeCost n threshold full discounted = n * full) ∨
    (¬ n < threshold ∧ PPC3.cakeCost n threshold full discounted = n * discounted) :=
  PPC3.cakeCost_correct n threshold full discounted
example (P Q : Prop) : P ∧ Q → Q ∧ P := PPC3.conjunction_swap P Q
example (P Q R : Prop) : (P → Q) → (Q → R) → P → R := PPC3.implication_compose P Q R
example {g : List PPCAudit.Formula} {p : PPCAudit.Formula}
    (d : PPCAudit.Derives g p) :
    ∀ v, PPCAudit.Satisfies v g → PPCAudit.Meaning v p :=
  PPCAudit.inference_soundness d
