"""Tests for the read-only browser UI.

The viewer exposes only the repository's read paths (list/get) and is mounted
outside bearer auth (see tests/test_server.py for the auth-boundary assertions).
Here we test the routes in isolation against a repository fixture.
"""

from __future__ import annotations

import httpx
import pytest

from skills_mcp.web import create_web_app


@pytest.fixture()
async def web_client(repo):
    repo.register("alpha", "First skill", "# Alpha\n\nDo the thing.", tags=["ops"])
    repo.register("beta", "Second skill", "## Beta steps")
    app = create_web_app(repo)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_index_serves_html(web_client):
    resp = await web_client.get("/ui")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Skills" in resp.text


async def test_api_list_returns_summaries_only(web_client):
    resp = await web_client.get("/api/skills")
    assert resp.status_code == 200
    data = resp.json()
    assert {d["name"] for d in data} == {"alpha", "beta"}
    # the index stays lightweight — no content leaks into the list
    assert all("content" not in d for d in data)


async def test_api_get_returns_full_content(web_client):
    resp = await web_client.get("/api/skills/alpha")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "alpha"
    assert data["description"] == "First skill"
    assert "Do the thing." in data["content"]
    assert "updated_at" in data


async def test_api_get_unknown_returns_404(web_client):
    resp = await web_client.get("/api/skills/does-not-exist")
    assert resp.status_code == 404
    assert "error" in resp.json()


async def test_api_list_includes_tags(web_client):
    resp = await web_client.get("/api/skills")
    tags = {d["name"]: d["tags"] for d in resp.json()}
    assert tags == {"alpha": ["ops"], "beta": []}


async def test_api_get_includes_tags(web_client):
    resp = await web_client.get("/api/skills/alpha")
    assert resp.json()["tags"] == ["ops"]
