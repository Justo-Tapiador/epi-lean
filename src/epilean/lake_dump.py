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

import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
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


def merge_dumps(dump_paths: list[Path], combined: Path) -> Path:
    """Concatenate module dumps into one combined dump file.

    Later duplicates of a name win (a re-defined name in a later module
    shadows the earlier one); first-appearance order is preserved.
    """
    seen: dict[str, dict] = {}
    ordered: list[str] = []

    for dump_path in dump_paths:
        with open(dump_path, encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                record = json.loads(stripped)
                if record["name"] not in seen:
                    ordered.append(record["name"])
                seen[record["name"]] = record

    with open(combined, "w", encoding="utf-8") as handle:
        handle.writelines(
            json.dumps(seen[name], ensure_ascii=False) + "\n" for name in ordered
        )

    return combined


def lean_version(lean_binary: str) -> str:
    """Output of `lean --version` (part of the cache fingerprint)."""
    completed = subprocess.run(
        [lean_binary, "--version"],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    return completed.stdout.strip()


def project_fingerprint(
    project_root: Path,
    modules: list[str],
    lean_binary: str,
    epidump_path: Path,
) -> str:
    """Hash that changes whenever any input of a dump can change.

    Covers: the Lean version, the dump metaprogram, the requested module
    list, and the content of *every* .olean under the project's build
    directory (a module's dump depends on its imports, so the safe,
    stale-free granularity is project-level; per-module invalidation
    would need the import graph and is left for later).
    """
    digest = hashlib.sha256()
    digest.update(lean_version(lean_binary).encode())
    digest.update(b"\0")
    digest.update(Path(epidump_path).read_bytes())
    digest.update(b"\0")
    digest.update("\n".join(sorted(modules)).encode())
    lib = project_lib_dir(project_root.resolve())
    for olean in sorted(lib.rglob("*.olean")):
        digest.update(olean.relative_to(lib).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(olean.read_bytes()).digest())
    return digest.hexdigest()


def dump_project(
    project_root: Path,
    modules: list[str],
    jobs: int = 1,
    use_cache: bool = True,
    timeout: int = 300,
    lean_binary: str | None = None,
    epidump_path: Path | None = None,
) -> tuple[Path, bool]:
    """Dump several modules (in parallel) into one combined dump.

    Returns ``(combined_path, from_cache)``. With ``use_cache`` the
    combined dump is stored under ``.lake/epilean-cache/`` keyed by
    ``project_fingerprint``; an unchanged project is not re-dumped (the
    common edit-the-registry/re-audit loop costs no Lean runs).
    ``jobs`` bounds concurrent Lean processes (each one loads the
    module's imports, so memory grows with ``jobs``).
    """
    root = project_root.resolve()
    lean = lean_binary or find_lean_binary()
    epidump = epidump_path or find_epidump()
    jobs = max(1, jobs)

    cache_dir = root / ".lake" / "epilean-cache"
    cached: Path | None = None
    if use_cache:
        key = project_fingerprint(root, modules, lean, epidump)
        cached = cache_dir / f"{key}.jsonl"
        if cached.is_file() and cached.stat().st_size > 0:
            return cached, True

    work = root / ".lake"
    work.mkdir(parents=True, exist_ok=True)

    def run(item: tuple[int, str]) -> Path:
        index, module = item
        out = work / f"epilean-dump-{index}.jsonl"
        return dump_module(
            root,
            module,
            out,
            lean_binary=lean,
            epidump_path=epidump,
            timeout=timeout,
        )

    items = list(enumerate(modules))
    if jobs == 1 or len(items) == 1:
        dump_paths = [run(item) for item in items]
    else:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            dump_paths = list(pool.map(run, items))  # preserves module order

    combined = work / "epilean-dump-combined.jsonl"
    merge_dumps(dump_paths, combined)

    if use_cache and cached is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(".tmp")
        shutil.copyfile(combined, tmp)
        os.replace(tmp, cached)  # atomic: never a half-written cache entry
        return cached, False

    return combined, False
