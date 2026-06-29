"""Wiring tests for the assembled ASGI application.

These verify that auth sits in front of the MCP app. Full MCP protocol
behaviour is covered by tests/test_tools.py via FastMCP.call_tool; here we
only assert the integration boundary (unauthenticated requests never reach
the MCP layer).
"""

from __future__ import annotations

import httpx
import pytest
from asgi_lifespan import LifespanManager

from skills_mcp.config import Config
from skills_mcp.server import build_app

CONFIG = Config(
    bearer_token="test-token",
    db_path=":memory:",
    host="127.0.0.1",
    port=8765,
)


@pytest.fixture()
async def client():
    # LifespanManager starts the MCP session manager's task group so that
    # authenticated requests can reach the MCP layer.
    app = build_app(CONFIG)
    async with LifespanManager(app) as managed:
        transport = httpx.ASGITransport(app=managed.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as ac:
            yield ac


async def test_unauthenticated_request_blocked_at_mcp_path(client):
    resp = await client.post("/mcp")
    assert resp.status_code == 401


async def test_authenticated_request_passes_auth_layer(client):
    # With a valid token the request is no longer rejected by auth (401);
    # the MCP layer may then return its own status for an incomplete handshake.
    resp = await client.post(
        "/mcp", headers={"Authorization": f"Bearer {CONFIG.bearer_token}"}
    )
    assert resp.status_code != 401


async def test_authenticated_request_not_blocked_by_host_check(client):
    # Regression: with no allowed_hosts configured, DNS-rebinding protection
    # must be OFF so a proxied (non-localhost) Host header does not yield 421.
    resp = await client.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {CONFIG.bearer_token}",
            "Host": "skills.codedancoffee.com",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "probe", "version": "0"},
            },
        },
    )
    assert resp.status_code != 421


@pytest.fixture()
async def hardened_client():
    cfg = Config(
        bearer_token="test-token",
        db_path=":memory:",
        host="127.0.0.1",
        port=8765,
        allowed_hosts=("skills.codedancoffee.com",),
    )
    app = build_app(cfg)
    async with LifespanManager(app) as managed:
        transport = httpx.ASGITransport(app=managed.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as ac:
            yield ac


def _init_payload():
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "probe", "version": "0"},
        },
    }


async def test_hardened_allows_configured_host(hardened_client):
    resp = await hardened_client.post(
        "/mcp",
        headers={
            "Authorization": "Bearer test-token",
            "Host": "skills.codedancoffee.com",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        json=_init_payload(),
    )
    assert resp.status_code != 421


async def test_hardened_rejects_unknown_host(hardened_client):
    resp = await hardened_client.post(
        "/mcp",
        headers={
            "Authorization": "Bearer test-token",
            "Host": "evil.example.com",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        json=_init_payload(),
    )
    assert resp.status_code == 421


def test_build_app_returns_callable():
    assert callable(build_app(CONFIG))
