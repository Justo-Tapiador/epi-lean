"""Tests for the elaborated-environment dump loader."""

import json
from pathlib import Path

import pytest

from epilean.dump import (
    DumpFormatError,
    axiom_provenance_from_dump,
    load_dump,
)


def _write_dump(path: Path, records: list[dict]) -> Path:
    with open(path, "w", encoding="utf-8") as handle:
        handle.writelines(json.dumps(record) + "\n" for record in records)
    return path


@pytest.fixture()
def small_dump(tmp_path: Path) -> Path:
    return _write_dump(tmp_path / "dump.jsonl", [
        {
            "name": "ax",
            "kind": "axiom",
            "dependencies": [],
            "axioms": ["ax"],
        },
        {
            "name": "thm",
            "kind": "theorem",
            "dependencies": ["ax", "Nat"],
            "axioms": ["ax", "propext"],
        },
        {
            "name": "def1",
            "kind": "def",
            "dependencies": [],
            "axioms": [],
        },
    ])


def test_load_dump_basic(small_dump: Path):
    declarations = load_dump(small_dump)

    assert [d.name for d in declarations] == ["ax", "thm", "def1"]
    assert declarations[0].kind == "axiom"
    assert declarations[1].dependencies == ("Nat", "ax")
    assert declarations[1].file == ""
    assert declarations[1].line == 0
    assert declarations[1].source == ""


def test_load_dump_skips_blank_lines(tmp_path: Path):
    path = tmp_path / "dump.jsonl"
    path.write_text(
        '{"name": "a", "kind": "def", "dependencies": [], "axioms": []}\n'
        "\n"
        '   {"name": "b", "kind": "theorem", "dependencies": [], "axioms": []}\n',
        encoding="utf-8",
    )
    declarations = load_dump(path)
    assert [d.name for d in declarations] == ["a", "b"]


def test_load_dump_rejects_bad_json(tmp_path: Path):
    path = tmp_path / "dump.jsonl"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(DumpFormatError, match="invalid JSON"):
        load_dump(path)


def test_load_dump_rejects_missing_field(tmp_path: Path):
    path = _write_dump(tmp_path / "dump.jsonl", [
        {"name": "a", "dependencies": []},
    ])

    with pytest.raises(DumpFormatError, match="missing field"):
        load_dump(path)


def test_load_dump_rejects_unknown_kind(tmp_path: Path):
    path = _write_dump(tmp_path / "dump.jsonl", [
        {"name": "a", "kind": "mystery", "dependencies": [], "axioms": []},
    ])

    with pytest.raises(DumpFormatError, match="unknown kind"):
        load_dump(path)


def test_load_dump_rejects_bad_dependencies(tmp_path: Path):
    path = _write_dump(tmp_path / "dump.jsonl", [
        {"name": "a", "kind": "def", "dependencies": "not-a-list", "axioms": []},
    ])

    with pytest.raises(DumpFormatError, match="dependencies"):
        load_dump(path)


def test_load_dump_rejects_empty_file(tmp_path: Path):
    path = tmp_path / "dump.jsonl"
    path.write_text("", encoding="utf-8")

    with pytest.raises(DumpFormatError, match="no declarations"):
        load_dump(path)


def test_load_dump_missing_axioms_defaults_to_empty(tmp_path: Path):
    path = _write_dump(tmp_path / "dump.jsonl", [
        {"name": "a", "kind": "def", "dependencies": []},
    ])
    # "axioms" absent: allowed (not computed for this kind).
    declarations = load_dump(path)
    assert len(declarations) == 1


def test_axiom_provenance_from_dump():
    class Fake:
        pass

    from epilean.models import Declaration

    axiom = Declaration(
        name="ax", kind="axiom", file="", line=0, source=""
    )
    thm = Declaration(
        name="thm", kind="theorem", file="", line=0, source=""
    )

    mapping = {"thm": ["propext", "Classical.choice"]}

    assert axiom_provenance_from_dump(axiom, mapping) == ["ax"]
    assert axiom_provenance_from_dump(thm, mapping) == [
        "Classical.choice",
        "propext",
    ]
    assert axiom_provenance_from_dump(axiom, {}) == ["ax"]
    assert axiom_provenance_from_dump(thm, {}) == []


def test_dump_supports_unicode_names(tmp_path: Path):
    path = _write_dump(tmp_path / "dump.jsonl", [
        {
            "name": "«théorème»",
            "kind": "theorem",
            "dependencies": [],
            "axioms": [],
        },
    ])
    declarations = load_dump(path)
    assert declarations[0].name == "«théorème»"
