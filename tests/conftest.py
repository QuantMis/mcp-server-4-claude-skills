"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from skills_mcp import db
from skills_mcp.repository import SkillRepository


@pytest.fixture()
def conn():
    """An in-memory SQLite connection with the schema applied."""
    connection = db.connect(":memory:")
    db.init_schema(connection)
    yield connection
    connection.close()


@pytest.fixture()
def repo(conn):
    """A repository backed by the in-memory connection."""
    return SkillRepository(conn)
