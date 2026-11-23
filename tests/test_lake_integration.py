"""End-to-end integration test: lake project -> dump -> audit.

Runs only when a Lean toolchain is available on PATH and the example
project ships prebuilt .olean files; otherwise the test is skipped
with an explicit reason (CI machines without Lean still get the rest
of the suite).
"""

import json
import shutil
from pathlib import Path

import pytest

from epilean.audit import audit_project_from_dump
from epilean.cli import main
from epilean.lake_dump import (
    dump_module,
    find_epidump,
    find_lean_binary,
    list_project_modules,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
LAKE_PROJECT = REPO_ROOT / "examples" / "lake-project"

# Declarations the tricky example must yield in elaborated mode:
# these are exactly the cases that break the source-level regex
# extractor (guillemet names, anonymous instances, namespace
# collisions), which is the point of this example.
EXPECTED_NAMES = {
    "théorème",
    "secret_axiom",
    "Inner.helper",
    "Outer.helper",
    "classical_use",
    "tête",
    "instCos",
    "Inner.helper_pos",
}

LEAN_BINARY = shutil.which("lean")
HAS_OLEANS = (
    LAKE_PROJECT / ".lake" / "build" / "lib" / "EpiTest" / "Test.olean"
).exists()

pytestmark = pytest.mark.skipif(
    not LEAN_BINARY or not HAS_OLEANS,
    reason=(
        "requires a Lean toolchain on PATH and the example project's "
        "prebuilt .olean files (run `lake build` in "
        "examples/lake-project)"
    ),
)


def test_find_lean_binary():
    assert find_lean_binary() == LEAN_BINARY


def test_find_epidump():
    epidump = find_epidump()
    assert epidump.name == "EpiDump.lean"
    assert epidump.exists()


def test_list_project_modules():
    modules = list_project_modules(LAKE_PROJECT)
    assert "EpiTest.Test" in modules


def test_dump_module_exact_contents(tmp_path: Path):
    dump_path = tmp_path / "dump.jsonl"
    dump_module(LAKE_PROJECT, "EpiTest.Test", dump_path)

    lines = [
        json.loads(line)
        for line in dump_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    names = {record["name"] for record in lines}
    assert EXPECTED_NAMES <= names

    by_name = {record["name"]: record for record in lines}

    # Exact axiom provenance, computed by Lean's collectAxioms.
    assert by_name["théorème"]["axioms"] == ["secret_axiom"]
    assert sorted(by_name["classical_use"]["axioms"]) == [
        "Classical.choice",
        "Quot.sound",
        "propext",
    ]
    assert by_name["Inner.helper"]["axioms"] == []
    assert by_name["secret_axiom"]["kind"] == "axiom"

    # The proof term's own references appear in dependencies (the
    # source-level extractor cannot see proof-term references).
    assert "secret_axiom" in by_name["théorème"]["dependencies"]


def test_audit_from_real_dump(tmp_path: Path):
    dump_path = tmp_path / "dump.jsonl"
    dump_module(LAKE_PROJECT, "EpiTest.Test", dump_path)

    report = audit_project_from_dump(dump_path)

    assert report["extraction_mode"] == "elaborated-environment"
    assert report["summary"]["declaration_count"] == 9
    assert report["summary"]["axiom_count"] == 1

    by_name = {
        audit["name"]: audit
        for audit in report["declaration_audits"]
    }
    assert by_name["théorème"]["declared_axiom_provenance"] == [
        "secret_axiom"
    ]
    assert by_name["classical_use"]["declared_axiom_provenance"] == [
        "Classical.choice",
        "Quot.sound",
        "propext",
    ]


def test_cli_lake_mode_end_to_end(capsys):
    exit_code = main([
        "audit",
        str(LAKE_PROJECT),
        "--lake",
        "--format",
        "json",
    ])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["extraction_mode"] == "elaborated-environment"
    assert payload["project_root"] == str(LAKE_PROJECT)
    names = {d["name"] for d in payload["declarations"]}
    assert EXPECTED_NAMES <= names
    assert payload["summary"]["declaration_count"] == 9


def test_source_mode_misses_what_elaborated_mode_finds(capsys):
    """The negative control: on this tricky project the source-level
    heuristic extractor cannot recover the guillemet names or the two
    namespace-distinct helpers — the reason elaborated mode exists."""
    exit_code = main([
        "audit",
        str(LAKE_PROJECT / "EpiTest"),
        "--format",
        "json",
    ])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    source_names = {d["name"] for d in payload["declarations"]}

    # Guillemet names are lost by the identifier regex.
    assert "théorème" not in source_names
    assert "tête" not in source_names
    # Namespace-suffixed names appear without their namespace.
    assert "Inner.helper" not in source_names


def test_mathlib_scale_markdown_handles_large_reports():
    """Rendering mathlib-scale declaration counts does not blow up."""
    from epilean.report import render_markdown

    fake_audits = [
        {
            "name": f"Mathlib.thm_{index}",
            "kind": "theorem",
            "dependencies": [],
            "transitive_dependencies": [],
            "declared_axiom_provenance": ["propext"],
        }
        for index in range(2000)
    ]

    report = {
        "tool": "EPI-LEAN",
        "version": "test",
        "project_root": "/mathlib",
        "extraction_mode": "elaborated-environment",
        "formal_verification": {
            "system": "Lean",
            "status": "NOT_CHECKED",
            "non_interference": "note",
        },
        "declarations": [],
        "declaration_audits": fake_audits,
        "semantic_entries": [],
        "epistemic_assessments": [],
        "epistemic_summary": {},
        "warnings": [],
        "summary": {
            "declaration_count": 2000,
            "axiom_count": 0,
            "semantic_entry_count": 0,
            "reviewed_semantic_entry_count": 0,
        },
    }

    markdown = render_markdown(report)
    assert "2000" in markdown
    assert "more declarations omitted" in markdown
    assert markdown.count("Mathlib.thm_") <= 60
