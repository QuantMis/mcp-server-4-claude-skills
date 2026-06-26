"""Unit tests for configuration loading and validation."""

from __future__ import annotations

import pytest

from skills_mcp.config import Config, ConfigError, load_config


def test_load_minimal_uses_defaults():
    cfg = load_config({"SKILLS_MCP_BEARER_TOKEN": "secret"})

    assert isinstance(cfg, Config)
    assert cfg.bearer_token == "secret"
    assert cfg.db_path == "./skills.db"
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8765


def test_load_full_override():
    cfg = load_config(
        {
            "SKILLS_MCP_BEARER_TOKEN": "  tok  ",
            "SKILLS_MCP_DB_PATH": "/data/s.db",
            "SKILLS_MCP_HOST": "127.0.0.1",
            "SKILLS_MCP_PORT": "9000",
        }
    )

    assert cfg.bearer_token == "tok"  # trimmed
    assert cfg.db_path == "/data/s.db"
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 9000


@pytest.mark.parametrize("env", [{}, {"SKILLS_MCP_BEARER_TOKEN": "   "}])
def test_missing_token_raises(env):
    with pytest.raises(ConfigError):
        load_config(env)


def test_non_integer_port_raises():
    with pytest.raises(ConfigError):
        load_config({"SKILLS_MCP_BEARER_TOKEN": "t", "SKILLS_MCP_PORT": "abc"})


@pytest.mark.parametrize("port", ["0", "70000", "-1"])
def test_out_of_range_port_raises(port):
    with pytest.raises(ConfigError):
        load_config({"SKILLS_MCP_BEARER_TOKEN": "t", "SKILLS_MCP_PORT": port})


def test_config_is_immutable():
    cfg = load_config({"SKILLS_MCP_BEARER_TOKEN": "t"})
    with pytest.raises(Exception):
        cfg.bearer_token = "other"  # type: ignore[misc]
