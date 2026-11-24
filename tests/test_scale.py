"""Scale features: internal-artifact filtering, closure sizes, frontier,
axiom explanation, and the real Mathlib example dumps."""

import json
import random
from pathlib import Path

import pytest

from epilean.audit import audit_project_from_dump
from epilean.closure import (
    choose_closure_mode,
    closure_sizes,
    strongly_connected_components,
)
from epilean.graph import transitive_dependencies
from epilean.internal import contract_dependencies, internal_rule
from epilean.provenance import axiom_introduction_points, explain_axiom
from epilean.report import render_markdown

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "lake-project"
SET_BASIC = EXAMPLES / "mathlib-Data.Set.Basic-dump.jsonl"


def _write(path: Path, records: list[dict]) -> Path:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    "name, rule",
    [
        ("Mathlib.Data.Set.Basic._auxLemma.39", "aux_lemma"),
        ("Set.Nonempty.not_subset_empty.match_1", "matcher"),
        ("Foo.bar.proof_3", "abstracted_proof"),
        ("Foo.bar.eq_1", "equation_lemma"),
        ("Foo.bar.eq_def", "equation_lemma"),
        ("Set.subtypeInsertEquivOption._elambda_1", "compiler_artifact"),
        ("Foo._cstage1", "compiler_artifact"),
        ("_example.foo", "anonymous_command"),
    ],
)
def test_internal_rules_flag_artifacts(name, rule):
    assert internal_rule(name) == rule


@pytest.mark.parametrize(
    "name",
    ["Set.inter_comm", "théorème", "Nat.add_comm", "my_closed_form", "Foo.equation_1x", "Foo.match"],
)
def test_internal_rules_keep_user_names(name):
    assert internal_rule(name) is None


def test_contraction_keeps_reachability_through_internal_nodes():
    deps = {
        "pub": ("Mathlib.X._auxLemma.1", "Nat"),
        "Mathlib.X._auxLemma.1": ("Mathlib.X._auxLemma.2", "propext"),
        "Mathlib.X._auxLemma.2": ("helper", "Other.match_1"),
        "helper": (),
    }
    internal = {"Mathlib.X._auxLemma.1", "Mathlib.X._auxLemma.2"}
    out = contract_dependencies(deps, internal)
    assert set(out) == {"pub", "helper"}
    # helper (in dump) and propext (external) survive; external matcher dropped.
    assert out["pub"] == ("Nat", "helper", "propext")


def test_contraction_survives_internal_cycles():
    deps = {
        "pub": ("a._auxLemma.1",),
        "a._auxLemma.1": ("a._auxLemma.2",),
        "a._auxLemma.2": ("a._auxLemma.1", "x"),
    }
    out = contract_dependencies(deps, {"a._auxLemma.1", "a._auxLemma.2"})
    assert "x" in out["pub"]


def test_closure_sizes_match_bfs_on_random_graphs_with_cycles():
    rng = random.Random(7)
    for _ in range(150):
        n = rng.randint(1, 20)
        graph = {
            f"n{i}": {f"n{j}" for j in rng.sample(range(n), rng.randint(0, min(n, 4)))}
            for i in range(n)
        }
        sizes = closure_sizes(graph)
        for name in graph:
            assert sizes[name] == len(transitive_dependencies(name, graph))


def test_scc_groups_cycles():
    graph = {"a": {"b"}, "b": {"a"}, "c": {"a"}}
    components = [sorted(c) for c in strongly_connected_components(graph)]
    assert ["a", "b"] in components
    assert components.index(["a", "b"]) < components.index(["c"])  # dependencies first


def test_closure_handles_deep_chains_without_recursion_error():
    n = 5000
    graph = {f"n{i}": ({f"n{i + 1}"} if i + 1 < n else set()) for i in range(n)}
    assert closure_sizes(graph)["n0"] == n - 1


def test_choose_closure_mode():
    assert choose_closure_mode("auto", 10) == "full"
    assert choose_closure_mode("auto", 10_000) == "count"
    assert choose_closure_mode("auto", 10_000_000) == "none"
    assert choose_closure_mode("none", 3) == "none"
    with pytest.raises(ValueError):
        choose_closure_mode("bogus", 3)


def _records_with_internals():
    return [
        {"name": "pub", "kind": "theorem", "dependencies": ["T._auxLemma.1", "Nat"],
         "axioms": ["propext"]},
        {"name": "T._auxLemma.1", "kind": "theorem", "dependencies": ["propext"],
         "axioms": ["propext"]},
        {"name": "f._elambda_1", "kind": "axiom", "dependencies": [], "axioms": ["f._elambda_1"]},
        {"name": "real_axiom", "kind": "axiom", "dependencies": [], "axioms": ["real_axiom"]},
    ]


def test_audit_filters_internal_and_does_not_count_elambda_as_axiom(tmp_path):
    report = audit_project_from_dump(_write(tmp_path / "d.jsonl", _records_with_internals()))
    names = {d["name"] for d in report["declarations"]}
    assert names == {"pub", "real_axiom"}
    assert report["summary"]["axiom_count"] == 1
    assert report["summary"]["internal_declaration_count"] == 2
    assert report["internal_filter"]["by_rule"] == {
        "aux_lemma": 1,
        "compiler_artifact": 1,
    }
    pub = next(a for a in report["declaration_audits"] if a["name"] == "pub")
    assert pub["declared_axiom_provenance"] == ["propext"]  # Lean's closure, untouched
    assert "propext" in pub["dependencies"]  # inherited through the contracted lemma


def test_audit_include_internal_restores_everything(tmp_path):
    report = audit_project_from_dump(
        _write(tmp_path / "d.jsonl", _records_with_internals()), include_internal=True
    )
    assert report["summary"]["declaration_count"] == 4
    assert report["internal_filter"]["enabled"] is False


def test_closure_modes_in_report(tmp_path):
    dump = _write(tmp_path / "d.jsonl", [
        {"name": "a", "kind": "def", "dependencies": ["b"], "axioms": []},
        {"name": "b", "kind": "def", "dependencies": ["c"], "axioms": []},
        {"name": "c", "kind": "def", "dependencies": [], "axioms": []},
    ])
    full = audit_project_from_dump(dump, closure_mode="full")
    count = audit_project_from_dump(dump, closure_mode="count")
    none = audit_project_from_dump(dump, closure_mode="none")
    a = lambda r: next(x for x in r["declaration_audits"] if x["name"] == "a")  # noqa: E731
    assert a(full)["transitive_dependencies"] == ["b", "c"]
    assert a(full)["transitive_dependency_count"] == 2
    assert "transitive_dependencies" not in a(count)
    assert a(count)["transitive_dependency_count"] == 2
    assert "transitive_dependency_count" not in a(none)
    assert none["closure"] == {"requested": "none", "mode": "none"}


def test_frontier_counts_external_constants(tmp_path):
    dump = _write(tmp_path / "d.jsonl", [
        {"name": "a", "kind": "theorem", "dependencies": ["Mathlib.Foo", "b"], "axioms": []},
        {"name": "b", "kind": "theorem", "dependencies": ["Mathlib.Foo", "Nat"], "axioms": []},
    ])
    report = audit_project_from_dump(dump)
    assert report["frontier"]["external_constant_count"] == 2
    assert report["frontier"]["top"][0] == {"name": "Mathlib.Foo", "used_by": 2}
    assert "## Dependency frontier" in render_markdown(report)


def test_real_mathlib_dump_numbers():
    """Regression on the shipped real Mathlib dump (Lean-computed)."""
    report = audit_project_from_dump(SET_BASIC)
    assert report["summary"]["declaration_count"] == 568
    assert report["summary"]["internal_declaration_count"] == 168
    assert report["summary"]["axiom_count"] == 0  # the two _elambda_ "axioms" are filtered
    histogram = {}
    for audit in report["declaration_audits"]:
        for axiom in audit["declared_axiom_provenance"]:
            histogram[axiom] = histogram.get(axiom, 0) + 1
    assert histogram == {"propext": 394, "Quot.sound": 387, "Classical.choice": 295}


def test_why_explains_chain_to_direct_use(tmp_path):
    records = [
        {"name": "top", "kind": "theorem", "dependencies": ["mid"], "axioms": ["propext"]},
        {"name": "mid", "kind": "theorem", "dependencies": ["leaf"], "axioms": ["propext"]},
        {"name": "leaf", "kind": "theorem", "dependencies": ["propext"], "axioms": ["propext"]},
        {"name": "clean", "kind": "theorem", "dependencies": [], "axioms": []},
    ]
    result = explain_axiom(records, "top", "propext")
    assert result["path"] == ["top", "mid", "leaf"]
    assert result["direct_use"] is True
    assert axiom_introduction_points(records, "propext") == ["leaf"]
    assert explain_axiom(records, "clean", "propext")["in_closure"] is False
    with pytest.raises(KeyError):
        explain_axiom(records, "missing", "propext")


def test_why_reports_external_entry_honestly():
    records = [
        {"name": "t", "kind": "theorem", "dependencies": ["Classical.em", "Nat"],
         "axioms": ["Classical.choice"]},
    ]
    result = explain_axiom(records, "t", "Classical.choice")
    assert result["direct_use"] is False
    assert result["external_candidates"] == ["Classical.em", "Nat"]
    assert "outside the dumped modules" in result["note"]
