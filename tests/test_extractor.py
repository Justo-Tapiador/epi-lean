from epilean.extractor import extract_declarations


def test_extracts_declarations_and_dependencies(tmp_path):
    source = """
axiom baseFact : True

lemma helper : True := baseFact

theorem result : True := helper
"""

    (tmp_path / "Example.lean").write_text(
        source,
        encoding="utf-8",
    )

    declarations = extract_declarations(tmp_path)
    by_name = {
        item.name: item
        for item in declarations
    }

    assert set(by_name) == {
        "baseFact",
        "helper",
        "result",
    }

    assert "baseFact" in by_name["helper"].dependencies
    assert "helper" in by_name["result"].dependencies


def test_ignores_comments(tmp_path):
    source = """
-- theorem fake : True := by trivial
/- lemma alsoFake : True := by trivial -/

theorem real : True := by trivial
"""

    (tmp_path / "Comments.lean").write_text(
        source,
        encoding="utf-8",
    )

    declarations = extract_declarations(tmp_path)

    assert [item.name for item in declarations] == ["real"]


def test_block_comment_at_end_of_file(tmp_path):
    # Regression: a block comment ending at the last character of the
    # file used to raise IndexError in strip_comments.
    source = "theorem real : True := trivial\n/- trailing comment -/"

    (tmp_path / "Tail.lean").write_text(
        source,
        encoding="utf-8",
    )

    declarations = extract_declarations(tmp_path)

    assert [item.name for item in declarations] == ["real"]


def test_attribute_and_modifier_declarations(tmp_path):
    source = """
@[simp]
theorem simplified : True := trivial

private theorem hidden : True := trivial

noncomputable def f : Nat := 0

partial def g (n : Nat) : Nat := n

instance inst : True := trivial
"""

    (tmp_path / "Attrs.lean").write_text(
        source,
        encoding="utf-8",
    )

    names = {
        item.name: item.kind
        for item in extract_declarations(tmp_path)
    }

    assert names == {
        "simplified": "theorem",
        "hidden": "theorem",
        "f": "def",
        "g": "def",
        "inst": "instance",
    }


def test_dependency_body_stops_at_next_declaration(tmp_path):
    source = """
axiom a1 : True

theorem t1 : True := a1

theorem t2 : True := trivial
"""

    (tmp_path / "Chain.lean").write_text(
        source,
        encoding="utf-8",
    )

    by_name = {
        item.name: item
        for item in extract_declarations(tmp_path)
    }

    # t2 mentions no axiom; a1 must not leak into its dependencies.
    assert by_name["t2"].dependencies == ()
    assert by_name["t1"].dependencies == ("a1",)
