"""Tests for the bearer-token ASGI middleware."""

from __future__ import annotations

import httpx
import pytest

from skills_mcp.auth import BearerAuthMiddleware

TOKEN = "s3cr3t-token"


async def _ok_app(scope, receive, send):
    """Minimal downstream app: 200 OK for any HTTP request."""
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"reached"})


@pytest.fixture()
def client():
    app = BearerAuthMiddleware(_ok_app, TOKEN)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_valid_token_passes_through(client):
    async with client:
        resp = await client.get("/mcp", headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 200
    assert resp.text == "reached"


async def test_missing_header_rejected(client):
    async with client:
        resp = await client.get("/mcp")
    assert resp.status_code == 401
    assert "bearer token" in resp.json()["error"]


async def test_wrong_token_rejected(client):
    async with client:
        resp = await client.get("/mcp", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid bearer token"


async def test_malformed_scheme_rejected(client):
    async with client:
        resp = await client.get("/mcp", headers={"Authorization": TOKEN})
    assert resp.status_code == 401


async def test_response_never_echoes_supplied_token(client):
    async with client:
        resp = await client.get(
            "/mcp", headers={"Authorization": "Bearer leak-me-please"}
        )
    assert "leak-me-please" not in resp.text


def test_empty_token_construction_refused():
    with pytest.raises(ValueError):
        BearerAuthMiddleware(_ok_app, "")
