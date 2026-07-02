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
from .web import create_web_app


def _transport_security(allowed_hosts: tuple[str, ...]) -> TransportSecuritySettings:
    """Translate configured public hosts into FastMCP transport security.

    No configured hosts -> protection disabled (bearer auth is the access
    gate; the server is public and TLS-terminated by nginx). Configured hosts
    -> protection enabled, allow-listing each host (with an ``:*`` port
    variant) and its ``https`` origins for defence-in-depth. Plaintext
    ``http`` origins are deliberately excluded: the public deployment is
    TLS-only, so no legitimate request carries one.
    """

    if not allowed_hosts:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)

    hosts: list[str] = []
    origins: list[str] = []
    for host in allowed_hosts:
        hosts.extend((host, f"{host}:*"))
        origins.extend((f"https://{host}", f"https://{host}:*"))
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


def _is_web_path(path: str) -> bool:
    """True for the read-only viewer paths that bypass bearer auth."""
    return (
        path == "/ui"
        or path.startswith("/ui/")
        or path == "/api"
        or path.startswith("/api/")
    )


class _Composite:
    """Front controller: open viewer for ``/ui`` + ``/api``, MCP for the rest.

    HTTP requests to the viewer paths are dispatched to the unauthenticated
    web app; every other scope — including the MCP ``/mcp`` endpoint, the
    lifespan events that start the MCP session manager, and websockets — goes
    to the bearer-protected MCP app untouched.
    """

    def __init__(self, web_app: ASGIApp, mcp_app: ASGIApp) -> None:
        self._web = web_app
        self._mcp = mcp_app

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] == "http" and _is_web_path(scope.get("path", "")):
            await self._web(scope, receive, send)
            return
        await self._mcp(scope, receive, send)


def build_app(config: Config) -> ASGIApp:
    """Construct the fully-wired ASGI application (no network binding).

    Opens the database, applies the schema, builds the MCP streamable-HTTP app
    wrapped in bearer-token auth, and fronts it with a read-only browser viewer
    (``/ui`` + ``/api``) that is deliberately left unauthenticated. Kept
    side-effect-light so tests can drive it through an in-process ASGI transport.
    """

    conn = db.connect(config.db_path)
    db.init_schema(conn)
    repo = SkillRepository(conn)
    mcp = create_mcp(repo, transport_security=_transport_security(config.allowed_hosts))
    http_app = mcp.streamable_http_app()
    protected_mcp = BearerAuthMiddleware(http_app, config.bearer_token)
    return _Composite(create_web_app(repo), protected_mcp)


def run(config: Config | None = None) -> None:
    """Load config (if not supplied) and serve over Streamable HTTP."""

    config = config or load_config()
    app = build_app(config)
    uvicorn.run(app, host=config.host, port=config.port)
