"""Scalable transitive-closure statistics for dependency graphs.

The naive per-declaration BFS in ``graph.transitive_dependencies`` is
O(n * (n + e)) in time and its output is O(n^2) in report size
(measured: 8,000 declarations -> 14M closure entries, 14 s). For
Mathlib-scale audits this module condenses strongly connected
components (iterative Tarjan) and propagates reachability bitsets in
reverse topological order, giving exact closure *sizes* in one pass.

Memory is O(n^2 / 8) bytes worst case, so callers choose a mode (see
``choose_closure_mode``): full lists for small projects, counts for
medium ones, nothing for very large ones.
"""

FULL_CLOSURE_LIMIT = 2_000
COUNT_CLOSURE_LIMIT = 50_000

CLOSURE_MODES = ("auto", "full", "count", "none")


def choose_closure_mode(requested: str, node_count: int) -> str:
    """Resolve ``auto`` against project size; validate explicit modes."""
    if requested not in CLOSURE_MODES:
        raise ValueError(
            f"closure mode must be one of {', '.join(CLOSURE_MODES)}, "
            f"got {requested!r}"
        )
    if requested != "auto":
        return requested
    if node_count <= FULL_CLOSURE_LIMIT:
        return "full"
    if node_count <= COUNT_CLOSURE_LIMIT:
        return "count"
    return "none"


def strongly_connected_components(
    graph: dict[str, set[str]],
) -> list[list[str]]:
    """Iterative Tarjan. Components come out dependencies-first."""
    index_of: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[list[str]] = []
    counter = 0

    for root in sorted(graph):
        if root in index_of:
            continue
        work = [(root, iter(sorted(graph[root])))]
        index_of[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)

        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in graph:
                    continue
                if child not in index_of:
                    index_of[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(sorted(graph[child]))))
                    advanced = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index_of[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index_of[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                components.append(component)

    return components


def closure_sizes(graph: dict[str, set[str]]) -> dict[str, int]:
    """Exact number of distinct transitive dependencies per node.

    Matches ``len(graph.transitive_dependencies(name, graph))``: the
    starting node itself is never counted, even inside a cycle.
    """
    components = strongly_connected_components(graph)
    bit = {name: i for i, name in enumerate(sorted(graph))}
    component_of: dict[str, int] = {}
    for ci, component in enumerate(components):
        for name in component:
            component_of[name] = ci

    reach = [0] * len(components)
    for ci, component in enumerate(components):
        mask = 0
        for name in component:
            mask |= 1 << bit[name]
        for name in component:
            for dep in graph[name]:
                cd = component_of.get(dep)
                if cd is not None and cd != ci:
                    mask |= reach[cd]
        reach[ci] = mask

    return {
        name: reach[component_of[name]].bit_count() - 1 for name in graph
    }
