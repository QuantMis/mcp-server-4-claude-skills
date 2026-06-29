"""Server assembly: wire config -> SQLite -> repository -> MCP -> auth -> ASGI."""

from __future__ import annotations

import uvicorn
from mcp.server.transport_security import TransportSecuritySettings
from starlette.types import ASGIApp

from . import db
from .auth import BearerAuthMiddleware
from .config import Config, load_config
from .repository import SkillRepository
from .tools import create_mcp


def _transport_security(allowed_hosts: tuple[str, ...]) -> TransportSecuritySettings:
    """Translate configured public hosts into FastMCP transport security.

    No configured hosts -> protection disabled (bearer auth is the access
    gate; the server is public and TLS-terminated by nginx). Configured hosts
    -> protection enabled, allow-listing each host (with an ``:*`` port
    variant) and its http/https origins for defence-in-depth.
    """

    if not allowed_hosts:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)

    hosts: list[str] = []
    origins: list[str] = []
    for host in allowed_hosts:
        hosts.extend((host, f"{host}:*"))
        origins.extend((f"https://{host}", f"http://{host}"))
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


def build_app(config: Config) -> ASGIApp:
    """Construct the fully-wired ASGI application (no network binding).

    Opens the database, applies the schema, builds the MCP streamable-HTTP app
    and wraps it in bearer-token auth. Kept side-effect-light so tests can
    drive it through an in-process ASGI transport.
    """

    conn = db.connect(config.db_path)
    db.init_schema(conn)
    repo = SkillRepository(conn)
    mcp = create_mcp(repo, transport_security=_transport_security(config.allowed_hosts))
    http_app = mcp.streamable_http_app()
    return BearerAuthMiddleware(http_app, config.bearer_token)


def run(config: Config | None = None) -> None:
    """Load config (if not supplied) and serve over Streamable HTTP."""

    config = config or load_config()
    app = build_app(config)
    uvicorn.run(app, host=config.host, port=config.port)
