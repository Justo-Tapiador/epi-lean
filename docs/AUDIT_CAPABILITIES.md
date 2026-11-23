# Audit Capabilities

This document defines the five audit situations that organize EPI-LEAN's
research program. For each situation it states: what EPI-LEAN intends to
detect, what evidence it needs, what can be automated today, what it
must *not* conclude, and how a result is validated.

The guiding rule is a strict separation between **detection** and
**judgment**: an algorithmic observation must never be presented as a
mathematical conclusion.

## The five audit situations

| # | Situation | Typical symptom | Epistemic status used |
|---|---|---|---|
| S1 | Wrong formalization of the intended statement | The formal proposition differs from the intended informal theorem. | `POTENTIAL_MISMATCH` |
| S2 | Dependence on questionable axioms or premises | A theorem holds only because of an introduced axiom or premise. | `FOUNDATIONAL_CONCERN` (future) |
| S3 | Misleading definition naming | A definition's name suggests a different property than its body. | `POTENTIAL_MISMATCH` |
| S4 | Omitted or under-documented hypotheses | A conditional result is communicated as unconditional. | `UNJUSTIFIED_GENERALIZATION` (future) |
| S5 | Misinterpretation of a formal result | The conclusion is presented with a meaning it does not have. | `TRACEABILITY_GAP` (future) |

## S1 — Wrong formalization of the intended statement

- **Intended detection.** The formal proposition does not capture the
  informal statement the author meant to prove (for example,
  formalizing `∀ x, 0 ≤ x + x` while intending `∀ x, 0 ≤ x * x`).
- **Evidence required.** A semantic registry entry recording the
  intended informal interpretation, plus the extracted formal source.
- **Automatable today.** Comparing the registry's recorded
  interpretation with the extracted declaration, and flagging every
  interpretation that is still `proposed` as `POTENTIAL_MISMATCH`.
- **Must not conclude.** That the formalization *is* wrong; only a
  human review can decide whether the mismatch is accidental,
  deliberate, or acceptable.
- **Validation.** Human review of the flagged entry; the review outcome
  is recorded as `reviewed` with evidence.

## S2 — Dependence on questionable axioms or premises

- **Intended detection.** A theorem transitively depends on an axiom
  introduced in the project (e.g. `axiom magic : False` enabling
  `theorem one_eq_two : 1 = 2`).
- **Evidence required.** The dependency graph and the declaration kinds
  extracted at source level; in elaborated mode, the per-declaration
  axiom closure computed by Lean's `collectAxioms`.
- **Automatable today.** Declared-axiom provenance: which declared
  axioms appear in the transitive closure of each declaration
  (`graph.axiom_provenance` in source mode; `collectAxioms` closures
  in elaborated mode — kernel-computed, exact). The report also carries
  an axiom-provenance histogram: declarations-per-axiom counts across
  the whole project (e.g. for `Mathlib.Data.Set.Basic`: `propext`
  530, `Quot.sound` 465, `Classical.choice` 349).
- **Must not conclude.** That an axiom is *unacceptable*; axioms of
  Lean's ambient logic (propositional extensionality, quotients,
  choice) are standard, and acceptability depends on the foundational
  stance chosen by the researcher.
- **Validation.** Inspecting the reported axiom provenance against the
  project's intended foundational baseline; in the future, against the
  full trusted environment of a Lean-aware backend.

## S3 — Misleading definition naming

- **Intended detection.** A name such as `IsSquareNonnegative` whose
  body expresses a different property (`0 ≤ x + x` instead of
  `0 ≤ x * x`). See `examples/semantic-mismatch/`.
- **Evidence required.** The extracted definition body plus a registry
  entry for the claimed interpretation.
- **Automatable today.** Surfacing the definition body next to the
  claimed interpretation, flagging unreviewed claims. The *semantic
  comparison itself* is not automatic: names are evidence of intent,
  not proof of it.
- **Must not conclude.** That the naming is an error; it could be a
  deliberate choice, a placeholder, or an in-joke. The audit makes the
  discrepancy visible and traceable; a human decides.
- **Validation.** Human review of the flagged entry.

## S4 — Omitted or under-documented hypotheses

- **Intended detection.** A proposition holds only under conditions
  (e.g. `x / x = 1` requires `x ≠ 0`) that are dropped when the result
  is communicated.
- **Evidence required.** Extraction of theorem hypotheses and scope
  conditions; today only source-level heuristics are available.
- **Automatable today.** Partially: hypothesis *presence* in the
  declaration header is visible in the extracted source. Whether a
  communicated claim omits a condition is an external comparison the
  prototype cannot make.
- **Must not conclude.** That a hypothesis was omitted in
  communication; that concerns text outside the analyzed source.
- **Validation.** Future hypothesis-and-scope auditor operating on
  elaborated Lean environments.

## S5 — Misinterpretation of a formal result

- **Intended detection.** All definitions and proofs are correct, but
  the conclusion is presented with a meaning that does not follow from
  them (relevant for translations between theories, equivalent
  definitions under hypotheses, structure transformations).
- **Evidence required.** Reconstruction of the semantic graph: what
  each intermediate result means and how meanings transform along the
  dependency chain.
- **Automatable today.** Nothing reliable. This requires the planned
  mathematical traceability engine.
- **Must not conclude.** Anything; the current prototype explicitly
  reports `INSUFFICIENT_EVIDENCE` for declarations without registry
  entries rather than guessing.
- **Validation.** The planned correspondence engine plus independent
  human mathematical review.

## Readiness summary

| Situation | Prototype readiness |
|---|---|
| S1 | Partial — registry comparison, no automatic intent inference |
| S2 | Partial — axiom provenance now kernel-computed in `--lake`/`--dump` mode (Lean's `collectAxioms`), no environment-level questionability analysis |
| S3 | Partial — visibility and flagging, no automatic semantic comparison |
| S4 | Partial — hypothesis extraction heuristics only |
| S5 | Not ready — awaiting the traceability engine |

## Extraction modes and what each supports

Two extraction modes shipped as of 0.2.0:

- **Source mode** (default): regex heuristics over `.lean` files. No
  toolchain needed. Cannot see guillemet names, anonymous instances,
  namespace collisions, or proof-term references — see
  `examples/lake-project/` for the negative control.
- **Elaborated mode** (`--lake` / `--dump`): the exact elaborated
  environment via `tools/EpiDump.lean`. Exact names, exact direct
  dependencies (statement + proof term), and per-declaration axiom
  provenance computed by Lean's `collectAxioms`. This is the mode for
  real projects, verified against Mathlib (`Mathlib.Data.Set.Basic`:
  736 declarations; `propext` in 530 closures, `Quot.sound` in 465,
  `Classical.choice` in 349).

S2's axiom-provenance reporting is therefore *exact* in elaborated
mode: what remains partial is judging whether an axiom is
*questionable* — a semantic, human-review question.

## Non-interference with formal verification

None of the five situations ever invalidates a Lean-verified proof.
EPI-LEAN assessments are complementary epistemic evaluations: a
`POTENTIAL_MISMATCH` flag means *the claimed meaning deserves human
review*, never that the proof is wrong or that Lean's verdict changes.
