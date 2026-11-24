# AI supervision (experimental)

EPI-LEAN can use a language model in two places. In both, the model is an
assistant whose output is *data to be validated*, never an authority.
This document states the guarantees, how each is enforced, and what is
not guaranteed.

## Commands

```bash
# Propose registry entries (written to a NEW file; never overwrites)
export ANTHROPIC_API_KEY=...            # keys come from the environment only
epilean propose dump.jsonl --provider anthropic --model <model-id> \
    --trail trail.jsonl --cassette cassette.jsonl --output ai-registry.json

# Re-run later, offline and identically, from the recorded exchange
epilean propose dump.jsonl --provider replay --cassette cassette.jsonl \
    --trail trail2.jsonl --output ai-registry-2.json

# Review an audit report: deterministic checks, optional AI second review
epilean audit dump.jsonl --dump --format json --output report.json
epilean supervise report.json [--provider ... --trail trail.jsonl]

# Check that a trail has not been edited
epilean verify-trail trail.jsonl
```

Providers: `anthropic`, `openai-compatible` (any `/chat/completions`
server, including local ones, via `--base-url`; key in `EPILEAN_API_KEY`
if needed) and `replay`. `--model` is mandatory for live providers: no
default is assumed so a stale model name is never used silently.

## Guarantees and how they are enforced

| Guarantee | Enforcement |
|---|---|
| A model cannot mark anything `reviewed` | Entries are rebuilt from a whitelist of fields; `status` is forced to `proposed`, `origin` to `ai_proposal`; model-supplied `status`, `reviewed_by`, `reviewed_at` are discarded (tested). The registry loader independently downgrades AI entries marked `reviewed`. |
| A model cannot talk about code that does not exist | Entries for declarations not in the requested batch are rejected. Supervision observations that cite unknown declarations are dropped. |
| A model cannot raise or hide a finding | Deterministic findings are computed before and independently of any model; AI observations are always `severity: info`, `verified: false`, `source: ai`. |
| The auditor is auditable | Every request/response is appended to a hash-chained trail (provider, model, prompt hash, response hash, accepted/rejected). Editing, deleting or reordering events fails `verify-trail`. |
| Model-assisted audits are reproducible | `--cassette` records exchanges; `--provider replay` answers only from the recording and never falls back to a live model. |
| Audited text cannot give orders to the model | Docstrings/statements are sanitized (control characters, tag break-outs, length) and fenced as untrusted data; the system prompt says to ignore instructions inside. |
| Formal status is never touched | The AI layer reads reports and dumps; it has no path to Lean. A deterministic check flags any report whose `formal_verification` block was altered. |

## What is NOT guaranteed

- **Prompt-injection resistance is mitigated, not proven.** Fencing and
  sanitization reduce risk; a determined adversary controlling the audited
  code may still influence a model's *proposal* text. This is why proposals
  stay `proposed` and require human review.
- **Proposal quality is limited by context.** The current dump has names,
  kinds, direct dependencies and axioms, but no statement text. Without a
  statement or docstring the model is inferring from names, and says so in
  `ai_provenance.context_fields`. Emitting `statement`/`docstring` from
  `EpiDump.lean` (the loader and prompts already accept them) is the main
  step to make proposals useful.
- **The trail is tamper-evident, not tamper-proof.** Anyone who can rewrite
  the whole file can recompute the chain. Anchor `head` hashes externally
  (CI logs, signed commits) when that matters.
- **A model reviewing a model is not verification.** The second review is
  one more fallible opinion, useful for surfacing things to look at.
- **Data egress.** Live providers send declaration names, dependencies and
  any statement text to the provider. Use a local `openai-compatible`
  server for confidential code.
- **The network providers have not been exercised against the live
  services** in this repository's tests (faked transport only).
- Quality of proposals and false-positive rates of the supervisor have not
  been measured. A seeded-defect benchmark (for example the
  `semantic-mismatch` example generalized) is the right next step.
