/- tricky declarations that break regex extraction -/

-- unicode name with guillemets
def «tête» (n : Nat) : Nat := n + 1

-- instance with anonymous name
instance : Inhabited Nat := ⟨0⟩

-- named instance
instance instCos : OfNat Nat (nat_lit 3) := ⟨3⟩

-- axiom used only inside a proof
axiom secret_axiom : ∀ n : Nat, n + 0 = n

-- theorem with unicode name and axiom dep
theorem «théorème» : ∀ n : Nat, n + 0 = n + 0 := by
  intro n
  rw [secret_axiom n]

-- namespaced declarations
namespace Inner
  def helper (n : Nat) : Nat := 2 * n
  theorem helper_pos : ∀ n : Nat, 0 < helper n + 1 := by
    intro n
    omega
end Inner

-- short-name collision: two helpers in different namespaces
namespace Outer
  def helper (b : Bool) : Bool := !b
end Outer

-- a proof using Classical.em
theorem classical_use (p : Prop) : p ∨ ¬ p := Classical.em p
