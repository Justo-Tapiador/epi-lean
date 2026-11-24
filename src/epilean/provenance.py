"""Explain *why* a declaration depends on an axiom.

Works on raw dump records (uncontracted, so the real chain including
``_auxLemma`` steps is visible). Everything here is derived from data
Lean computed; nothing is guessed.
"""

from collections import deque


def _index(records: list[dict]) -> dict[str, dict]:
    return {record["name"]: record for record in records}


def axiom_introduction_points(records: list[dict], axiom: str) -> list[str]:
    """Declarations whose closure has ``axiom`` but none of whose in-dump
    dependencies' closures do: the axiom enters *at* these nodes, via
    their own term or via constants outside the dump."""
    by_name = _index(records)
    points = []
    for record in records:
        if axiom not in record.get("axioms", []):
            continue
        carried = any(
            dep in by_name and axiom in by_name[dep].get("axioms", [])
            for dep in record["dependencies"]
        )
        if not carried:
            points.append(record["name"])
    return sorted(points)


def explain_axiom(records: list[dict], declaration: str, axiom: str) -> dict:
    """Shortest dependency chain from ``declaration`` to an introduction
    point of ``axiom``, with an explicit statement of what is known."""
    by_name = _index(records)
    if declaration not in by_name:
        raise KeyError(f"Unknown declaration: {declaration}")

    if axiom not in by_name[declaration].get("axioms", []):
        return {
            "declaration": declaration,
            "axiom": axiom,
            "in_closure": False,
            "path": [],
            "introduced_at": None,
            "direct_use": False,
            "external_candidates": [],
            "note": "The axiom is not in this declaration's closure.",
        }

    points = set(axiom_introduction_points(records, axiom))
    parent: dict[str, str | None] = {declaration: None}
    queue = deque([declaration])
    target = None
    while queue:
        node = queue.popleft()
        if node in points:
            target = node
            break
        for dep in sorted(by_name[node]["dependencies"]):
            # Only nodes carrying the axiom can lead to it.
            if (
                dep in by_name
                and dep not in parent
                and axiom in by_name[dep].get("axioms", [])
            ):
                parent[dep] = node
                queue.append(dep)

    path: list[str] = []
    node = target
    while node is not None:
        path.append(node)
        node = parent[node]
    path.reverse()

    direct = axiom in by_name[target]["dependencies"] or target == axiom
    external = sorted(
        dep for dep in by_name[target]["dependencies"] if dep not in by_name
    )
    if direct:
        note = "The chain ends at a declaration that references the axiom directly."
    else:
        note = (
            "The axiom enters through constants outside the dumped modules; "
            "inspect the external candidates listed (their own closures are "
            "not part of this dump)."
        )
    return {
        "declaration": declaration,
        "axiom": axiom,
        "in_closure": True,
        "path": path,
        "introduced_at": target,
        "direct_use": direct,
        "external_candidates": [] if direct else external,
        "note": note,
    }
