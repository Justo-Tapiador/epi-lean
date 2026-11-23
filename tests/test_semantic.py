import json

from epilean.semantic import load_semantic_registry


def _write(tmp_path, payload, name="registry.json"):
    registry = tmp_path / name
    registry.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    return registry


def test_loads_semantic_registry(tmp_path):
    registry = _write(tmp_path, {
        "entries": [
            {
                "declaration": "known",
                "interpretation": "A sample mathematical interpretation.",
                "status": "proposed",
                "evidence": "Example evidence.",
            }
        ]
    })

    entries, warnings = load_semantic_registry(
        registry,
        {"known"},
    )

    assert len(entries) == 1
    assert warnings == []


def test_rejects_invalid_registry(tmp_path):
    registry = _write(tmp_path, {"wrong": []})

    try:
        load_semantic_registry(registry, set())
    except ValueError as error:
        assert "entries" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_duplicate_declarations_warn(tmp_path):
    registry = _write(tmp_path, {
        "entries": [
            {
                "declaration": "t",
                "interpretation": "first",
                "status": "proposed",
            },
            {
                "declaration": "t",
                "interpretation": "second",
                "status": "proposed",
            },
        ]
    })

    entries, warnings = load_semantic_registry(registry, {"t"})

    assert [entry["interpretation"] for entry in entries] == ["first"]
    assert any("duplicate" in warning.lower() for warning in warnings)


def test_reviewed_without_evidence_is_downgraded(tmp_path):
    registry = _write(tmp_path, {
        "entries": [
            {
                "declaration": "t",
                "interpretation": "desc",
                "status": "reviewed",
            }
        ]
    })

    entries, warnings = load_semantic_registry(registry, {"t"})

    assert entries[0]["status"] == "under_review"
    assert any("downgraded" in warning for warning in warnings)


def test_ai_proposal_marked_reviewed_is_downgraded(tmp_path):
    registry = _write(tmp_path, {
        "entries": [
            {
                "declaration": "t",
                "interpretation": "desc",
                "status": "reviewed",
                "evidence": "an LLM suggested it",
                "origin": "ai_proposal",
            }
        ]
    })

    entries, warnings = load_semantic_registry(registry, {"t"})

    assert entries[0]["status"] == "under_review"
    assert any("AI" in warning for warning in warnings)


def test_empty_required_strings_are_skipped(tmp_path):
    registry = _write(tmp_path, {
        "entries": [
            {
                "declaration": "t",
                "interpretation": "   ",
                "status": "proposed",
            }
        ]
    })

    entries, warnings = load_semantic_registry(registry, {"t"})

    assert entries == []
    assert any("empty" in warning for warning in warnings)


def test_unknown_declaration_warns_but_entry_is_kept(tmp_path):
    registry = _write(tmp_path, {
        "entries": [
            {
                "declaration": "ghost",
                "interpretation": "desc",
                "status": "proposed",
            }
        ]
    })

    entries, warnings = load_semantic_registry(registry, {"other"})

    assert len(entries) == 1
    assert any("unknown declaration" in warning for warning in warnings)


def test_no_registry_means_no_entries():
    entries, warnings = load_semantic_registry(None, set())
    assert entries == []
    assert warnings == []
