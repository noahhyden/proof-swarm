import Mathlib

/-!
Formalized statements + human-reviewed reference proofs for the parity problems.
The reference proof is the oracle's self-test: `lake build` compiling this file
proves each statement is provable (live verification), and the mutation tests
confirm a broken proof is rejected. See docs/lean-oracle-spec.md.
-/

namespace ProofSwarm

/-- even_plus_even: the sum of two even integers is even. -/
theorem even_plus_even (a b : ℤ) (ha : Even a) (hb : Even b) : Even (a + b) :=
  ha.add hb

/-- even_plus_odd: an even integer plus an odd integer is odd. -/
theorem even_plus_odd (a b : ℤ) (ha : Even a) (hb : Odd b) : Odd (a + b) :=
  ha.add_odd hb

/-- product_of_odds: the product of two odd integers is odd. -/
theorem product_of_odds (a b : ℤ) (ha : Odd a) (hb : Odd b) : Odd (a * b) :=
  ha.mul hb

end ProofSwarm
