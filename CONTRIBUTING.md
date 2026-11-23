# Contributing to EPI-LEAN

Thank you for your interest in contributing. EPI-LEAN is an early-stage
research prototype, so contributions of all sizes are welcome — bug
reports, documentation improvements, tests, new examples, and research
ideas alike.

## Ground rules

Before anything else, please read `README.md` (sections *Fundamental
Principles* and *Scientific Scope and Limitations*) and
`docs/RESEARCH_METHODOLOGY.md`. Two rules matter most:

1. **Never present heuristic or AI-generated output as verified.**
   Anything that is not checked by a formal tool must be labeled a
   proposal.
2. **Never weaken the non-interference principle.** EPI-LEAN must not
   invalidate, modify, override, or replace the formal verification
   status established by Lean.

## Development setup

```bash
git clone https://github.com/YOUR-USERNAME/epi-lean.git
cd epi-lean
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Requirements: Python 3.10+ (Git and a Lean 4 installation are only
needed for Lean-side work; the Python audit tool runs without Lean).

## Running the tests and linter

Before opening a pull request, run:

```bash
pytest                 # full test suite
ruff check src tests   # style check (line length 100)
```

Both must pass. CI runs the same commands on Python 3.10–3.12.

## Workflow

1. Open an issue describing the bug or proposal (for research ideas,
   use the `research-discussion` label).
2. Fork the repository and create a branch from `main`
   (`git checkout -b my-contribution`).
3. Make your change. If it affects behavior, add or update tests. If it
   changes the report or registry format, update
   `schemas/semantic-registry.schema.json` and the docs.
4. Run `pytest` and `ruff check src tests`.
5. Open a pull request referencing the issue, with a short description
   of the change and, for research contributions, which of the five
   audit situations (`docs/AUDIT_CAPABILITIES.md`) it advances.

## Contribution areas

- **Extraction robustness**: parser edge cases, dependency accuracy
  measurements, Lean-aware backends.
- **Semantic registry tooling**: validation, schema evolution,
  review-workflow support.
- **Examples**: small, self-contained Lean developments with registries
  and expected reports. Keep examples Mathlib-free when possible so
  they stay reproducible.
- **Documentation**: clarity about what is implemented versus
  researched.
- **Testing**: regression tests, fixtures from real Lean projects.

## Semantic registry entries

If you contribute registry entries (for examples or case studies):

- Keep interpretations concise and mathematical.
- Always supply `evidence`.
- Mark AI-generated interpretations with `"origin": "ai_proposal"` and
  never mark them `reviewed`.
- Only humans set `status: reviewed`, ideally with `reviewed_by` and
  `reviewed_at`.

## Commit messages and style

- Write commit messages in the imperative mood ("Add hypothesis
  auditor", not "Added ...").
- Keep Python lines under 100 characters; the codebase uses 4-space
  indentation and type hints.
- Documentation and code comments are in English.

## Licensing

By contributing, you agree that your contributions will be licensed
under the Apache License 2.0 (see `LICENSE`).
