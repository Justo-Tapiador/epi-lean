"""Tests for dump-based audits and large-report rendering."""

import json
from pathlib import Path

import pytest

from epilean.audit import audit_project_from_dump
from epilean.report import (
    LARGE_REPORT_THRESHOLD,
    render_markdown,
)


def _write_dump(path: Path, records: list[dict]) -> Path:
    with open(path, "w", encoding="utf-8") as handle:
        handle.writelines(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    return path


@pytest.fixture()
def tricky_dump(tmp_path: Path) -> Path:
    """Mirror of examples/lake-project (elaborated dump)."""
    return _write_dump(tmp_path / "dump.jsonl", [
        {
            "name": "théorème",
            "kind": "theorem",
            "dependencies": ["secret_axiom", "Nat", "Eq"],
            "axioms": ["secret_axiom"],
        },
        {
            "name": "secret_axiom",
            "kind": "axiom",
            "dependencies": ["Nat", "Eq"],
            "axioms": ["secret_axiom"],
        },
        {
            "name": "Inner.helper",
            "kind": "def",
            "dependencies": ["Nat"],
            "axioms": [],
        },
        {
            "name": "Outer.helper",
            "kind": "def",
            "dependencies": ["Bool"],
            "axioms": [],
        },
        {
            "name": "classical_use",
            "kind": "theorem",
            "dependencies": ["Classical.em"],
            "axioms": ["Classical.choice", "propext", "Quot.sound"],
        },
    ])


def test_audit_from_dump_reports_exact_provenance(tricky_dump: Path):
    report = audit_project_from_dump(tricky_dump)

    assert report["extraction_mode"] == "elaborated-environment"
    assert report["summary"]["declaration_count"] == 5
    assert report["summary"]["axiom_count"] == 1

    by_name = {
        audit["name"]: audit
        for audit in report["declaration_audits"]
    }

    # The axiom's own provenance is itself; the theorem's closure came
    # straight from the dump line (Lean-computed at dump time).
    assert by_name["secret_axiom"]["declared_axiom_provenance"] == [
        "secret_axiom"
    ]
    assert by_name["théorème"]["declared_axiom_provenance"] == [
        "secret_axiom"
    ]
    assert by_name["classical_use"]["declared_axiom_provenance"] == [
        "Classical.choice",
        "Quot.sound",
        "propext",
    ]
    assert by_name["Inner.helper"]["declared_axiom_provenance"] == []

    # Exact dependencies from the elaborated environment: no heuristic
    # name matching involved.
    assert set(by_name["théorème"]["dependencies"]) == {
        "Eq",
        "Nat",
        "secret_axiom",
    }


def test_audit_from_dump_namespaces_distinct(tricky_dump: Path):
    """Two helpers in different namespaces stay distinct in dump mode."""
    report = audit_project_from_dump(tricky_dump)
    names = [d["name"] for d in report["declarations"]]
    assert names.count("Inner.helper") == 1
    assert names.count("Outer.helper") == 1


def test_audit_from_dump_missing_file(tmp_path: Path):
    with pytest.raises(ValueError, match="not a file"):
        audit_project_from_dump(tmp_path / "nope.jsonl")


def test_audit_from_dump_all_insufficient_evidence(tricky_dump: Path):
    """Without a semantic registry every declaration is INSUFFICIENT_EVIDENCE."""
    report = audit_project_from_dump(tricky_dump)
    assert report["epistemic_summary"]["INSUFFICIENT_EVIDENCE"] == 5


def test_audit_from_dump_with_registry(tricky_dump: Path, tmp_path: Path):
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps({
            "registry_version": "0.1.0",
            "entries": [
                {
                    "declaration": "théorème",
                    "interpretation": "n + 0 = n + 0",
                    "status": "reviewed",
                    "evidence": "Checked against Lean's Nat.add_zero.",
                    "references": [],
                    "origin": "human",
                },
            ],
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    report = audit_project_from_dump(tricky_dump, registry)
    assert report["epistemic_summary"]["SEMANTICALLY_SUPPORTED"] == 1
    assert report["epistemic_summary"]["INSUFFICIENT_EVIDENCE"] == 4


def test_elaborated_warnings_present(tricky_dump: Path):
    report = audit_project_from_dump(tricky_dump)
    joined = " ".join(report["warnings"])
    assert "elaborated Lean environment" in joined
    assert "collectAxioms" in joined
    # Non-interference still applies.
    assert report["formal_verification"]["status"] == "NOT_CHECKED"


def test_markdown_axiom_histogram(tricky_dump: Path):
    report = audit_project_from_dump(tricky_dump)
    markdown = render_markdown(report)

    assert "## Axiom provenance histogram" in markdown
    assert "`propext` | 1" in markdown
    assert "`Classical.choice` | 1" in markdown
    assert "`secret_axiom` | 2" in markdown


def test_markdown_extraction_mode_line(tricky_dump: Path):
    report = audit_project_from_dump(tricky_dump)
    markdown = render_markdown(report)
    assert "Extraction mode: `elaborated-environment`" in markdown


def _big_dump(tmp_path: Path, count: int) -> Path:
    records = [
        {
            "name": f"decl_{index}",
            "kind": "theorem",
            "dependencies": [],
            "axioms": ["propext"],
        }
        for index in range(count)
    ]
    return _write_dump(tmp_path / "big.jsonl", records)


def test_markdown_truncates_large_reports(tmp_path: Path):
    dump = _big_dump(tmp_path, LARGE_REPORT_THRESHOLD + 40)
    report = audit_project_from_dump(dump)
    markdown = render_markdown(report)

    assert "more declarations omitted" in markdown
    # Head and tail survive.
    assert "`decl_0`" in markdown
    assert f"`decl_{LARGE_REPORT_THRESHOLD + 39}`" in markdown


def test_markdown_no_truncation_below_threshold(tmp_path: Path):
    dump = _big_dump(tmp_path, LARGE_REPORT_THRESHOLD)
    report = audit_project_from_dump(dump)
    markdown = render_markdown(report)

    assert "more declarations omitted" not in markdown
    assert markdown.count("| `decl_") == LARGE_REPORT_THRESHOLD


def test_json_report_never_truncates(tmp_path: Path):
    count = LARGE_REPORT_THRESHOLD + 10
    dump = _big_dump(tmp_path, count)
    report = audit_project_from_dump(dump)

    assert report["summary"]["declaration_count"] == count
    assert len(report["declaration_audits"]) == count
