"""Detection and contraction of compiler/elaborator-generated declarations.

Elaborated environments contain many constants the user never wrote:
``_auxLemma.N`` simp lemmas, ``match_N`` matchers, ``proof_N`` abstracted
proofs, ``eq_N`` equation lemmas, compiler stages (``_cstage1``,
``_elambda_N``, ...). In a real Mathlib module they are ~20% of the
dump. Counting them as "declarations" inflates every statistic, and
``_elambda_N`` constants are even emitted with kind ``axiom``, which
would be reported as project axioms.

This module classifies them by name (every rule is named, so a report
can say *why* something was filtered) and *contracts* the dependency
graph through them: a public declaration that used ``_auxLemma.39``
inherits that lemma's own dependencies, so no reachability is lost.
Axiom provenance is unaffected: it comes from Lean's ``collectAxioms``.
"""

import re

INTERNAL_RULES: tuple[tuple[str, re.Pattern], ...] = (
    ("aux_lemma", re.compile(r"(^|\.)_auxLemma(\.|$)")),
    ("matcher", re.compile(r"(^|\.)match_\d+(\.|$)")),
    ("abstracted_proof", re.compile(r"\.proof_\d+$")),
    ("equation_lemma", re.compile(r"\.(eq_\d+|eq_def|_eq_\d+)$")),
    (
        "compiler_artifact",
        re.compile(
            r"(^|\.)_(cstage[123]|rarg|boxed|spec_\d+|lambda_\d+|"
            r"elambda_\d+|closed_\d+|unsafe_rec|sunfold)$"
        ),
    ),
    ("anonymous_command", re.compile(r"^(_example|_cmd)(\.|$)")),
)


def internal_rule(name: str) -> str | None:
    """Name of the first rule matching ``name``, or None if user-facing."""
    for rule, pattern in INTERNAL_RULES:
        if pattern.search(name):
            return rule
    return None


def is_internal_name(name: str) -> bool:
    return internal_rule(name) is not None


def contract_dependencies(
    dependencies: dict[str, tuple[str, ...]],
    internal: set[str],
) -> dict[str, tuple[str, ...]]:
    """Dependencies of every non-internal declaration, contracted.

    ``dependencies`` maps every dumped declaration (internal or not) to
    its direct dependencies. In the result, an in-dump internal
    dependency is replaced by whatever it (transitively, through
    internal nodes only) depends on. Dependencies outside the dump that
    are themselves internal-named (other modules' matchers, etc.) are
    dropped: their content is not available and they are noise.
    """
    memo: dict[str, frozenset[str]] = {}

    def expand(start: str) -> frozenset[str]:
        # Iterative post-order over internal nodes (chains can be deep).
        stack = [(start, False)]
        visiting: set[str] = set()
        while stack:
            node, done = stack.pop()
            if node in memo:
                continue
            if done:
                acc: set[str] = set()
                for dep in dependencies[node]:
                    if dep in internal:
                        acc |= memo.get(dep, frozenset())
                    elif dep in dependencies or not is_internal_name(dep):
                        acc.add(dep)
                memo[node] = frozenset(acc)
                visiting.discard(node)
                continue
            if node in visiting:
                continue  # cycle guard: contributes nothing further
            visiting.add(node)
            stack.append((node, True))
            for dep in dependencies[node]:
                if dep in internal and dep not in memo:
                    stack.append((dep, False))
        return memo.get(start, frozenset())

    result: dict[str, tuple[str, ...]] = {}
    for name, deps in dependencies.items():
        if name in internal:
            continue
        acc: set[str] = set()
        for dep in deps:
            if dep in internal:
                acc |= expand(dep)
            elif dep in dependencies or not is_internal_name(dep):
                acc.add(dep)
        acc.discard(name)
        result[name] = tuple(sorted(acc))
    return result
