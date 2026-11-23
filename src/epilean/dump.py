"""Loader for EPI-LEAN environment dumps (JSONL).

Each line of the dump describes one declaration of the elaborated Lean
environment, produced by tools/EpiDump.lean:

    {"name": ..., "kind": ..., "dependencies": [...], "axioms": [...]}

The "axioms" field is the transitive axiom closure computed by Lean's
own ``collectAxioms`` at dump time — a kernel-level query, not a
heuristic. The "dependencies" field holds the exact direct dependencies
(constants appearing in the declaration's type and value/proof term).
"""

import json
from pathlib import Path

from .models import Declaration

VALID_KINDS = frozenset({
    "axiom",
    "def",
    "theorem",
    "opaque",
    "ctor",
    "inductive",
    "quot",
    "recursor",
})

# Kinds of auxiliary declarations that are not user-facing theorems or
# definitions; they still count as graph nodes when present in a dump.
AUXILIARY_KINDS = frozenset({"ctor", "recursor", "quot"})


class DumpFormatError(ValueError):
    """Raised when a dump line does not match the expected shape."""


def load_dump(path: Path) -> list[Declaration]:
    """Load an EPI-LEAN JSONL dump into Declaration objects.

    File, line, and source fields are empty: they do not exist at the
    elaborated-environment level (positions are a source-file concept).
    """
    declarations = []

    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            stripped = line.strip()

            if not stripped:
                continue

            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as error:
                raise DumpFormatError(
                    f"{path}:{number}: invalid JSON: {error}"
                ) from error

            try:
                name = record["name"]
                kind = record["kind"]
                dependencies = record["dependencies"]
                # "axioms" is optional in the dump format: absent means
                # "not computed for this kind".
                axioms = record.get("axioms", [])
            except KeyError as error:
                raise DumpFormatError(
                    f"{path}:{number}: missing field {error}"
                ) from error

            if not isinstance(name, str) or not name:
                raise DumpFormatError(
                    f"{path}:{number}: invalid name {name!r}"
                )

            if kind not in VALID_KINDS:
                raise DumpFormatError(
                    f"{path}:{number}: unknown kind {kind!r}"
                )

            if not isinstance(dependencies, list) or not all(
                isinstance(dep, str) for dep in dependencies
            ):
                raise DumpFormatError(
                    f"{path}:{number}: dependencies must be a list of names"
                )

            if not isinstance(axioms, list) or not all(
                isinstance(ax, str) for ax in axioms
            ):
                raise DumpFormatError(
                    f"{path}:{number}: axioms must be a list of names"
                )

            declarations.append(
                Declaration(
                    name=name,
                    kind=kind,
                    file="",
                    line=0,
                    source="",
                    dependencies=tuple(sorted(set(dependencies))),
                )
            )

    if not declarations:
        raise DumpFormatError(
            f"{path}: no declarations found in dump"
        )

    return declarations


def declared_axioms(declarations: list[Declaration]) -> list[str]:
    """Names of dump declarations whose kind is `axiom`."""
    return sorted(
        item.name for item in declarations if item.kind == "axiom"
    )


def axiom_provenance_from_dump(
    declaration: Declaration,
    axioms_by_name: dict[str, list[str]],
) -> list[str]:
    """Axiom provenance for one declaration, straight from the dump.

    In elaborated mode, the provenance is the `axioms` closure Lean
    computed at dump time; the dict maps each declaration name to its
    closure. Names not present in the map get an empty closure (e.g.
    auxiliary kinds where the dump does not compute one).
    """
    if declaration.kind == "axiom":
        return [declaration.name]
    return sorted(axioms_by_name.get(declaration.name, []))
