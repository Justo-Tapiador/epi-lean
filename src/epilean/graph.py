from collections import defaultdict, deque

from .models import Declaration


def dependency_map(
    declarations: list[Declaration],
) -> dict[str, set[str]]:
    """Build a graph containing only dependencies found in the project."""
    known = {item.name for item in declarations}
    graph = defaultdict(set)

    for item in declarations:
        graph[item.name].update(
            dependency
            for dependency in item.dependencies
            if dependency in known
        )
        graph.setdefault(item.name, set())

    return dict(graph)


def transitive_dependencies(
    name: str,
    graph: dict[str, set[str]],
) -> set[str]:
    """Return all reachable dependencies without including the starting node."""
    if name not in graph:
        raise KeyError(f"Unknown declaration: {name}")

    visited = set()
    queue = deque(graph[name])

    while queue:
        current = queue.popleft()

        if current == name or current in visited:
            continue

        visited.add(current)
        queue.extend(graph.get(current, set()) - visited)

    return visited


def axiom_provenance(
    name: str,
    declarations: list[Declaration],
    graph: dict[str, set[str]],
) -> list[str]:
    """Find declared axioms in a declaration's transitive dependency closure."""
    kinds = {item.name: item.kind for item in declarations}
    closure = transitive_dependencies(name, graph)

    if kinds.get(name) == "axiom":
        closure.add(name)

    return sorted(
        dependency
        for dependency in closure
        if kinds.get(dependency) == "axiom"
    )