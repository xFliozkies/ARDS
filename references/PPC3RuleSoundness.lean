import Init
namespace PPCAudit
inductive Formula where
  | atom : Nat → Formula
  | top : Formula
  | bot : Formula
  | conj : Formula → Formula → Formula
  | disj : Formula → Formula → Formula
  | impl : Formula → Formula → Formula

def Meaning (v : Nat → Prop) : Formula → Prop
  | .atom n => v n
  | .top => True
  | .bot => False
  | .conj p q => Meaning v p ∧ Meaning v q
  | .disj p q => Meaning v p ∨ Meaning v q
  | .impl p q => Meaning v p → Meaning v q

def Satisfies (v : Nat → Prop) (g : List Formula) : Prop :=
  ∀ p, p ∈ g → Meaning v p

inductive Derives : List Formula → Formula → Prop where
  | hyp : p ∈ g → Derives g p
  | truth : Derives g .top
  | pair : Derives g p → Derives g q → Derives g (.conj p q)
  | left : Derives g (.conj p q) → Derives g p
  | right : Derives g (.conj p q) → Derives g q
  | inl : Derives g p → Derives g (.disj p q)
  | inr : Derives g q → Derives g (.disj p q)
  | intro : Derives (p :: g) q → Derives g (.impl p q)
  | apply : Derives g (.impl p q) → Derives g p → Derives g q
  | cases : Derives g (.disj p q) → Derives (p :: g) r → Derives (q :: g) r → Derives g r
  | absurd : Derives g .bot → Derives g r

theorem satisfies_cons (h : Satisfies v g) (hp : Meaning v p) :
    Satisfies v (p :: g) := by
  intro q hq
  cases hq with
  | head => exact hp
  | tail _ hm => exact h q hm

theorem inference_soundness (d : Derives g p) :
    ∀ v, Satisfies v g → Meaning v p := by
  induction d with
  | hyp hm => intro v h; exact h _ hm
  | truth => intro v h; exact True.intro
  | pair _ _ ihp ihq => intro v h; exact ⟨ihp v h, ihq v h⟩
  | left _ ih => intro v h; exact (ih v h).left
  | right _ ih => intro v h; exact (ih v h).right
  | inl _ ih => intro v h; exact Or.inl (ih v h)
  | inr _ ih => intro v h; exact Or.inr (ih v h)
  | intro _ ih => intro v h hp; exact ih v (satisfies_cons h hp)
  | apply _ _ ihi iha => intro v h; exact ihi v h (iha v h)
  | cases _ _ _ ihs ihl ihr =>
      intro v h
      cases ihs v h with
      | inl hp => exact ihl v (satisfies_cons h hp)
      | inr hq => exact ihr v (satisfies_cons h hq)
  | absurd _ ih => intro v h; exact False.elim (ih v h)
#print axioms PPCAudit.satisfies_cons
#print axioms PPCAudit.inference_soundness
#print PPCAudit.inference_soundness
end PPCAudit
