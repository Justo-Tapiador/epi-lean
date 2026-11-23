"""Schema conformance tests.

jsonschema is optional: if unavailable, tests validate the essentials
by hand so CI still runs with zero dependencies.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "semantic-registry.schema.json"

try:
    import jsonschema

    HAVE_JSONSCHEMA = True
except ImportError:
    HAVE_JSONSCHEMA = False


def _schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _registries():
    return {
        "basic": REPO_ROOT / "examples" / "basic" / "semantic_registry.json",
        "mismatch": (
            REPO_ROOT / "examples" / "semantic-mismatch" / (
                "semantic_registry.json"
            )
        ),
    }


def test_schema_file_exists_and_parses():
    schema = _schema()
    assert schema["title"] == "EPI-LEAN semantic registry"
    assert schema["required"] == ["entries"]
    entry = schema["$defs"]["entry"]
    assert set(entry["required"]) == {
        "declaration", "interpretation", "status",
    }
    assert entry["properties"]["status"]["enum"] == [
        "proposed", "under_review", "reviewed",
    ]
    assert entry["properties"]["origin"]["enum"] == [
        "human", "ai_proposal",
    ]


def test_example_registries_conform():
    for name, path in _registries().items():
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload["entries"], list), name

        if HAVE_JSONSCHEMA:
            jsonschema.validate(payload, _schema())


def test_valid_entry_shape():
    if not HAVE_JSONSCHEMA:
        return
    payload = {
        "entries": [
            {
                "declaration": "t",
                "interpretation": "desc",
                "status": "reviewed",
                "evidence": "e",
                "origin": "human",
                "references": ["ref"],
            }
        ]
    }
    jsonschema.validate(payload, _schema())


def test_invalid_status_rejected():
    if not HAVE_JSONSCHEMA:
        return
    payload = {
        "entries": [
            {
                "declaration": "t",
                "interpretation": "desc",
                "status": "approved",
            }
        ]
    }
    try:
        jsonschema.validate(payload, _schema())
    except jsonschema.ValidationError:
        pass
    else:
        raise AssertionError("Expected schema rejection of bad status")
