from epilean.graph import (
    axiom_provenance,
    dependency_map,
    transitive_dependencies,
)
from epilean.models import Declaration


def test_transitive_axiom_provenance():
    declarations = [
        Declaration("foundation", "axiom", "A.lean", 1, ""),
        Declaration("middle", "lemma", "A.lean", 2, "", ("foundation",)),
        Declaration("top", "theorem", "A.lean", 3, "", ("middle",)),
    ]

    graph = dependency_map(declarations)

    assert transitive_dependencies("top", graph) == {
        "middle",
        "foundation",
    }

    assert axiom_provenance(
        "top",
        declarations,
        graph,
    ) == ["foundation"]


def test_cycles_do_not_loop_forever():
    declarations = [
        Declaration("a", "lemma", "A.lean", 1, "", ("b",)),
        Declaration("b", "lemma", "A.lean", 2, "", ("a",)),
    ]

    graph = dependency_map(declarations)

    assert transitive_dependencies("a", graph) == {"b"}