# Research Methodology

## Research question

Can the epistemic structure of a formally verified mathematical
development be made more inspectable by combining formal dependency
provenance with explicit, evidence-backed semantic correspondence
records?

## Working distinctions

- Formal correctness: a proof term is accepted by the Lean kernel.
- Semantic adequacy: formal definitions and propositions appropriately
  represent the intended mathematical concepts.
- Explanatory understanding: a human can reconstruct why the result
  follows and how its components relate mathematically.

These dimensions are related but non-identical. A development can score
differently on each: excellent formal correctness with weak semantic
documentation, or thorough interpretation records on top of a small
formal core.

## The five audit situations

The research program is organized around five situations in which a
Lean-accepted proof may still fail to support the claim made for it.
Each situation defines detection goals, evidence requirements,
automatable parts, and validation method in
`AUDIT_CAPABILITIES.md`. Summary:

1. **S1 — Wrong formalization** of the intended statement.
2. **S2 — Questionable axiom or premise dependence.**
3. **S3 — Misleading definition naming.**
4. **S4 — Omitted or under-documented hypotheses.**
5. **S5 — Misinterpretation of a formal result.**

## Non-interference

The project never presents its findings as invalidations of
Lean-verified proofs. Epistemic statuses (`POTENTIAL_MISMATCH`,
`REVIEW_REQUIRED`, `INSUFFICIENT_EVIDENCE`, `SEMANTICALLY_SUPPORTED`)
describe *documentation and review state*, not formal validity.

## Evaluation directions

1. Compare extracted dependencies against Lean-aware tooling.
2. Measure missed and spurious edges on curated projects.
3. Evaluate axiom provenance against known assumptions.
4. Have independent reviewers assess semantic entries.
5. Track unresolved correspondence obligations.
6. Preserve tool versions and source hashes.

## Non-claims

The prototype does not determine whether a formalization captures the
intended informal theorem. It does not infer mathematical meaning from
syntax alone or certify semantic equivalence.
