# Changelog

All notable changes to EPI-LEAN are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-11-23

### Added

- **Elaborated-environment extraction (exact mode)**: `tools/EpiDump.lean`,
  a self-contained Lean metaprogram (Lean 4.15, no Mathlib dependency),
  dumps the elaborated environment of a compiled project to JSONL —
  exact declaration names, exact direct dependencies (statement and
  proof term, including instance references), and per-declaration axiom
  provenance computed by Lean's own `collectAxioms` (kernel-level,
  transitive). This closes the roadmap-0.2.0 gap: real lake projects,
  including Mathlib-scale ones, audit with exact data instead of
  regex heuristics.
- New CLI flags: `--dump` (audit an existing JSONL dump) and `--lake`
  (build the dump for every module under `.lake/build/lib` and audit
  the combined result); `--module` restricts a `--lake` audit to
  specific modules.
- New modules: `dump.py` (validated JSONL dump loader) and
  `lake_dump.py` (toolchain/project discovery and the `lean --run`
  driver).
- **Axiom provenance histogram** in every report: declarations-per-axiom
  counts (e.g. Mathlib `Data.Set.Basic`: `propext` 530, `Quot.sound`
  465, `Classical.choice` 349).
- **Large-report handling**: markdown declaration tables truncate above
  60 entries with an explicit omission marker; the JSON report always
  carries everything.
- New example `examples/lake-project/`: a compiled lake project with
  declarations chosen to break the source-level extractor (guillemet
  names, anonymous instance, namespace collisions, proof-term-only
  axiom use), with a README.
- Tests: dump loader (10), dump audits and report truncation (11),
  CLI dump/lake flags (5), lake end-to-end integration (8, skipped
  without a Lean toolchain) — including a **negative control** that
  shows the source extractor missing what elaborated mode recovers on
  the same project.

### Verified

- Full suite: 71/71 tests passing.
- The `.lean` sources of all examples elaborate with Lean 4.15.0.
- **Mathlib at tag `v4.15.0`** (olean cache via `lake exe cache get`):
  `Mathlib.Data.Set.Basic` → 736 declarations; `Mathlib.Algebra.Group.Basic`
  → 492; axiom provenance histograms as above, all numbers computed by
  Lean's kernel-level `collectAxioms`.

## [0.1.1] — 2026-11-23

### Added

- Epistemic assessment layer (`epistemic.py`): every declaration now
  receives one of four statuses — `SEMANTICALLY_SUPPORTED`,
  `POTENTIAL_MISMATCH`, `REVIEW_REQUIRED`, `INSUFFICIENT_EVIDENCE` —
  computed from the semantic registry, with observation, evidence, and
  `human_review_required` kept as independent fields.
- **Non-interference principle** made explicit: reports carry a
  `formal_verification` block stating that EPI-LEAN does not invoke the
  Lean kernel and never invalidates, modifies, overrides, or replaces
  Lean's formal verification status.
- JSON Schema for the semantic registry
  (`schemas/semantic-registry.schema.json`), including `origin`
  (`human` / `ai_proposal`), `reviewed_by`, `reviewed_at`, and
  `references` fields.
- New example `examples/semantic-mismatch/` with a self-contained Lean
  file (no Mathlib), semantic registry, and generated audit report
  illustrating a `POTENTIAL_MISMATCH` (the `IsSquareNonnegative` case).
- Generated audit reports for both examples
  (`examples/basic/audit-report.md`,
  `examples/semantic-mismatch/audit-report.md`).
- `docs/AUDIT_CAPABILITIES.md`: the five audit situations (S1–S5) with
  detection goals, evidence requirements, automatable parts,
  non-conclusions, and validation method.
- Semantic registry hardening: duplicate declarations, empty strings,
  `reviewed` entries without evidence (auto-downgraded), and AI
  proposals marked `reviewed` (auto-downgraded) now produce warnings.
- `--version` flag for the CLI.
- New tests: epistemic assessment, semantic registry hardening,
  CLI behavior, schema conformance, and example regression.

### Fixed

- Example Lean files now actually elaborate with Lean 4 core
  (verified with Lean 4.15.0, no Mathlib): `Basic.lean` no longer uses
  `lemma` directly after an `axiom` (a Lean 4 parser pitfall) and
  `SemanticMismatch.lean` no longer relies on the Mathlib-only lemma
  `Nat.le_mul_self` (proved with `simp` instead).
- `strip_comments` no longer raises `IndexError` on a block comment
  ending at the last character of the file.
- Declaration extraction now recognizes `@[attribute]` annotations
  (e.g. `@[simp]`), the `partial` modifier, and named `instance`
  declarations.
- `README.md` file tree now matches the actual repository layout
  (previously it listed `examples/basic/` and `schemas/` before they
  existed).

### Changed

- Removed the unused `AuditResult` dataclass from `models.py`.
- Reports now show the tool version and an epistemic summary table.
- Version bumped to `0.1.1`.

## [0.1.0] — 2026-11-23

### Added

- Initial research prototype: source-level declaration extraction,
  heuristic dependency graph, transitive dependencies, declared-axiom
  provenance, semantic registry loading, JSON and Markdown audit
  reports, CLI (`epilean audit`), test suite, and CI workflow.
