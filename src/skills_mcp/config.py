"""Runtime configuration, loaded once from the environment at startup.

Validates required settings eagerly (fail fast) per the security rule:
"Validate that required secrets are present at startup."
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_BEARER_ENV = "SKILLS_MCP_BEARER_TOKEN"
_DB_PATH_ENV = "SKILLS_MCP_DB_PATH"
_HOST_ENV = "SKILLS_MCP_HOST"
_PORT_ENV = "SKILLS_MCP_PORT"

_DEFAULT_DB_PATH = "./skills.db"
_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 8080


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    """Immutable view of the server's runtime configuration."""

    bearer_token: str
    db_path: str
    host: str
    port: int


def load_config(env: dict[str, str] | None = None) -> Config:
    """Build a :class:`Config` from ``env`` (defaults to ``os.environ``).

    Raises :class:`ConfigError` if the bearer token is absent/blank or the
    port is not a valid integer.
    """

    source = os.environ if env is None else env

    token = (source.get(_BEARER_ENV) or "").strip()
    if not token:
        raise ConfigError(
            f"{_BEARER_ENV} is required; the server will not start without a "
            "bearer token. See .env.example."
        )

    raw_port = (source.get(_PORT_ENV) or "").strip() or str(_DEFAULT_PORT)
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ConfigError(f"{_PORT_ENV} must be an integer, got {raw_port!r}") from exc
    if not 0 < port < 65536:
        raise ConfigError(f"{_PORT_ENV} must be in 1..65535, got {port}")

    return Config(
        bearer_token=token,
        db_path=(source.get(_DB_PATH_ENV) or "").strip() or _DEFAULT_DB_PATH,
        host=(source.get(_HOST_ENV) or "").strip() or _DEFAULT_HOST,
        port=port,
    )
