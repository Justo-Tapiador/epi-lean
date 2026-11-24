import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .audit import audit_project, audit_project_from_dump
from .closure import CLOSURE_MODES
from .dump import load_dump_records
from .lake_dump import dump_project, list_project_modules
from .provenance import explain_axiom
from .providers import ProviderError, make_provider
from .report import render_json, render_markdown
from .supervisor import propose_entries, supervise_report
from .trail import AuditTrail, verify_trail

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

    audit.add_argument(
        "--include-internal",
        action="store_true",
        help=(
            "Dump/lake modes: list compiler-generated constants "
            "(_auxLemma, match_N, proof_N, eq_N, _elambda_N ...) too. "
            "By default they are excluded and the graph is contracted "
            "through them."
        ),
    )

    audit.add_argument(
        "--closure",
        choices=CLOSURE_MODES,
        default="auto",
        help=(
            "Dump/lake modes: how to report transitive dependencies: "
            "full lists, counts only, or none (auto picks by project size)."
        ),
    )

    audit.add_argument(
        "--frontier-top",
        type=int,
        default=50,
        metavar="N",
        help="Dump/lake modes: external constants to list in the frontier.",
    )

    audit.add_argument(
        "--jobs",
        type=int,
        default=1,
        metavar="N",
        help="With --lake: concurrent Lean processes (memory grows with N).",
    )

    audit.add_argument(
        "--no-cache",
        action="store_true",
        help="With --lake: ignore and do not write the dump cache.",
    )

    audit.add_argument(
        "--timeout",
        type=int,
        default=300,
        metavar="SECONDS",
        help="With --lake: per-module Lean timeout.",
    )

    why = subparsers.add_parser(
        "why",
        help="Explain which dependency chain brings an axiom into a declaration.",
    )
    why.add_argument("dump", type=Path, help="EPI-LEAN JSONL dump.")
    why.add_argument("declaration")
    why.add_argument("axiom")

    def add_ai_options(command):
        command.add_argument(
            "--provider",
            choices=("anthropic", "openai-compatible", "replay"),
            required=True,
            help="Model backend. 'replay' answers only from --cassette.",
        )
        command.add_argument("--model", help="Model identifier (required for live providers).")
        command.add_argument("--base-url", help="Endpoint for openai-compatible servers.")
        command.add_argument(
            "--cassette",
            type=Path,
            help="Record exchanges to / replay them from this file (reproducibility).",
        )
        command.add_argument(
            "--trail",
            type=Path,
            required=True,
            help="Hash-chained audit trail file (appended to).",
        )

    propose = subparsers.add_parser(
        "propose",
        help="[experimental] Ask a model to PROPOSE semantic registry entries.",
    )
    propose.add_argument("dump", type=Path, help="EPI-LEAN JSONL dump.")
    propose.add_argument("--output", type=Path, required=True, help="New registry file to write.")
    propose.add_argument("--registry", type=Path, help="Existing registry: its declarations are skipped.")
    propose.add_argument("--limit", type=int, default=20)
    propose.add_argument("--batch-size", type=int, default=5)
    add_ai_options(propose)

    supervise = subparsers.add_parser(
        "supervise",
        help="[experimental] Review a JSON audit report (deterministic checks, optional AI second review).",
    )
    supervise.add_argument("report", type=Path, help="JSON report from `epilean audit --format json`.")
    supervise.add_argument("--output", type=Path)
    supervise.add_argument("--provider", choices=("anthropic", "openai-compatible", "replay"))
    supervise.add_argument("--model")
    supervise.add_argument("--base-url")
    supervise.add_argument("--cassette", type=Path)
    supervise.add_argument("--trail", type=Path, help="Required when a provider is used.")

    verify = subparsers.add_parser(
        "verify-trail",
        help="Check the integrity of an AI audit trail.",
    )
    verify.add_argument("trail", type=Path)

    return parser


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
            include_internal=args.include_internal,
            closure_mode=args.closure,
            frontier_top=args.frontier_top,
        )

    if args.lake:
        root = args.project.resolve()

        if not root.is_dir():
            raise ValueError(
                "--lake expects a lake project directory, got: "
                f"{args.project}"
            )

        modules = args.module or list_project_modules(root)
        combined, _from_cache = dump_project(
            root,
            modules,
            jobs=args.jobs,
            use_cache=not args.no_cache,
            timeout=args.timeout,
        )
        report = audit_project_from_dump(
            combined,
            args.semantic_registry,
            include_internal=args.include_internal,
            closure_mode=args.closure,
            frontier_top=args.frontier_top,
        )
        report["project_root"] = str(root)
        return report

    return audit_project(
        args.project,
        args.semantic_registry,
    )


def _write_or_print(text: str, output: Path | None) -> None:
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def _run_why(args) -> str:
    records = load_dump_records(args.dump)
    return json.dumps(
        explain_axiom(records, args.declaration, args.axiom),
        indent=2,
        ensure_ascii=False,
    )


def _run_propose(args) -> str:
    if args.output.exists():
        raise ValueError(
            f"{args.output} already exists; proposals never overwrite a registry"
        )
    records = load_dump_records(args.dump)
    existing: set[str] = set()
    if args.registry:
        payload = json.loads(args.registry.read_text(encoding="utf-8"))
        existing = {entry["declaration"] for entry in payload.get("entries", [])}
    provider = make_provider(args.provider, args.model, args.base_url, args.cassette)
    outcome = propose_entries(
        records,
        provider,
        AuditTrail(args.trail),
        existing=existing,
        limit=args.limit,
        batch_size=args.batch_size,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(outcome["registry"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return (
        f"epilean: wrote {len(outcome['registry']['entries'])} AI proposal(s) to "
        f"{args.output} (all status=proposed, origin=ai_proposal); "
        f"{len(outcome['rejected'])} rejected. Review them before use."
    )


def _run_supervise(args) -> str:
    report = json.loads(args.report.read_text(encoding="utf-8"))
    provider = trail = None
    if args.provider:
        if not args.trail:
            raise ValueError("--trail is required when a provider is used")
        provider = make_provider(args.provider, args.model, args.base_url, args.cassette)
        trail = AuditTrail(args.trail)
    return json.dumps(
        supervise_report(report, provider, trail), indent=2, ensure_ascii=False
    )


def _run_verify_trail(args) -> tuple[str, int]:
    ok, count, error = verify_trail(args.trail)
    if ok:
        return f"trail OK: {count} event(s), chain intact", 0
    return f"trail INVALID after {count} valid event(s): {error}", 2


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "why":
            _write_or_print(_run_why(args), None)
            return 0
        if args.command == "propose":
            print(_run_propose(args))
            return 0
        if args.command == "supervise":
            _write_or_print(_run_supervise(args), args.output)
            return 0
        if args.command == "verify-trail":
            message, code = _run_verify_trail(args)
            print(message)
            return code

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

    except (OSError, ValueError, KeyError, RuntimeError, ProviderError) as error:
        print(f"epilean: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
