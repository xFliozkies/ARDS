import Init

/-!
PPC 3.0 Lean 4 demonstration.

This file is a formal theorem example, NOT a locally Lean-verified artifact
until a real Lean invocation succeeds and the axiom listing is inspected.
It proves the mathematical pricing function conforms to its exact piecewise
specification; it does not prove arbitrary contestant code correct.
-/

namespace PPC3

def cakeCost (n threshold full discounted : Nat) : Nat :=
  if n < threshold then n * full else n * discounted

def cakeSpecification (n threshold full discounted result : Nat) : Prop :=
  (n < threshold ∧ result = n * full) ∨
  (¬ n < threshold ∧ result = n * discounted)

theorem cakeCost_correct (n threshold full discounted : Nat) :
    cakeSpecification n threshold full discounted
      (cakeCost n threshold full discounted) := by
  by_cases h : n < threshold
  · exact Or.inl ⟨h, by simp [cakeCost, h]⟩
  · exact Or.inr ⟨h, by simp [cakeCost, h]⟩

theorem conjunction_swap (P Q : Prop) (h : P ∧ Q) : Q ∧ P :=
  ⟨h.right, h.left⟩

theorem implication_compose (P Q R : Prop)
    (pq : P → Q) (qr : Q → R) : P → R :=
  fun hp => qr (pq hp)

#print axioms PPC3.cakeCost_correct
#print axioms PPC3.conjunction_swap
#print axioms PPC3.implication_compose

end PPC3
