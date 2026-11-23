import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .audit import audit_project, audit_project_from_dump
from .lake_dump import dump_module, list_project_modules
from .report import render_json, render_markdown

DUMP_SUFFIX = ".jsonl"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="epilean",
        description=(
            "EPI-LEAN: audit the epistemic structure of Lean projects "
            "at source level (heuristic) or from an elaborated-environment "
            "dump (exact; see --dump and --lake)."
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    audit = subparsers.add_parser(
        "audit",
        help="Run a source-level or dump-based epistemic audit.",
    )

    audit.add_argument(
        "project",
        type=Path,
        help=(
            "Directory containing Lean source files (source mode), a "
            "lake project with a .lake/build directory (--lake), or a "
            "JSONL dump file (--dump)."
        ),
    )

    audit.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
    )

    audit.add_argument(
        "--output",
        type=Path,
        help="Write the report to a file.",
    )

    audit.add_argument(
        "--semantic-registry",
        type=Path,
        help="Optional semantic registry JSON.",
    )

    audit.add_argument(
        "--dump",
        action="store_true",
        help=(
            "Treat PROJECT as an EPI-LEAN JSONL environment dump "
            "(produced by tools/EpiDump.lean) and audit from it: "
            "exact declarations, dependencies, and axiom provenance "
            "computed by Lean itself."
        ),
    )

    audit.add_argument(
        "--lake",
        action="store_true",
        help=(
            "Treat PROJECT as a compiled lake project: find its "
            ".olean modules under .lake/build/lib, run the EPI-LEAN "
            "dump metaprogram on each, and audit the combined result. "
            "Requires `lean` on PATH and a prior `lake build`."
        ),
    )

    audit.add_argument(
        "--module",
        action="append",
        default=None,
        metavar="MODULE",
        help=(
            "With --lake: audit only these module names (e.g. "
            "MyProject.Basic). May be given multiple times; default is "
            "every module found in .lake/build/lib."
        ),
    )

    return parser


def _merge_dumps(dump_paths: list[Path]) -> Path:
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

    combined = dump_paths[0].parent / "epilean-dump-combined.jsonl"
    with open(combined, "w", encoding="utf-8") as handle:
        handle.writelines(json.dumps(seen[name], ensure_ascii=False) + "\n" for name in ordered)

    return combined


def _run_audit(args) -> dict:
    if args.dump and args.lake:
        raise ValueError("--dump and --lake are mutually exclusive")

    if args.dump:
        if not args.project.is_file():
            raise ValueError(
                f"--dump expects a JSONL dump file, got: {args.project}"
            )
        return audit_project_from_dump(
            args.project,
            args.semantic_registry,
        )

    if args.lake:
        root = args.project.resolve()

        if not root.is_dir():
            raise ValueError(
                "--lake expects a lake project directory, got: "
                f"{args.project}"
            )

        modules = args.module or list_project_modules(root)
        dump_paths = []

        for index, module in enumerate(modules):
            dump_path = root / ".lake" / f"epilean-dump-{index}.jsonl"
            dump_module(root, module, dump_path)
            dump_paths.append(dump_path)

        combined = _merge_dumps(dump_paths)
        report = audit_project_from_dump(
            combined,
            args.semantic_registry,
        )
        report["project_root"] = str(root)
        return report

    return audit_project(
        args.project,
        args.semantic_registry,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        report = _run_audit(args)

        if args.format == "json":
            rendered = render_json(report)
        else:
            rendered = render_markdown(report)

        if args.output:
            args.output.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            args.output.write_text(
                rendered + "\n",
                encoding="utf-8",
            )
        else:
            print(rendered)

        return 0

    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"epilean: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
