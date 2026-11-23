# Example 02 — Compiled lake project with tricky syntax

This is a real lake project (one module, `EpiTest.Test`) whose
declarations were chosen to break the source-level regex extractor on
purpose. It is the positive/negative control pair for the
elaborated-environment mode (`--lake` / `--dump`).

## The declarations that break source-level extraction

| Declaration | Why it breaks regex extraction |
|---|---|
| `«théorème»`, `«tête»` | Guillemet (unicode) names don't match an ASCII identifier regex. |
| `instance : Inhabited Nat` (anonymous) | No user-visible name at source level. |
| `Inner.helper` + `Outer.helper` | The same short name in two namespaces: a name collision for source-level matching. |
| `secret_axiom` (used in `«théorème»`'s proof) | Used only inside a proof *term*; statement-level heuristics never see it. |
| `classical_use` | Proof via `Classical.em`; its axiom closure (`Classical.choice`, `propext`, `Quot.sound`) lives in proof terms. |

## Run the exact audit

Requires a Lean 4 toolchain (`lean` on PATH) matching Lean 4.15:

```bash
cd examples/lake-project
lake build
epilean audit . --lake --format markdown
```

Expected results (all elaborated-environment facts):

- 9 user declarations recovered with exact names (the anonymous
  instance appears as `instInhabitedNat_epiTest` — the name Lean gave
  it after elaboration).
- `théorème` → axiom provenance `['secret_axiom']` and direct
  dependencies include `secret_axiom` (proof-term reference).
- `classical_use` → axiom provenance `['Classical.choice',
  'Quot.sound', 'propext']`.
- `Inner.helper_pos` → `['propext', 'Quot.sound']` (the `omega`
  tactic's proof uses quotient soundness).
- Every other declaration → no axioms.

## The negative control

Run the *same* project in source mode:

```bash
epilean audit EpiTest --format json
```

The source-level extractor cannot recover `«théorème»`, `«tête»`, or
`Inner.helper` as such — documented in
`tests/test_lake_integration.py::test_source_mode_misses_what_elaborated_mode_finds`.
That gap is precisely why the elaborated mode exists.

## Dump format

The dump metaprogram (`tools/EpiDump.lean`) writes one JSON object per
line:

```json
{"name": "théorème", "kind": "theorem",
 "dependencies": ["Eq", "Eq.mpr", "secret_axiom", "..."],
 "axioms": ["secret_axiom"]}
```

- `dependencies`: exact direct references in the declaration's type
  *and* value/proof term.
- `axioms`: transitive axiom closure computed by Lean's
  `collectAxioms` at dump time (kernel-level query, not a heuristic).

## On the two `_elambda` "axioms"

When auditing Mathlib modules you may see names like
`Set.subtypeInsertEquivOption._elambda_1` with `kind: axiom` in the
histogram. These are opaque auxiliaries Lean elaboration introduces
(not user-declared axioms). The histogram reports them because
`collectAxioms` counts them; the report makes no distinction beyond
the name, which is visible evidence of their auxiliary nature.

## Saved Mathlib dumps (real evidence)

Two dumps produced from **Mathlib at tag `v4.15.0`** (olean cache via
`lake exe cache get`) are committed as evidence that the exact mode
works at Mathlib scale:

- `mathlib-Data.Set.Basic-dump.jsonl` — 736 declarations.
- `mathlib-Algebra.Group.Basic-dump.jsonl` — 492 declarations.

Audit them without any Lean toolchain:

```bash
epilean audit examples/lake-project/mathlib-Data.Set.Basic-dump.jsonl --dump --format markdown
```
