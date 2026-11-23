import re
from pathlib import Path

from .models import Declaration

# Optional modifiers that may precede a declaration keyword.
MODIFIERS = (
    "private",
    "protected",
    "noncomputable",
    "partial",
    "unsafe",
)

DECLARATION_RE = re.compile(
    r"(?m)^[ \t]*"
    r"(?:@\[[^\]]*\][ \t]*\n?[ \t]*)*"
    r"(?:(?:" + "|".join(MODIFIERS) + r")\s+)*"
    r"(theorem|lemma|def|abbrev|axiom|opaque|structure|inductive|class|instance)\s+"
    r"([A-Za-z_][A-Za-z0-9_'.]*)"
)


def strip_comments(source: str) -> str:
    """Remove line and nested block comments, preserving line positions."""
    output = list(source)
    index = 0
    depth = 0
    in_string = False

    while index < len(source):
        if (
            depth == 0
            and not in_string
            and source.startswith("--", index)
        ):
            end = source.find("\n", index)
            if end == -1:
                end = len(source)
            for position in range(index, end):
                output[position] = " "
            index = end
            continue

        if not in_string and source.startswith("/-", index):
            depth += 1
            output[index] = output[index + 1] = " "
            index += 2
            continue

        if depth and source.startswith("-/", index):
            depth -= 1
            output[index] = output[index + 1] = " "
            index += 2
            continue

        if depth:
            if source[index] != "\n":
                output[index] = " "
            index += 1
            continue

        if source[index] == '"' and (
            index == 0 or source[index - 1] != "\\"
        ):
            in_string = not in_string

        index += 1

    return "".join(output)


def _declaration_body(
    item: dict,
    raw: list[dict],
) -> str:
    """Source region of a declaration: from its header to the next header."""
    later_starts = [
        other["start"]
        for other in raw
        if other["file"] == item["file"]
        and other["start"] > item["start"]
    ]
    end = min(later_starts) if later_starts else len(item["cleaned"])
    return item["cleaned"][item["start"]:end]


def extract_declarations(project_root: Path) -> list[Declaration]:
    """Extract declaration headers and approximate intra-project references."""
    root = project_root.resolve()
    raw = []

    for path in sorted(root.rglob("*.lean")):
        original = path.read_text(encoding="utf-8")
        cleaned = strip_comments(original)

        for match in DECLARATION_RE.finditer(cleaned):
            kind, name = match.groups()
            line = cleaned.count("\n", 0, match.start()) + 1
            raw.append({
                "name": name,
                "kind": kind,
                "file": path.relative_to(root).as_posix(),
                "line": line,
                "cleaned": cleaned,
                "start": match.start(),
            })

    known_names = {item["name"] for item in raw}
    declarations = []

    for item in raw:
        body = _declaration_body(item, raw)

        dependencies = []
        for candidate in known_names:
            if candidate == item["name"]:
                continue

            pattern = (
                r"(?<![A-Za-z0-9_'])"
                + re.escape(candidate)
                + r"(?![A-Za-z0-9_'])"
            )
            if re.search(pattern, body):
                dependencies.append(candidate)

        declarations.append(
            Declaration(
                name=item["name"],
                kind=item["kind"],
                file=item["file"],
                line=item["line"],
                source=body[:1000].strip(),
                dependencies=tuple(sorted(set(dependencies))),
            )
        )

    return declarations
