"""Epistemic assessment of declarations.

This module implements the *non-interference principle* discussed for
EPI-LEAN: EPI-LEAN never invalidates, modifies, overrides, or replaces
the formal verification status established by Lean. Its assessments are
complementary epistemic evaluations and must remain explicitly
distinguishable from formal proof validity.
"""

# Epistemic assessment statuses (deliberately distinct from Lean's
# formal verification, so they can never be confused with it).
SEMANTICALLY_SUPPORTED = "SEMANTICALLY_SUPPORTED"
POTENTIAL_MISMATCH = "POTENTIAL_MISMATCH"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

ALL_STATUSES = (
    SEMANTICALLY_SUPPORTED,
    POTENTIAL_MISMATCH,
    REVIEW_REQUIRED,
    INSUFFICIENT_EVIDENCE,
)

NON_INTERFERENCE_NOTE = (
    "EPI-LEAN does not invalidate, modify, override, or replace the "
    "formal verification status established by Lean. Its assessments "
    "are complementary epistemic evaluations and remain explicitly "
    "distinguishable from formal proof validity."
)


def assess_declaration(
    declaration: dict,
    entry: dict | None,
) -> dict:
    """Produce an epistemic assessment for one declaration.

    The assessment has three independent fields (observation, evidence,
    assessment), so that an algorithmic suspicion is never presented as
    a mathematical conclusion. Without a semantic entry, the epistemic
    status is INSUFFICIENT_EVIDENCE: the prototype cannot infer meaning.
    """
    if entry is None:
        return {
            "declaration": declaration["name"],
            "epistemic_status": INSUFFICIENT_EVIDENCE,
            "observation": (
                "No semantic registry entry was supplied for this "
                "declaration; EPI-LEAN cannot assess its intended "
                "mathematical meaning."
            ),
            "evidence": [],
            "human_review_required": True,
        }

    status = entry["status"]
    evidence = [entry.get("evidence", "Not supplied")]
    references = entry.get("references") or []
    evidence.extend(references)

    if status == "reviewed":
        epistemic_status = SEMANTICALLY_SUPPORTED
        observation = (
            "A human review of this interpretation has been recorded. "
            "'Reviewed' is a workflow annotation, not a machine-verified "
            "truth claim."
        )
        human_review = False
    elif status == "under_review":
        epistemic_status = REVIEW_REQUIRED
        observation = (
            "The recorded interpretation is currently under review; "
            "no semantic conclusion is drawn until the review completes."
        )
        human_review = True
    else:  # "proposed"
        epistemic_status = POTENTIAL_MISMATCH
        observation = (
            "The recorded interpretation is a proposal. It has not been "
            "reviewed, so a potential mismatch between the declared "
            "meaning and the formal content cannot be excluded yet."
        )
        human_review = True

    return {
        "declaration": declaration["name"],
        "epistemic_status": epistemic_status,
        "observation": observation,
        "evidence": evidence,
        "human_review_required": human_review,
    }


def assess_project(
    declaration_audits: list[dict],
    semantic_entries: list[dict],
) -> list[dict]:
    """Assess every declaration, keeping declaration order stable."""
    by_declaration = {
        entry["declaration"]: entry
        for entry in semantic_entries
    }
    return [
        assess_declaration(item, by_declaration.get(item["name"]))
        for item in declaration_audits
    ]


def epistemic_summary(
    assessments: list[dict],
) -> dict[str, int]:
    """Count each epistemic status across all assessments."""
    counts = {status: 0 for status in ALL_STATUSES}
    for assessment in assessments:
        counts[assessment["epistemic_status"]] += 1
    return counts
