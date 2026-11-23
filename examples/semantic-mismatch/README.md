# Example 01 — Semantic Mismatch in an Auxiliary Definition

## Overview

This example illustrates a situation in which a Lean theorem is formally valid, but its declaration and intended mathematical interpretation do not match the proposition it actually establishes.

It demonstrates one of the central motivations behind **EPI-LEAN**: formal proof correctness and semantic adequacy are related, but they are not the same thing.

The example is intentionally simple and does not represent a failure in Lean's kernel or proof verification.

> **Reproducibility note.** [`SemanticMismatch.lean`](SemanticMismatch.lean)
> uses only Lean 4 core declarations (no Mathlib) and elaborates cleanly
> (verified with Lean 4.15.0). The registry and
> [`audit-report.md`](audit-report.md) were generated with EPI-LEAN 0.1.1:
> `epilean audit examples/semantic-mismatch --semantic-registry
> examples/semantic-mismatch/semantic_registry.json`.
> The Lean-Real version below is kept for exposition; the committed file
> works on `Nat` so that it stays self-contained.

## 1. Intended Mathematical Statement

Suppose we want to establish that the square of every real number is nonnegative:

\[
\forall x \in \mathbb{R}, \quad 0 \leq x^2
\]

In Lean:

```lean
theorem square_nonnegative (x : ℝ) : 0 ≤ x * x := by
  positivity
```

This theorem is formally verified by Lean.

Its proposition corresponds to the intended mathematical statement.

## 2. Introducing a Misleading Auxiliary Definition

Now consider the following auxiliary definition:

```lean
def IsSquareNonnegative (x : ℝ) : Prop :=
  0 ≤ x + x
```

The name `IsSquareNonnegative` suggests that it represents the nonnegativity of the square of a real number.

However, its actual definition expresses a different property:

\[
0 \leq x+x
\]

This is not equivalent to:

\[
0 \leq x^2
\]

For example, the first proposition is false when \(x=-1\), whereas the second is true.

We can then prove:

```lean
theorem square_nonnegative_via_auxiliary
    (x : ℝ) (h : IsSquareNonnegative x) :
    0 ≤ x + x := by
  exact h
```

Lean accepts this theorem because the conclusion follows directly from the hypothesis.

There is no formal proof error here.

The potential problem is semantic: the auxiliary definition has a name that suggests a mathematical meaning different from its actual content.

## 3. What EPI-LEAN Should Investigate

An EPI-LEAN audit could identify several relevant observations.

| Audit dimension | Observation |
|---|---|
| Formal correctness | The theorem is accepted by Lean. |
| Declaration naming | `IsSquareNonnegative` suggests a property about squares. |
| Actual definition | The definition expresses nonnegativity of twice the input. |
| Semantic correspondence | The declared mathematical interpretation does not match the formal definition. |
| Assumption provenance | The theorem depends directly on a hypothesis containing its conclusion. |
| Epistemic assessment | Human semantic review is required. |

## 4. Illustrative Audit Report

The JSON below was the *proposed* report format from the original
design discussion. As of EPI-LEAN 0.1.1, this example is fully
implemented and reproducible:

- `SemanticMismatch.lean` elaborates cleanly with Lean 4 core alone
  (verified with Lean 4.15.0; no Mathlib required).
- Run `epilean audit examples/semantic-mismatch --semantic-registry
  examples/semantic-mismatch/semantic_registry.json` to regenerate
  [`audit-report.md`](audit-report.md).
- The real report flags `IsSquareNonnegative` and
  `square_nonnegative_via_auxiliary` as `POTENTIAL_MISMATCH` and marks
  `square_nonnegative_nat` as `SEMANTICALLY_SUPPORTED`, exactly the
  didactic scenario described here.

```json
{
  "declaration": "square_nonnegative_via_auxiliary",
  "formal_status": "accepted_by_lean",
  "semantic_status": "potential_mismatch",
  "declared_meaning": "The square of a real number is nonnegative",
  "actual_proposition": "0 <= x + x",
  "assumptions": [
    "IsSquareNonnegative x"
  ],
  "observations": [
    "The auxiliary definition does not express the nonnegativity of a square.",
    "The theorem does not establish square nonnegativity.",
    "The conclusion follows directly from the supplied hypothesis."
  ],
  "recommendation": "Human semantic review required"
}
```

## 5. Why This Is an Epistemic Issue

This example illustrates three distinct levels of assessment:

1. **Formal fact:** Lean verifies the theorem against its stated type and premises.
2. **Semantic observation:** The auxiliary definition does not correspond to the mathematical concept suggested by its name.
3. **Epistemic judgment:** A human reviewer must determine whether the discrepancy is accidental, misleading, or intentional.

EPI-LEAN should not automatically classify every naming discrepancy as a mathematical error. Names, comments, and documentation provide evidence of intended meaning, but they do not independently establish it.

The purpose of the audit is to make the discrepancy visible and traceable.

## 6. Expected EPI-LEAN Contribution

This example motivates several capabilities:

- Extraction of declarations and their formal types.
- Analysis of dependencies and assumptions.
- Comparison between formal definitions and registered semantic descriptions.
- Identification of potential mismatches between intended and actual mathematical content.
- Generation of reviewable audit observations.

The example also highlights an important architectural distinction: formal dependency analysis can be performed independently of semantic interpretation, while semantic assessments require additional evidence and, ultimately, human review.

## 7. Limitations of This Demonstration

This is a deliberately constructed example intended to illustrate the research problem.

It does not demonstrate that the current EPI-LEAN prototype can automatically infer mathematical intent from Lean declaration names or detect arbitrary semantic mismatches.

A practical implementation would require an explicit semantic registry, documented interpretations, and a mechanism for comparing those interpretations with extracted formal propositions.

**The central lesson is that a formally verified theorem establishes exactly what its formal proposition and premises state—not necessarily what its author intended the theorem to mean.**