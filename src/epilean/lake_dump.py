"""Run the Lean-side environment dump for a lake project.

This module knows how to execute ``tools/EpiDump.lean`` against a
compiled lake project and produce a JSONL dump of the elaborated
environment, without EPI-LEAN reimplementing any Lean internals.

Two levels of integration:

* ``dump_module``: the caller (the CLI) arranges for the toolchain and
  the project's build outputs; this function only shells out to Lean.
* discovery of the ``lean``/``lake`` binaries and of the project's
  ``.lake/build/lib`` directory lives here as well, with explicit
  errors when anything is missing.
"""

import shutil
import subprocess
import sys
from pathlib import Path

# Relative location of the dump metaprogram inside the epi-lean repo.
EPIDUMP_RELPATH = Path("tools") / "EpiDump.lean"

# Location of the dump script when the repo is not available (installed
# package): tools/ is packaged as data in pyproject (see [tool.]).
def find_epidump() -> Path:
    """Locate tools/EpiDump.lean shipped with this EPI-LEAN install."""
    # 1. Adjacent to the package (repo checkout or zip layout).
    here = Path(__file__).resolve().parent
    candidate = here.parent.parent / EPIDUMP_RELPATH
    if candidate.exists():
        return candidate
    # 2. Site-packages data layout.
    candidate = here / "tools" / "EpiDump.lean"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        "tools/EpiDump.lean not found next to the epilean package; "
        "run from a full EPI-LEAN checkout"
    )


def find_lean_binary() -> str:
    """Return the path of a usable `lean` binary, or raise."""
    for candidate in ("lean",):
        found = shutil.which(candidate)
        if found:
            return found
    raise FileNotFoundError(
        "no `lean` binary on PATH; install a Lean toolchain "
        "(e.g. elan) and retry"
    )


def project_lib_dir(project_root: Path) -> Path:
    """The project's compiled library directory (.lake/build/lib)."""
    lib = project_root / ".lake" / "build" / "lib"
    if not lib.is_dir():
        raise FileNotFoundError(
            f"{lib} does not exist; run `lake build` first"
        )
    return lib


def list_project_modules(project_root: Path) -> list[str]:
    """Module names (Foo.Bar) compiled under .lake/build/lib."""
    lib = project_lib_dir(project_root)
    modules = []

    for olean in sorted(lib.rglob("*.olean")):
        relative = olean.relative_to(lib).with_suffix("")
        modules.append(relative.as_posix().replace("/", "."))

    if not modules:
        raise FileNotFoundError(
            f"no .olean files under {lib}; run `lake build` first"
        )

    return modules


def dump_module(
    project_root: Path,
    module: str,
    output_path: Path,
    lean_binary: str | None = None,
    epidump_path: Path | None = None,
    lean_path: str | None = None,
    timeout: int = 300,
) -> Path:
    """Dump one module of a compiled lake project to JSONL.

    ``lean_binary`` and ``epidump_path`` default to discovery; pass
    ``lean_path`` to prepend extra LEAN_PATH entries (e.g. a toolchain
    lib dir for projects needing extra imports).
    """
    root = project_root.resolve()
    lib = project_lib_dir(root)

    lean = lean_binary or find_lean_binary()
    epidump = epidump_path or find_epidump()

    lean_path_value = str(lib)
    if lean_path:
        lean_path_value = f"{lean_path}:{lib}"

    command = [
        lean,
        "--run",
        str(epidump),
        "--",
        str(output_path),
        module,
    ]

    environment = {"LEAN_PATH": lean_path_value}

    completed = subprocess.run(
        command,
        cwd=root,
        env={**dict(__import__("os").environ), **environment},
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        raise RuntimeError(
            f"lean --run failed (exit {completed.returncode}) for module "
            f"{module}: {completed.stderr.strip()[:500]}"
        )

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(
            f"dump for module {module} produced no output at "
            f"{output_path}"
        )

    return output_path
