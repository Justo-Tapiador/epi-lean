from epilean.epistemic import (
    INSUFFICIENT_EVIDENCE,
    NON_INTERFERENCE_NOTE,
    POTENTIAL_MISMATCH,
    REVIEW_REQUIRED,
    SEMANTICALLY_SUPPORTED,
    assess_declaration,
    epistemic_summary,
)


def _declaration(name):
    return {
        "name": name,
        "kind": "theorem",
        "file": "A.lean",
        "line": 1,
        "source": "",
        "dependencies": [],
    }


def test_no_entry_means_insufficient_evidence():
    assessment = assess_declaration(_declaration("t"), None)
    assert assessment["epistemic_status"] == INSUFFICIENT_EVIDENCE
    assert assessment["human_review_required"] is True
    assert "cannot assess" in assessment["observation"]


def test_reviewed_entry_is_semantically_supported():
    entry = {"status": "reviewed", "evidence": "checked by hand"}
    assessment = assess_declaration(_declaration("t"), entry)
    assert assessment["epistemic_status"] == SEMANTICALLY_SUPPORTED
    assert assessment["human_review_required"] is False


def test_under_review_entry_requires_review():
    entry = {"status": "under_review", "evidence": "draft notes"}
    assessment = assess_declaration(_declaration("t"), entry)
    assert assessment["epistemic_status"] == REVIEW_REQUIRED
    assert assessment["human_review_required"] is True


def test_proposed_entry_is_potential_mismatch():
    entry = {"status": "proposed", "evidence": "name suggests it"}
    assessment = assess_declaration(_declaration("t"), entry)
    assert assessment["epistemic_status"] == POTENTIAL_MISMATCH
    assert assessment["human_review_required"] is True


def test_evidence_and_references_are_collected():
    entry = {
        "status": "reviewed",
        "evidence": "matches Definition 2.3",
        "references": ["Bourbaki, Alg. I", "Mathlib issue #1"],
    }
    assessment = assess_declaration(_declaration("t"), entry)
    assert "matches Definition 2.3" in assessment["evidence"]
    assert "Bourbaki, Alg. I" in assessment["evidence"]
    assert "Mathlib issue #1" in assessment["evidence"]


def test_non_interference_note_is_explicit():
    assert "does not invalidate" in NON_INTERFERENCE_NOTE
    assert "formal verification status established by Lean" in (
        NON_INTERFERENCE_NOTE
    )


def test_epistemic_summary_counts_all_statuses():
    counts = epistemic_summary([
        {"epistemic_status": SEMANTICALLY_SUPPORTED},
        {"epistemic_status": SEMANTICALLY_SUPPORTED},
        {"epistemic_status": POTENTIAL_MISMATCH},
    ])
    assert counts == {
        SEMANTICALLY_SUPPORTED: 2,
        POTENTIAL_MISMATCH: 1,
        REVIEW_REQUIRED: 0,
        INSUFFICIENT_EVIDENCE: 0,
    }
