import json
from pathlib import Path

ALLOWED_STATUSES = {
    "proposed",
    "under_review",
    "reviewed",
}


def load_semantic_registry(
    path: Path | None,
    declaration_names: set[str],
) -> tuple[list[dict], list[str]]:
    """Load and validate a semantic registry.

    Returns (entries, warnings). Warnings are non-fatal: an invalid entry
    is skipped and reported rather than aborting the whole audit.
    """
    if path is None:
        return [], []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Cannot read semantic registry {path}: {error}"
        ) from error

    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("entries"), list)
    ):
        # The audit pipeline's error contract is ValueError.
        raise ValueError(  # noqa: TRY004
            "Semantic registry must contain an 'entries' array."
        )

    entries = []
    warnings = []
    seen_declarations: dict[str, int] = {}

    for index, entry in enumerate(payload["entries"]):
        if not isinstance(entry, dict):
            warnings.append(
                f"Semantic entry {index} is not an object and was skipped."
            )
            continue

        required = {"declaration", "interpretation", "status"}
        missing = required - entry.keys()

        if missing:
            warnings.append(
                f"Semantic entry {index} is missing: "
                f"{', '.join(sorted(missing))}."
            )
            continue

        empty_or_invalid = [
            key
            for key in required
            if not isinstance(entry[key], str) or not entry[key].strip()
        ]

        if empty_or_invalid:
            warnings.append(
                f"Semantic entry {index} has an empty or non-string "
                f"required field ({', '.join(sorted(empty_or_invalid))}) "
                "and was skipped."
            )
            continue

        if entry["status"] not in ALLOWED_STATUSES:
            warnings.append(
                f"Semantic entry {index} has an invalid status "
                f"'{entry['status']}' and was skipped."
            )
            continue

        declaration = entry["declaration"]

        if declaration in seen_declarations:
            warnings.append(
                f"Semantic entry {index} duplicates the declaration "
                f"'{declaration}' (first seen at entry "
                f"{seen_declarations[declaration]}); only the first entry "
                "was kept."
            )
            continue

        if (
            entry["status"] == "reviewed"
            and not entry.get("evidence", "").strip()
        ):
            warnings.append(
                f"Semantic entry {index} ('{declaration}') is marked "
                "'reviewed' but supplies no evidence; the status was "
                "downgraded to 'under_review'."
            )
            entry = {**entry, "status": "under_review"}

        if (
            entry.get("origin") == "ai_proposal"
            and entry["status"] == "reviewed"
        ):
            warnings.append(
                f"Semantic entry {index} ('{declaration}') is an AI "
                "proposal marked 'reviewed'; AI proposals must never be "
                "auto-reviewed. The status was downgraded to "
                "'under_review'."
            )
            entry = {**entry, "status": "under_review"}

        if declaration not in declaration_names:
            warnings.append(
                f"Semantic entry {index} refers to unknown declaration "
                f"'{declaration}'."
            )

        seen_declarations[declaration] = index
        entries.append(entry)

    return entries, warnings
