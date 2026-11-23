namespace EpiLeanExample

/- Toy example for the EPI-LEAN prototype.
   It uses only Lean 4 core (no Mathlib) so it stays self-contained.
   `foundational_assumption` is an explicitly declared axiom:
   the audit must surface it in the dependency closure of
   `final_result`. -/

axiom foundational_assumption : True

theorem intermediate_result : True :=
  foundational_assumption

theorem final_result : True :=
  intermediate_result

end EpiLeanExample
