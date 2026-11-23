/- Example 01 — Semantic mismatch in an auxiliary definition.

This example is *self-contained*: it uses only Lean 4 core declarations
(`Nat`, `String`, `True`, ...) and no Mathlib, so it elaborates without
any external dependency.

The point is that `IsSquareNonnegative` does not formalize "the square
of x is nonnegative" even though its name suggests that: on `Nat` the
definition `0 ≤ x + x` is equivalent to `0 ≤ x`, which is a *different*
property from `0 ≤ x * x` (they coincide on `Nat` only accidentally, and
the intended real-number statement is false for x = -1).
-/

/-- Misleading auxiliary definition: the name says "square nonnegative",
the body says "double nonnegative". -/
def IsSquareNonnegative (x : Nat) : Prop :=
  0 ≤ x + x

theorem square_nonnegative_via_auxiliary
    (x : Nat) (h : IsSquareNonnegative x) :
    0 ≤ x + x := by
  exact h

/-- The honest version of the intended statement, proved directly. -/
theorem square_nonnegative_nat (n : Nat) : 0 ≤ n * n := by
  simp
