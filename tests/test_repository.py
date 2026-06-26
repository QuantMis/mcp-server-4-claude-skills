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
