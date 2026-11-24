from pathlib import Path

from . import __version__
from .closure import choose_closure_mode, closure_sizes
from .dump import (
    axiom_provenance_from_dump,
    load_dump_records,
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
from .internal import contract_dependencies, internal_rule
from .models import Declaration
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
    include_internal: bool = False,
    closure_mode: str = "auto",
    frontier_top: int = 50,
) -> dict:
    """Run an epistemic audit from an elaborated-environment dump.

    The dump (JSONL produced by tools/EpiDump.lean) carries exact
    declarations, exact direct dependencies, and — for each
    proof-carrying constant — the transitive axiom closure computed by
    Lean's collectAxioms. The audit therefore does not need to
    reconstruct either: it reports them as Lean computed them.

    Scale features:

    * Compiler/elaborator artifacts (``_auxLemma.N``, ``match_N``,
      ``proof_N``, ``eq_N``, ``_elambda_N`` ...) are excluded from the
      declaration list unless ``include_internal`` is set; the
      dependency graph is *contracted* through them, so no reachability
      is lost and axiom provenance (Lean-computed) is unchanged.
    * ``closure_mode`` selects how transitive dependencies are reported
      (``full`` lists, ``count`` only, ``none``; ``auto`` by size).
    * Dependencies on constants *outside* the dumped modules (e.g.
      Mathlib) are summarized in a ``frontier`` section.
    """
    path = Path(dump_path).resolve()

    if not path.exists() or not path.is_file():
        raise ValueError(f"Dump path is not a file: {dump_path}")

    records = load_dump_records(path)
    all_names = {record["name"] for record in records}

    # Last occurrence of a name wins, first-appearance order is kept.
    by_name: dict[str, dict] = {}
    for record in records:
        by_name[record["name"]] = record

    internal: set[str] = set()
    rule_counts: dict[str, int] = {}
    if not include_internal:
        for name in by_name:
            rule = internal_rule(name)
            if rule is not None:
                internal.add(name)
                rule_counts[rule] = rule_counts.get(rule, 0) + 1

    contracted = contract_dependencies(
        {name: tuple(record["dependencies"]) for name, record in by_name.items()},
        internal,
    )

    declarations = [
        Declaration(
            name=name,
            kind=by_name[name]["kind"],
            file="",
            line=0,
            source="",
            dependencies=contracted[name],
        )
        for name in by_name
        if name not in internal
    ]
    graph = dependency_map(declarations)
    names = {item.name for item in declarations}

    entries, semantic_warnings = load_semantic_registry(
        semantic_registry,
        all_names,
    )

    axioms_by_name = {
        name: record.get("axioms", []) for name, record in by_name.items()
    }

    mode = choose_closure_mode(closure_mode, len(declarations))
    sizes = closure_sizes(graph) if mode == "count" else {}

    declaration_audits = []

    for declaration in declarations:
        item = {
            **declaration.to_dict(),
            "declared_axiom_provenance": axiom_provenance_from_dump(
                declaration,
                axioms_by_name,
            ),
        }
        if mode == "full":
            closure = sorted(transitive_dependencies(declaration.name, graph))
            item["transitive_dependencies"] = closure
            item["transitive_dependency_count"] = len(closure)
        elif mode == "count":
            item["transitive_dependency_count"] = sizes[declaration.name]
        declaration_audits.append(item)

    assessments = assess_project(declaration_audits, entries)

    frontier_usage: dict[str, int] = {}
    for declaration in declarations:
        for dependency in declaration.dependencies:
            if dependency not in names:
                frontier_usage[dependency] = frontier_usage.get(dependency, 0) + 1
    frontier = {
        "external_constant_count": len(frontier_usage),
        "top": [
            {"name": name, "used_by": count}
            for name, count in sorted(
                frontier_usage.items(), key=lambda pair: (-pair[1], pair[0])
            )[:frontier_top]
        ],
    }

    warnings = [
        *ELABORATED_WARNINGS,
        *semantic_warnings,
    ]

    report = _finish_report(
        root=path.parent,
        declarations=declarations,
        declaration_audits=declaration_audits,
        entries=entries,
        assessments=assessments,
        warnings=warnings,
        extraction_mode="elaborated-environment",
    )
    report["summary"]["internal_declaration_count"] = len(internal)
    report["internal_filter"] = {
        "enabled": not include_internal,
        "filtered": len(internal),
        "by_rule": dict(sorted(rule_counts.items())),
    }
    report["closure"] = {"requested": closure_mode, "mode": mode}
    report["frontier"] = frontier
    return report


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
