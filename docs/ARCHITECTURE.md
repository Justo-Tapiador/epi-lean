# Architecture

EPI-LEAN maintains two conceptually distinct structures:

1. Formal dependency graph.
2. Semantic registry.

The formal dependency graph records source-level references between Lean
declarations. The semantic registry records human-authored mathematical
interpretations and their supporting evidence.

The structures are linked by declaration names, but a semantic entry is
not considered true merely because a formal declaration exists.

On top of these two structures, the **epistemic assessment layer**
combines them into per-declaration epistemic statuses, and the
**non-interference principle** keeps those statuses categorically
separate from Lean's formal verification.

## Module map

| Module | Responsibility |
|---|---|
| `extractor.py` | Source-level extraction of declaration headers and heuristic intra-project references. |
| `graph.py` | Formal dependency graph, transitive dependencies, declared-axiom provenance. |
| `semantic.py` | Loading and validation of the semantic registry (duplicates, statuses, evidence rules). |
| `epistemic.py` | Epistemic statuses and assessments; non-interference note. |
| `audit.py` | Coordinates the pipeline and assembles the report. |
| `report.py` | JSON and Markdown rendering. |
| `cli.py` | Command-line interface. |

## Pipeline

1. Discover Lean source files.
2. Remove comments approximately.
3. Extract supported declaration headers (including `@[attribute]`
   annotations, `partial`/`protected`/… modifiers, and named
   `instance` declarations).
4. Identify references to declarations in the project.
5. Compute transitive dependencies.
6. Track declared axiom provenance.
7. Load and validate semantic registry entries.
8. Assess each declaration epistemically
   (`SEMANTICALLY_SUPPORTED`, `POTENTIAL_MISMATCH`,
   `REVIEW_REQUIRED`, `INSUFFICIENT_EVIDENCE`).
9. Generate JSON or Markdown reports.

## Epistemic statuses

The epistemic layer never uses `valid`/`invalid`, which could be
confused with Lean's formal verdicts. Instead:

| Status | Meaning |
|---|---|
| `SEMANTICALLY_SUPPORTED` | A human review of the interpretation has been recorded (workflow annotation, not a machine-verified claim). |
| `POTENTIAL_MISMATCH` | The recorded interpretation is a proposal; a mismatch between declared meaning and formal content cannot yet be excluded. |
| `REVIEW_REQUIRED` | The interpretation is under review; no conclusion drawn until it completes. |
| `INSUFFICIENT_EVIDENCE` | No registry entry exists; the prototype cannot infer meaning from syntax. |

Every assessment carries three independent fields — observation,
evidence, assessment — so an algorithmic suspicion is never presented
as a mathematical conclusion.

## Trust boundaries

- Lean's kernel checks formal proof terms.
- EPI-LEAN's current extractor is heuristic.
- Semantic interpretations are supplied by researchers.
- AI-generated interpretations must remain proposals until reviewed; the
  loader downgrades any AI proposal marked `reviewed`.
- Report generation is not proof verification.

## Non-interference principle

> EPI-LEAN does not invalidate, modify, override, or replace the
> formal verification status established by Lean. Its assessments are
> complementary epistemic evaluations and must remain explicitly
> distinguishable from formal proof validity.

Concretely: audits never modify the analyzed Lean files; reports carry
a `formal_verification` block with status `NOT_CHECKED` and this note;
and no epistemic status ever feeds back into Lean.

## Future Lean-aware backend

A future backend should consume elaborated Lean environments or trusted
Lean tooling. It should record the Lean version, Mathlib revision,
source hashes, build command, and extractor version. See
`AUDIT_CAPABILITIES.md` for what each audit situation additionally
requires.
