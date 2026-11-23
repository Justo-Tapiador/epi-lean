import json

from epilean.audit import audit_project
from epilean.report import render_json, render_markdown


def test_audit_and_render(tmp_path):
    source = """
axiom premise : True

theorem conclusion : True := premise
"""

    (tmp_path / "Main.lean").write_text(
        source,
        encoding="utf-8",
    )

    report = audit_project(tmp_path)

    assert report["summary"]["declaration_count"] == 2

    conclusion = next(
        item
        for item in report["declaration_audits"]
        if item["name"] == "conclusion"
    )

    assert conclusion["declared_axiom_provenance"] == ["premise"]
    assert "not a Lean kernel verification result" in render_markdown(report)
    assert '"declaration_audits"' in render_json(report)


def test_formal_verification_block_is_present(tmp_path):
    (tmp_path / "Main.lean").write_text(
        "theorem t : True := trivial\n",
        encoding="utf-8",
    )

    report = audit_project(tmp_path)

    assert report["formal_verification"]["status"] == "NOT_CHECKED"
    assert "does not invalidate" in (
        report["formal_verification"]["non_interference"]
    )
    assert "NOT_CHECKED" in render_markdown(report)
    assert "does not invalidate" in render_markdown(report)


def test_declarations_without_registry_are_insufficient_evidence(tmp_path):
    (tmp_path / "Main.lean").write_text(
        "theorem t : True := trivial\n",
        encoding="utf-8",
    )

    report = audit_project(tmp_path)

    assessment = report["epistemic_assessments"][0]
    assert assessment["epistemic_status"] == "INSUFFICIENT_EVIDENCE"
    assert assessment["human_review_required"] is True
    assert report["epistemic_summary"]["INSUFFICIENT_EVIDENCE"] == 1


def test_registry_statuses_drive_epistemic_statuses(tmp_path):
    (tmp_path / "Main.lean").write_text(
        "theorem good : True := trivial\n"
        "theorem unsure : True := trivial\n"
        "theorem bad : True := trivial\n",
        encoding="utf-8",
    )

    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps({
            "entries": [
                {
                    "declaration": "good",
                    "interpretation": "honest",
                    "status": "reviewed",
                    "evidence": "checked by hand",
                },
                {
                    "declaration": "unsure",
                    "interpretation": "being checked",
                    "status": "under_review",
                    "evidence": "draft notes",
                },
                {
                    "declaration": "bad",
                    "interpretation": "claimed",
                    "status": "proposed",
                    "evidence": "name suggests it",
                },
            ]
        }),
        encoding="utf-8",
    )

    report = audit_project(tmp_path, registry)

    by_declaration = {
        item["declaration"]: item["epistemic_status"]
        for item in report["epistemic_assessments"]
    }

    assert by_declaration == {
        "good": "SEMANTICALLY_SUPPORTED",
        "unsure": "REVIEW_REQUIRED",
        "bad": "POTENTIAL_MISMATCH",
    }

    assert report["epistemic_summary"] == {
        "SEMANTICALLY_SUPPORTED": 1,
        "POTENTIAL_MISMATCH": 1,
        "REVIEW_REQUIRED": 1,
        "INSUFFICIENT_EVIDENCE": 0,
    }


def test_markdown_report_shows_epistemic_table(tmp_path):
    (tmp_path / "Main.lean").write_text(
        "theorem t : True := trivial\n",
        encoding="utf-8",
    )

    text = render_markdown(audit_project(tmp_path))

    assert "## Epistemic summary" in text
    assert "## Formal verification status" in text
    assert "| insufficient evidence (`INSUFFICIENT_EVIDENCE`) | 1 |" in text
    assert "| `t` | theorem | — | — | `INSUFFICIENT_EVIDENCE` |" in text


def test_version_is_recorded(tmp_path):
    (tmp_path / "Main.lean").write_text(
        "theorem t : True := trivial\n",
        encoding="utf-8",
    )

    report = audit_project(tmp_path)

    assert report["version"] == "0.2.0"
