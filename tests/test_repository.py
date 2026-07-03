"""Unit tests for the SkillRepository (data access + versioning)."""

from __future__ import annotations

import pytest

from skills_mcp.repository import (
    DuplicateSkillError,
    NoPriorVersionError,
    SkillNotFoundError,
    SkillRepository,
)


def test_register_then_get_roundtrip(repo: SkillRepository):
    repo.register("deploy", "How to deploy", "Step 1. Push. Step 2. Pray.")

    skill = repo.get("deploy")

    assert skill.name == "deploy"
    assert skill.description == "How to deploy"
    assert skill.content == "Step 1. Push. Step 2. Pray."
    assert skill.updated_at  # ISO timestamp present


def test_list_returns_index_only(repo: SkillRepository):
    repo.register("a", "First skill", "AAA body")
    repo.register("b", "Second skill", "BBB body")

    index = repo.list()

    assert {(s.name, s.description) for s in index} == {
        ("a", "First skill"),
        ("b", "Second skill"),
    }
    # The lightweight index intentionally does not carry full content.
    assert all(not hasattr(s, "content") for s in index)


def test_list_is_sorted_by_name(repo: SkillRepository):
    repo.register("zebra", "z", "z body")
    repo.register("apple", "a", "a body")

    names = [s.name for s in repo.list()]

    assert names == ["apple", "zebra"]


def test_list_empty(repo: SkillRepository):
    assert repo.list() == []


def test_get_missing_raises(repo: SkillRepository):
    with pytest.raises(SkillNotFoundError):
        repo.get("nope")


def test_register_duplicate_name_refused(repo: SkillRepository):
    repo.register("dup", "first", "first body")

    with pytest.raises(DuplicateSkillError):
        repo.register("dup", "second", "second body")

    # Original is untouched.
    assert repo.get("dup").content == "first body"


@pytest.mark.parametrize("bad", ["", "   ", "\t\n"])
def test_register_rejects_blank_name(repo: SkillRepository, bad: str):
    with pytest.raises(ValueError):
        repo.register(bad, "desc", "content")


def test_register_rejects_blank_content_and_description(repo: SkillRepository):
    with pytest.raises(ValueError):
        repo.register("x", "desc", "   ")
    with pytest.raises(ValueError):
        repo.register("x", "  ", "content")


def test_update_snapshots_prior_version(repo: SkillRepository):
    repo.register("note", "a note", "v1 content")
    repo.update("note", "v2 content")

    assert repo.get("note").content == "v2 content"

    versions = repo.history("note")
    assert [v.content for v in versions] == ["v1 content"]
    assert versions[0].created_at


def test_update_preserves_description(repo: SkillRepository):
    repo.register("note", "original desc", "v1")
    repo.update("note", "v2")

    assert repo.get("note").description == "original desc"


def test_update_bumps_timestamp(repo: SkillRepository):
    repo.register("note", "d", "v1")
    first = repo.get("note").updated_at
    repo.update("note", "v2")
    second = repo.get("note").updated_at

    assert second >= first


def test_update_missing_raises(repo: SkillRepository):
    with pytest.raises(SkillNotFoundError):
        repo.update("ghost", "content")


def test_update_rejects_blank_content(repo: SkillRepository):
    repo.register("note", "d", "v1")
    with pytest.raises(ValueError):
        repo.update("note", "   ")


def test_multiple_updates_accumulate_history(repo: SkillRepository):
    repo.register("note", "d", "v1")
    repo.update("note", "v2")
    repo.update("note", "v3")

    # History is append-only and ordered oldest -> newest.
    assert [v.content for v in repo.history("note")] == ["v1", "v2"]
    assert repo.get("note").content == "v3"


def test_revert_restores_most_recent_prior_version(repo: SkillRepository):
    repo.register("note", "d", "v1")
    repo.update("note", "v2")

    repo.revert("note")

    assert repo.get("note").content == "v1"


def test_revert_is_itself_recoverable(repo: SkillRepository):
    # Revert snapshots the current content before restoring, so it stays
    # append-only and a revert can be undone.
    repo.register("note", "d", "v1")
    repo.update("note", "v2")  # history: [v1]
    repo.revert("note")        # history: [v1, v2], content -> v1
    repo.revert("note")        # history: [v1, v2, v1], content -> v2

    assert repo.get("note").content == "v2"


def test_revert_without_history_raises(repo: SkillRepository):
    repo.register("note", "d", "v1")
    with pytest.raises(NoPriorVersionError):
        repo.revert("note")


def test_revert_missing_skill_raises(repo: SkillRepository):
    with pytest.raises(SkillNotFoundError):
        repo.revert("ghost")


def test_history_missing_skill_raises(repo: SkillRepository):
    with pytest.raises(SkillNotFoundError):
        repo.history("ghost")


# ------------------------------------------------------------------------ tags
def test_register_with_tags_roundtrip(repo: SkillRepository):
    repo.register("deploy", "d", "c", tags=["ops", "ci"])

    assert repo.get("deploy").tags == ("ci", "ops")


def test_register_defaults_to_no_tags(repo: SkillRepository):
    repo.register("deploy", "d", "c")

    assert repo.get("deploy").tags == ()


def test_tags_are_normalised_and_deduplicated(repo: SkillRepository):
    repo.register("deploy", "d", "c", tags=["  Ops ", "ops", "CI"])

    assert repo.get("deploy").tags == ("ci", "ops")


def test_register_rejects_blank_tag(repo: SkillRepository):
    with pytest.raises(ValueError):
        repo.register("deploy", "d", "c", tags=["ops", "   "])


def test_register_rejects_bare_string_tags(repo: SkillRepository):
    # A plain string would iterate per-character and silently store
    # single-letter tags; the boundary must reject it instead.
    with pytest.raises(ValueError):
        repo.register("deploy", "d", "c", tags="ops")


def test_set_tags_rejects_bare_string_tags(repo: SkillRepository):
    repo.register("a", "d", "c")
    with pytest.raises(ValueError):
        repo.set_tags("a", "ops")


def test_list_includes_tags(repo: SkillRepository):
    repo.register("a", "da", "ca", tags=["x"])
    repo.register("b", "db", "cb")

    by_name = {s.name: s.tags for s in repo.list()}

    assert by_name == {"a": ("x",), "b": ()}


def test_list_filters_by_tag(repo: SkillRepository):
    repo.register("a", "da", "ca", tags=["planka"])
    repo.register("b", "db", "cb", tags=["codebase"])
    repo.register("c", "dc", "cc", tags=["planka", "codebase"])

    assert [s.name for s in repo.list(tag="planka")] == ["a", "c"]


def test_list_filter_matches_case_insensitively(repo: SkillRepository):
    repo.register("a", "da", "ca", tags=["planka"])

    assert [s.name for s in repo.list(tag="  Planka ")] == ["a"]


def test_list_unknown_tag_returns_empty(repo: SkillRepository):
    repo.register("a", "da", "ca", tags=["x"])

    assert repo.list(tag="nope") == []


def test_set_tags_replaces_existing_set(repo: SkillRepository):
    repo.register("a", "d", "c", tags=["old"])

    repo.set_tags("a", ["new", "fresh"])

    assert repo.get("a").tags == ("fresh", "new")


def test_set_tags_empty_clears(repo: SkillRepository):
    repo.register("a", "d", "c", tags=["old"])

    repo.set_tags("a", [])

    assert repo.get("a").tags == ()


def test_set_tags_missing_skill_raises(repo: SkillRepository):
    with pytest.raises(SkillNotFoundError):
        repo.set_tags("ghost", ["x"])


def test_set_tags_rejects_blank_tag(repo: SkillRepository):
    repo.register("a", "d", "c")
    with pytest.raises(ValueError):
        repo.set_tags("a", [""])


def test_update_preserves_tags(repo: SkillRepository):
    repo.register("a", "d", "v1", tags=["keep"])
    repo.update("a", "v2")

    assert repo.get("a").tags == ("keep",)
