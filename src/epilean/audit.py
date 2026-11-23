from pathlib import Path

from . import __version__
from .dump import (
    axiom_provenance_from_dump,
    load_dump,
)
from .epistemic import (
    NON_INTERFERENCE_NOTE,
    assess_project,
    epistemic_summary,
)
from .extractor import extract_declarations
from .graph import (
    axiom_provenance,
    dependency_map,
    transitive_dependencies,
)
from .semantic import load_semantic_registry

SOURCE_WARNINGS = [
    "Source-level heuristic only: this is not a Lean kernel verification result.",
    "Dependency extraction may be incomplete or contain false positives.",
    "Semantic adequacy is not automatically established by this audit.",
]

ELABORATED_WARNINGS = [
    (
        "Declarations and dependencies come from the elaborated Lean "
        "environment (post-elaboration), extracted with Lean's own "
        "metaprogramming API; they are exact, not heuristic."
    ),
    (
        "Axiom provenance for each theorem is the transitive closure "
        "computed by Lean's collectAxioms (a kernel-level query)."
    ),
    (
        "Semantic adequacy is not automatically established by this "
        "audit: an exact dependency graph still says nothing about "
        "whether a theorem's statement means what its name claims."
    ),
]


def audit_project(
    project_root: Path,
    semantic_registry: Path | None = None,
) -> dict:
    """Run a source-level (heuristic) epistemic audit of a Lean project."""
    root = project_root.resolve()

    if not root.exists() or not root.is_dir():
        raise ValueError(f"Project path is not a directory: {project_root}")

    declarations = extract_declarations(root)
    graph = dependency_map(declarations)
    names = {item.name for item in declarations}

    entries, semantic_warnings = load_semantic_registry(
        semantic_registry,
        names,
    )

    declaration_audits = []

    for declaration in declarations:
        declaration_audits.append({
            **declaration.to_dict(),
            "transitive_dependencies": sorted(
                transitive_dependencies(declaration.name, graph)
            ),
            "declared_axiom_provenance": axiom_provenance(
                declaration.name,
                declarations,
                graph,
            ),
        })

    assessments = assess_project(declaration_audits, entries)

    warnings = [
        *SOURCE_WARNINGS,
        *semantic_warnings,
    ]

    return _finish_report(
        root=root,
        declarations=declarations,
        declaration_audits=declaration_audits,
        entries=entries,
        assessments=assessments,
        warnings=warnings,
        extraction_mode="source-heuristic",
    )


def audit_project_from_dump(
    dump_path: Path,
    semantic_registry: Path | None = None,
) -> dict:
    """Run an epistemic audit from an elaborated-environment dump.

    The dump (JSONL produced by tools/EpiDump.lean) carries exact
    declarations, exact direct dependencies, and — for each
    proof-carrying constant — the transitive axiom closure computed by
    Lean's collectAxioms. The audit therefore does not need to
    reconstruct either: it reports them as Lean computed them.
    """
    path = Path(dump_path).resolve()

    if not path.exists() or not path.is_file():
        raise ValueError(f"Dump path is not a file: {dump_path}")

    declarations = load_dump(path)
    graph = dependency_map(declarations)
    names = {item.name for item in declarations}

    entries, semantic_warnings = load_semantic_registry(
        semantic_registry,
        names,
    )

    # Axiom closure per declaration, straight from the dump lines.
    axioms_by_name: dict[str, list[str]] = {}

    with open(path, encoding="utf-8") as handle:
        import json

        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            axioms_by_name[record["name"]] = record.get("axioms", [])

    declaration_audits = []

    for declaration in declarations:
        declaration_audits.append({
            **declaration.to_dict(),
            "transitive_dependencies": sorted(
                transitive_dependencies(declaration.name, graph)
            ),
            "declared_axiom_provenance": axiom_provenance_from_dump(
                declaration,
                axioms_by_name,
            ),
        })

    assessments = assess_project(declaration_audits, entries)

    warnings = [
        *ELABORATED_WARNINGS,
        *semantic_warnings,
    ]

    return _finish_report(
        root=path.parent,
        declarations=declarations,
        declaration_audits=declaration_audits,
        entries=entries,
        assessments=assessments,
        warnings=warnings,
        extraction_mode="elaborated-environment",
    )


def _finish_report(
    root: Path,
    declarations,
    declaration_audits: list[dict],
    entries: list[dict],
    assessments: list[dict],
    warnings: list[str],
    extraction_mode: str,
) -> dict:
    """Assemble the final report shared by both audit modes."""
    return {
        "tool": "EPI-LEAN",
        "version": __version__,
        "project_root": str(root),
        "extraction_mode": extraction_mode,
        "formal_verification": {
            "system": "Lean",
            "status": "NOT_CHECKED",
            "note": (
                "EPI-LEAN does not invoke the Lean kernel. When Lean has "
                "accepted a proof, that formal status is unchanged by "
                "anything reported here."
            ),
            "non_interference": NON_INTERFERENCE_NOTE,
        },
        "declarations": [
            declaration.to_dict()
            for declaration in declarations
        ],
        "declaration_audits": declaration_audits,
        "semantic_entries": entries,
        "epistemic_assessments": assessments,
        "epistemic_summary": epistemic_summary(assessments),
        "warnings": warnings,
        "summary": {
            "declaration_count": len(declarations),
            "axiom_count": sum(
                item.kind == "axiom"
                for item in declarations
            ),
            "semantic_entry_count": len(entries),
            "reviewed_semantic_entry_count": sum(
                entry.get("status") == "reviewed"
                for entry in entries
            ),
        },
    }
