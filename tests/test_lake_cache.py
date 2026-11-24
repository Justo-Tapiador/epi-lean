"""Parallel dumping and project-level cache, using a fake `lean` binary
so the logic is tested on machines without a Lean toolchain."""

import json
import os
import stat
from pathlib import Path

import pytest

from epilean.cli import main
from epilean.lake_dump import dump_project, project_fingerprint

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="the fake `lean` is a POSIX executable script"
)

FAKE_LEAN = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args == ["--version"]:
    print("Lean (version 0.0.0-fake)")
    sys.exit(0)
# lean --run EpiDump.lean -- <out> <module>
out, module = args[-2], args[-1]
with open(os.environ["FAKE_LEAN_LOG"], "a") as log:
    log.write(module + "\\n")
record = {"name": module + ".thm", "kind": "theorem",
          "dependencies": [], "axioms": ["propext"]}
with open(out, "w") as handle:
    handle.write(json.dumps(record) + "\\n")
"""


@pytest.fixture()
def project(tmp_path: Path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    lean = bindir / "lean"
    lean.write_text(FAKE_LEAN)
    lean.chmod(lean.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "lean.log"
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_LEAN_LOG", str(log))
    root = tmp_path / "proj"
    lib = root / ".lake" / "build" / "lib"
    lib.mkdir(parents=True)
    for module in ("A", "B", "C"):
        (lib / f"{module}.olean").write_bytes(f"olean-{module}".encode())
    return root, log


def _runs(log: Path) -> list[str]:
    return log.read_text().split() if log.exists() else []


def test_parallel_dump_merges_in_module_order(project):
    root, log = project
    combined, from_cache = dump_project(root, ["A", "B", "C"], jobs=3)
    assert from_cache is False
    assert sorted(_runs(log)) == ["A", "B", "C"]
    names = [json.loads(line)["name"] for line in combined.read_text().splitlines()]
    assert names == ["A.thm", "B.thm", "C.thm"]  # module order, whatever finished first


def test_cache_hit_runs_no_lean(project):
    root, log = project
    dump_project(root, ["A", "B"], jobs=2)
    before = len(_runs(log))
    combined, from_cache = dump_project(root, ["A", "B"], jobs=2)
    assert from_cache is True
    assert len(_runs(log)) == before
    assert combined.parent.name == "epilean-cache"


def test_changed_olean_invalidates_cache(project):
    root, log = project
    dump_project(root, ["A"])
    (root / ".lake" / "build" / "lib" / "A.olean").write_bytes(b"changed")
    _, from_cache = dump_project(root, ["A"])
    assert from_cache is False
    assert len(_runs(log)) == 2


def test_different_module_selection_has_different_key(project):
    root, _ = project
    from epilean.lake_dump import find_epidump, find_lean_binary

    lean, epidump = find_lean_binary(), find_epidump()
    assert project_fingerprint(root, ["A"], lean, epidump) != project_fingerprint(
        root, ["A", "B"], lean, epidump
    )


def test_no_cache_flag_always_redumps(project):
    root, log = project
    dump_project(root, ["A"], use_cache=False)
    dump_project(root, ["A"], use_cache=False)
    assert len(_runs(log)) == 2
    assert not (root / ".lake" / "epilean-cache").exists()


def test_cli_lake_mode_with_jobs_and_cache(project, tmp_path, capsys):
    root, log = project
    out = tmp_path / "report.json"
    argv = ["audit", str(root), "--lake", "--jobs", "2", "--format", "json", "--output", str(out)]
    assert main(argv) == 0
    report = json.loads(out.read_text())
    assert {d["name"] for d in report["declarations"]} == {"A.thm", "B.thm", "C.thm"}
    runs = len(_runs(log))
    assert main(argv) == 0  # second audit: served from cache
    assert len(_runs(log)) == runs
