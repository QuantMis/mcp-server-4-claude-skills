"""SQLite connection and schema management.

Three tables (plan section 4):

* ``skills``         — current state, keyed by ``name``.
* ``skill_versions`` — append-only history; every update snapshots the prior
  content here so that overwrites and mistakes are always recoverable.
* ``skill_tags``     — many-to-many grouping labels; current-state metadata,
  not versioned content, so it sits outside the append-only invariant.
"""

from __future__ import annotations

import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    name        TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    content     TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_versions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (name) REFERENCES skills (name)
);

CREATE INDEX IF NOT EXISTS idx_skill_versions_name
    ON skill_versions (name, id);

CREATE TABLE IF NOT EXISTS skill_tags (
    name TEXT NOT NULL,
    tag  TEXT NOT NULL,
    PRIMARY KEY (name, tag),
    FOREIGN KEY (name) REFERENCES skills (name)
);

CREATE INDEX IF NOT EXISTS idx_skill_tags_tag
    ON skill_tags (tag);
"""


def connect(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection with sensible pragmas and row access by name.

    ``check_same_thread=False`` is safe here: writes are serialised by the
    repository and SQLite's own locking, and the async server may dispatch
    calls across the anyio worker threads.
    """

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they do not already exist (idempotent)."""

    conn.executescript(_SCHEMA)
    conn.commit()
