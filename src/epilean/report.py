import json

STATUS_ICONS = {
    "SEMANTICALLY_SUPPORTED": "supported",
    "POTENTIAL_MISMATCH": "potential mismatch",
    "REVIEW_REQUIRED": "review required",
    "INSUFFICIENT_EVIDENCE": "insufficient evidence",
}

# Above this many declarations, the per-declaration table and the
# per-declaration epistemic assessments are truncated in the markdown
# report (the JSON report always carries everything).
LARGE_REPORT_THRESHOLD = 60

# How many rows to show on each side of the truncation.
TRUNCATION_KEEP = 25


def render_json(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def _axiom_histogram(declaration_audits: list[dict]) -> list[tuple[str, int]]:
    """Count, per axiom name, how many declarations depend on it."""
    histogram: dict[str, int] = {}

    for item in declaration_audits:
        for axiom in item.get("declared_axiom_provenance", []):
            histogram[axiom] = histogram.get(axiom, 0) + 1

    return sorted(histogram.items(), key=lambda pair: (-pair[1], pair[0]))


def _truncate(items: list[dict]) -> tuple[list[dict], bool]:
    """Keep head+tail of a list if it exceeds the threshold."""
    if len(items) <= LARGE_REPORT_THRESHOLD:
        return items, False

    head = items[:TRUNCATION_KEEP]
    tail = items[-TRUNCATION_KEEP:]
    omitted = len(items) - 2 * TRUNCATION_KEEP
    # Marker row so the reader sees the cut explicitly.
    marker = {
        "name": f"... {omitted} more declarations omitted in this "
        f"markdown report (see JSON output for all) ..."
    }
    return head + [marker] + tail, True


def render_markdown(report: dict) -> str:
    summary = report.get("summary", {})
    formal = report.get("formal_verification", {})
    epistemic_summary = report.get("epistemic_summary", {})
    declaration_audits = report.get("declaration_audits", [])
    extraction_mode = report.get("extraction_mode", "source-heuristic")

    lines = [
        "# EPI-LEAN Audit Report",
        "",
        f"- Project: `{report.get('project_root', '')}`",
        f"- Tool version: {report.get('version', 'unknown')}",
        f"- Extraction mode: `{extraction_mode}`",
        f"- Declarations: {summary.get('declaration_count', 0)}",
        f"- Declared axioms: {summary.get('axiom_count', 0)}",
        f"- Semantic entries: {summary.get('semantic_entry_count', 0)}",
        f"- Reviewed entries: {summary.get('reviewed_semantic_entry_count', 0)}",
        "",
        "## Formal verification status",
        "",
        f"- System: {formal.get('system', 'Lean')}",
        f"- Status: `{formal.get('status', 'NOT_CHECKED')}`",
        "",
        formal.get("non_interference", ""),
        "",
        "## Epistemic summary",
        "",
    ]

    if epistemic_summary:
        lines.append("| Epistemic status | Count |")
        lines.append("|---|---|")
        for status, count in epistemic_summary.items():
            label = STATUS_ICONS.get(status, status)
            lines.append(f"| {label} (`{status}`) | {count} |")
        lines.append("")
    else:
        lines.append("No epistemic assessments were produced.")
        lines.append("")

    # Axiom histogram: the project-wide view of axiom provenance.
    histogram = _axiom_histogram(declaration_audits)

    if histogram:
        lines.append("## Axiom provenance histogram")
        lines.append("")
        lines.append(
            "Number of declarations whose axiom-provenance closure "
            "contains each axiom (Lean-computed in elaborated mode):"
        )
        lines.append("")
        lines.append("| Axiom | Dependent declarations |")
        lines.append("|---|---|")
        for axiom, count in histogram:
            lines.append(f"| `{axiom}` | {count} |")
        lines.append("")

    internal_filter = report.get("internal_filter")
    if internal_filter and internal_filter.get("filtered"):
        rules = ", ".join(
            f"{rule}: {count}"
            for rule, count in internal_filter.get("by_rule", {}).items()
        )
        lines.extend([
            "## Internal declarations excluded",
            "",
            f"{internal_filter['filtered']} compiler/elaborator-generated "
            f"constants were excluded from the declaration list ({rules}). "
            "The dependency graph was contracted through them, so no "
            "reachability is lost; axiom provenance is unchanged. Use "
            "`--include-internal` to list them.",
            "",
        ])

    closure = report.get("closure")
    if closure and closure.get("mode") != "full":
        lines.extend([
            "## Transitive closure",
            "",
            f"Mode: `{closure['mode']}` (requested: `{closure['requested']}`). "
            + (
                "Only closure sizes are reported (`transitive_dependency_count` "
                "in the JSON report)."
                if closure["mode"] == "count"
                else "Closures were not computed for a project of this size."
            ),
            "",
        ])

    frontier = report.get("frontier")
    if frontier and frontier.get("top"):
        lines.extend([
            "## Dependency frontier (constants outside the audited modules)",
            "",
            f"{frontier['external_constant_count']} distinct external "
            "constants are used. Most-used:",
            "",
            "| External constant | Audited declarations using it |",
            "|---|---|",
        ])
        for item in frontier["top"][:20]:
            lines.append(f"| `{item['name']}` | {item['used_by']} |")
        lines.append("")

    # Declaration table (truncated for large reports).
    shown_audits, _truncated = _truncate(declaration_audits)

    lines.extend([
        "## Declaration audit",
        "",
        "| Declaration | Kind | Dependencies | Axiom provenance | Epistemic status |",
        "|---|---|---|---|---|",
    ])

    epistemic_by_declaration = {
        item["declaration"]: item
        for item in report.get("epistemic_assessments", [])
    }

    for item in shown_audits:
        if "kind" not in item:
            lines.append(
                f"| {item.get('name', '')} | — | — | — | — |"
            )
            continue

        dependencies = ", ".join(
            f"`{name}`"
            for name in item.get("dependencies", [])
        ) or "—"

        axioms = ", ".join(
            f"`{name}`"
            for name in item.get("declared_axiom_provenance", [])
        ) or "—"

        assessment = epistemic_by_declaration.get(item["name"])
        status = (
            f"`{assessment['epistemic_status']}`"
            if assessment
            else "not assessed"
        )

        lines.append(
            f"| `{item['name']}` | {item['kind']} | "
            f"{dependencies} | {axioms} | {status} |"
        )

    lines.extend(["", "## Epistemic assessments", ""])

    assessments = report.get("epistemic_assessments", [])

    if assessments:
        shown_assessments, _ = _truncate(assessments)

        for assessment in shown_assessments:
            if "epistemic_status" not in assessment:
                lines.append(
                    f"### {assessment.get('declaration', '')}"
                )
                lines.append("")
                lines.append(
                    "Additional declarations omitted here; see the JSON "
                    "report for the full list."
                )
                lines.append("")
                continue

            lines.extend([
                f"### `{assessment['declaration']}`",
                "",
                f"- Epistemic status: `{assessment['epistemic_status']}`",
                (
                    f"- Human review required: "
                    f"{assessment['human_review_required']}"
                ),
                "",
                assessment["observation"],
                "",
                "Evidence:",
                "",
            ])
            lines.extend(
                f"- {item}"
                for item in assessment.get("evidence", [])
            )
            lines.append("")
    else:
        lines.append("No epistemic assessments were produced.")
        lines.append("")

    lines.extend(["", "## Semantic registry", ""])

    if report.get("semantic_entries"):
        for entry in report["semantic_entries"]:
            lines.extend([
                f"### `{entry.get('declaration', 'unknown')}`",
                "",
                entry.get("interpretation", ""),
                "",
                f"- Status: `{entry.get('status', 'unspecified')}`",
                f"- Evidence: {entry.get('evidence', 'Not supplied')}",
                f"- Origin: {entry.get('origin', 'human')}",
                "",
            ])
    else:
        lines.append("No semantic registry entries were supplied.")

    lines.extend(["", "## Warnings", ""])
    lines.extend(
        f"- {warning}"
        for warning in report.get("warnings", [])
    )

    lines.extend([
        "",
        "---",
        "This report is an experimental analysis. It is not a proof",
        "certificate and does not establish semantic adequacy. It",
        "does not modify the formal verification status of any Lean",
        "declaration.",
        "",
    ])

    return "\n".join(lines)
