# Security Policy

## Supported versions

EPI-LEAN is an early-stage research prototype (0.1.x). Security fixes
are applied only to the latest released version.

| Version | Supported |
|---------|-----------|
| 0.1.x (latest) | ✅ |
| earlier 0.1.x | ❌ — upgrade first |

## Reporting a vulnerability

Please do **not** report security vulnerabilities through public
GitHub issues, pull requests, or discussions.

Instead, report them privately through GitHub's *Report a
vulnerability* form on the repository's **Security** tab, if enabled.
If that form is unavailable, open a private security advisory by
emailing the maintainer at the address published on the repository
profile or in `CITATION.cff` correspondence data.

Please include as much of the following as you can:

- The type of issue (e.g. path traversal, command injection, unsafe
  deserialization).
- The affected file or module (e.g. `src/epilean/extractor.py`).
- Step-by-step instructions or a proof of concept.
- The Python version involved.
- Any configuration relevant to reproducing the issue.

You should receive a response within 14 days. Please refrain from
public disclosure until a fix is released.

## Scope

EPI-LEAN processes untrusted input by design: it reads Lean source
files and JSON registries supplied by the user. Reports of any way in
which a *malformed file* can cause code execution, data corruption, or
a crash that escapes as an unhandled exception are in scope and
welcome.

Out of scope for this policy:

- Vulnerabilities in Lean itself or in Mathlib (report those to their
  own projects).
- Vulnerabilities in Python's standard library or in the CI platform
  (report those upstream).
- Issues that require already-existing code execution on the machine
  running the audit.

## Attributions

This policy borrows structure from GitHub's recommended security policy
templates.
