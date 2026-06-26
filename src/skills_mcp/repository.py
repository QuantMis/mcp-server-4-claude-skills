"""Data access for skills, with append-only versioning.

The repository is the only place that touches SQL. Business/transport layers
depend on this interface, not on the storage mechanism (repository pattern).

Versioning invariant (plan section 6, guardrail #1): every content overwrite
first snapshots the prior content into ``skill_versions``. History is never
deleted, so every mistake is recoverable.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


class RepositoryError(Exception):
    """Base class for repository errors."""


class SkillNotFoundError(RepositoryError):
    """Raised when a named skill does not exist."""


class DuplicateSkillError(RepositoryError):
    """Raised when registering a name that already exists."""


class NoPriorVersionError(RepositoryError):
    """Raised when reverting a skill that has no prior version."""


@dataclass(frozen=True)
class Skill:
    """Full skill record (current state)."""

    name: str
    description: str
    content: str
    updated_at: str


@dataclass(frozen=True)
class SkillSummary:
    """Lightweight index entry returned by :meth:`SkillRepository.list`."""

    name: str
    description: str


@dataclass(frozen=True)
class SkillVersion:
    """A superseded snapshot from the append-only history."""

    content: str
    created_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: str, field: str) -> str:
    """Validate a required string field at the boundary; never trust input."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


class SkillRepository:
    """SQLite-backed store for skills and their version history."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------ reads
    def list(self) -> list[SkillSummary]:
        """Return the lightweight catalogue (name + description), sorted."""
        rows = self._conn.execute(
            "SELECT name, description FROM skills ORDER BY name"
        ).fetchall()
        return [SkillSummary(name=r["name"], description=r["description"]) for r in rows]

    def get(self, name: str) -> Skill:
        """Return the full skill, or raise :class:`SkillNotFoundError`."""
        row = self._conn.execute(
            "SELECT name, description, content, updated_at FROM skills WHERE name = ?",
            (name,),
        ).fetchone()
        if row is None:
            raise SkillNotFoundError(name)
        return Skill(
            name=row["name"],
            description=row["description"],
            content=row["content"],
            updated_at=row["updated_at"],
        )

    def history(self, name: str) -> list[SkillVersion]:
        """Return prior versions oldest -> newest. Raises if skill is unknown."""
        self._require_exists(name)
        rows = self._conn.execute(
            "SELECT content, created_at FROM skill_versions WHERE name = ? ORDER BY id",
            (name,),
        ).fetchall()
        return [
            SkillVersion(content=r["content"], created_at=r["created_at"]) for r in rows
        ]

    # ----------------------------------------------------------------- writes
    def register(self, name: str, description: str, content: str) -> Skill:
        """Create a new skill. Refuses on exact name collision."""
        name = _clean(name, "name")
        description = _clean(description, "description")
        content = _clean(content, "content")

        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO skills (name, description, content, updated_at) "
                    "VALUES (?, ?, ?, ?)",
                    (name, description, content, _now()),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateSkillError(name) from exc
        return self.get(name)

    def update(self, name: str, content: str) -> Skill:
        """Snapshot the current content into history, then overwrite."""
        content = _clean(content, "content")
        with self._conn:
            current = self._get_for_update(name)
            self._snapshot(name, current["content"])
            self._conn.execute(
                "UPDATE skills SET content = ?, updated_at = ? WHERE name = ?",
                (content, _now(), name),
            )
        return self.get(name)

    def revert(self, name: str) -> Skill:
        """Restore the most recent prior version.

        The current content is snapshotted first, so revert stays append-only
        and is itself reversible.
        """
        with self._conn:
            current = self._get_for_update(name)
            prior = self._conn.execute(
                "SELECT content FROM skill_versions WHERE name = ? "
                "ORDER BY id DESC LIMIT 1",
                (name,),
            ).fetchone()
            if prior is None:
                raise NoPriorVersionError(name)
            self._snapshot(name, current["content"])
            self._conn.execute(
                "UPDATE skills SET content = ?, updated_at = ? WHERE name = ?",
                (prior["content"], _now(), name),
            )
        return self.get(name)

    # ---------------------------------------------------------------- helpers
    def _require_exists(self, name: str) -> None:
        row = self._conn.execute(
            "SELECT 1 FROM skills WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            raise SkillNotFoundError(name)

    def _get_for_update(self, name: str) -> sqlite3.Row:
        row = self._conn.execute(
            "SELECT content FROM skills WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            raise SkillNotFoundError(name)
        return row

    def _snapshot(self, name: str, content: str) -> None:
        self._conn.execute(
            "INSERT INTO skill_versions (name, content, created_at) VALUES (?, ?, ?)",
            (name, content, _now()),
        )
