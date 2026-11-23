# Semantic Registry

The semantic registry is a JSON document containing an `entries` array.
Its machine-readable contract is
`schemas/semantic-registry.schema.json` (JSON Schema 2020-12).

## Required fields

Each entry must contain:

- `declaration`: exact Lean declaration name.
- `interpretation`: concise mathematical interpretation.
- `status`: `proposed`, `under_review`, or `reviewed`.
- `evidence`: supporting source, definition mapping, or reviewer note
  (required in practice for `reviewed` entries — the loader downgrades
  `reviewed` entries without evidence to `under_review` and warns).

## Optional fields

- `origin`: `human` (default) or `ai_proposal`. The loader downgrades
  any AI proposal marked `reviewed` to `under_review` and warns: AI
  proposals must never be auto-reviewed.
- `reviewed_by`, `reviewed_at`: reviewer identity and date for
  `reviewed` entries.
- `references`: array of pointers to literature or documentation.

## Validation behavior

The loader (`src/epilean/semantic.py`) is deliberately forgiving:
invalid entries are skipped with a **warning** rather than aborting the
audit. Currently warned and handled:

- entries that are not objects, or miss required fields, or have
  empty/non-string required values;
- duplicate `declaration` entries (only the first is kept);
- `reviewed` without `evidence` (downgraded to `under_review`);
- AI proposals marked `reviewed` (downgraded to `under_review`);
- references to declarations not found in the project (still kept —
  registries may cover more than one file — but reported).

A structurally invalid file (not JSON, or missing the `entries` array)
raises `ValueError` and aborts the audit.

## Semantics of `reviewed`

A `reviewed` status is a human workflow annotation. It is not a
machine-verified truth claim. It feeds the epistemic status
`SEMANTICALLY_SUPPORTED` (see `ARCHITECTURE.md`), which likewise means
"human review recorded", never "EPI-LEAN has verified this
interpretation".

## Effect on the epistemic assessment

| Registry status | Epistemic status |
|---|---|
| `reviewed` | `SEMANTICALLY_SUPPORTED` |
| `under_review` | `REVIEW_REQUIRED` |
| `proposed` | `POTENTIAL_MISMATCH` |
| no entry | `INSUFFICIENT_EVIDENCE` |
