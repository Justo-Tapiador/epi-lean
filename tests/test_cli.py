import json
from pathlib import Path

from epilean.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_version_flag(capsys):
    try:
        exit_code = main(["--version"])
    except SystemExit as caught:  # argparse action="version"
        exit_code = caught.code
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "0.2.1" in captured.out


def test_audit_writes_markdown_report(tmp_path, capsys):
    source = """
axiom premise : True

theorem conclusion : True := premise
"""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "Main.lean").write_text(source, encoding="utf-8")

    output = tmp_path / "report.md"

    exit_code = main([
        "audit",
        str(project),
        "--format",
        "markdown",
        "--output",
        str(output),
    ])

    assert exit_code == 0
    text = output.read_text(encoding="utf-8")
    assert "# EPI-LEAN Audit Report" in text
    assert "NOT_CHECKED" in text
    assert "does not invalidate" in text
    assert "`premise`" in text
    # Nothing printed when --output is used.
    assert capsys.readouterr().out == ""


def test_audit_prints_json_to_stdout(tmp_path, capsys):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "Main.lean").write_text(
        "theorem t : True := trivial\n", encoding="utf-8"
    )

    exit_code = main([
        "audit",
        str(project),
        "--format",
        "json",
    ])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"] == "EPI-LEAN"
    assert payload["formal_verification"]["status"] == "NOT_CHECKED"
    assert payload["summary"]["declaration_count"] == 1


def test_missing_project_directory_fails(tmp_path, capsys):
    exit_code = main([
        "audit",
        str(tmp_path / "does-not-exist"),
    ])
    assert exit_code == 2
    assert "epilean: error:" in capsys.readouterr().err


def test_basic_example_end_to_end():
    exit_code = main([
        "audit",
        str(REPO_ROOT / "examples" / "basic"),
        "--semantic-registry",
        str(REPO_ROOT / "examples" / "basic" / "semantic_registry.json"),
        "--format",
        "json",
    ])
    assert exit_code == 0


def test_audit_from_dump_flag(tmp_path, capsys):
    dump = tmp_path / "dump.jsonl"
    dump.write_text(
        '{"name": "t1", "kind": "theorem", "dependencies": [], '
        '"axioms": ["propext"]}\n',
        encoding="utf-8",
    )

    exit_code = main([
        "audit",
        str(dump),
        "--dump",
        "--format",
        "json",
    ])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["extraction_mode"] == "elaborated-environment"
    assert payload["summary"]["declaration_count"] == 1
    assert payload["declaration_audits"][0]["declared_axiom_provenance"] == [
        "propext"
    ]


def test_dump_flag_with_missing_file_fails(tmp_path, capsys):
    exit_code = main([
        "audit",
        str(tmp_path / "nope.jsonl"),
        "--dump",
    ])
    assert exit_code == 2
    assert "dump file" in capsys.readouterr().err


def test_dump_and_lake_flags_are_exclusive(tmp_path, capsys):
    project = tmp_path / "proj"
    project.mkdir()
    exit_code = main([
        "audit",
        str(project),
        "--dump",
        "--lake",
    ])
    assert exit_code == 2
    assert "mutually exclusive" in capsys.readouterr().err


def test_lake_flag_without_lean_on_path_fails(tmp_path, capsys, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    # No .lake/build: fails before even looking for lean.
    exit_code = main([
        "audit",
        str(project),
        "--lake",
    ])
    assert exit_code == 2
    assert "lake build" in capsys.readouterr().err


def test_lake_flag_without_build_directory(tmp_path, capsys, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setattr(
        "epilean.lake_dump.project_lib_dir",
        lambda root: (_ for _ in ()).throw(
            FileNotFoundError(f"{root}/.lake/build/lib does not exist")
        ),
    )
    exit_code = main([
        "audit",
        str(project),
        "--lake",
    ])
    assert exit_code == 2
    assert ".lake/build/lib" in capsys.readouterr().err
