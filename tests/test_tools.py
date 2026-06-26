"""Integration tests for the MCP tool layer, exercised via FastMCP.call_tool.

call_tool returns a ``(content_blocks, structured_result)`` tuple. For tools
that return a list, the structured payload is wrapped as ``{"result": [...]}``;
for dict-returning tools it is the dict itself.
"""

from __future__ import annotations

import pytest

from mcp.server.fastmcp.exceptions import ToolError

from skills_mcp.repository import SkillRepository
from skills_mcp.tools import create_mcp


@pytest.fixture()
def mcp(repo: SkillRepository):
    return create_mcp(repo)


async def _structured(mcp, name, args):
    _content, structured = await mcp.call_tool(name, args)
    return structured


# ----------------------------------------------------------------- read tools
async def test_list_skills_returns_index(mcp, repo):
    repo.register("alpha", "Alpha summary", "alpha body")
    repo.register("beta", "Beta summary", "beta body")

    result = (await _structured(mcp, "list_skills", {}))["result"]

    assert result == [
        {"name": "alpha", "description": "Alpha summary"},
        {"name": "beta", "description": "Beta summary"},
    ]


async def test_list_skills_empty(mcp):
    assert (await _structured(mcp, "list_skills", {}))["result"] == []


async def test_get_skill_returns_full_content(mcp, repo):
    repo.register("alpha", "Alpha summary", "the full body")

    result = await _structured(mcp, "get_skill", {"name": "alpha"})

    assert result == {"name": "alpha", "content": "the full body"}


async def test_get_skill_missing_raises_tool_error(mcp):
    with pytest.raises(ToolError):
        await mcp.call_tool("get_skill", {"name": "ghost"})


# ---------------------------------------------------------------- write tools
async def test_register_skill_creates(mcp, repo):
    result = await _structured(
        mcp, "register_skill", {"name": "new", "description": "d", "content": "c"}
    )

    assert result == {"ok": True}
    assert repo.get("new").content == "c"


async def test_register_duplicate_raises(mcp, repo):
    repo.register("dup", "d", "c")
    with pytest.raises(ToolError):
        await mcp.call_tool(
            "register_skill", {"name": "dup", "description": "d2", "content": "c2"}
        )


async def test_register_blank_field_raises(mcp):
    with pytest.raises(ToolError):
        await mcp.call_tool(
            "register_skill", {"name": "x", "description": "d", "content": "   "}
        )


async def test_update_skill_overwrites(mcp, repo):
    repo.register("note", "d", "v1")

    result = await _structured(mcp, "update_skill", {"name": "note", "content": "v2"})

    assert result == {"ok": True}
    assert repo.get("note").content == "v2"
    assert [v.content for v in repo.history("note")] == ["v1"]


async def test_update_missing_raises(mcp):
    with pytest.raises(ToolError):
        await mcp.call_tool("update_skill", {"name": "ghost", "content": "x"})


async def test_update_blank_content_raises(mcp, repo):
    repo.register("note", "d", "v1")
    with pytest.raises(ToolError):
        await mcp.call_tool("update_skill", {"name": "note", "content": "   "})


async def test_revert_skill_restores(mcp, repo):
    repo.register("note", "d", "v1")
    repo.update("note", "v2")

    result = await _structured(mcp, "revert_skill", {"name": "note"})

    assert result == {"ok": True}
    assert repo.get("note").content == "v1"


async def test_revert_without_history_raises(mcp, repo):
    repo.register("note", "d", "v1")
    with pytest.raises(ToolError):
        await mcp.call_tool("revert_skill", {"name": "note"})


async def test_revert_missing_raises(mcp):
    with pytest.raises(ToolError):
        await mcp.call_tool("revert_skill", {"name": "ghost"})


# ----------------------------------------------------- descriptions (the lever)
async def test_all_five_tools_are_registered(mcp):
    names = {t.name for t in await mcp.list_tools()}
    assert names == {
        "list_skills",
        "get_skill",
        "register_skill",
        "update_skill",
        "revert_skill",
    }


async def test_list_skills_description_prompts_task_start_usage(mcp):
    tool = next(t for t in await mcp.list_tools() if t.name == "list_skills")
    assert "start of any non-trivial task" in tool.description


@pytest.mark.parametrize("tool_name", ["register_skill", "update_skill"])
async def test_write_tool_descriptions_require_confirmation(mcp, tool_name):
    tool = next(t for t in await mcp.list_tools() if t.name == tool_name)
    assert "confirmation" in tool.description.lower()
