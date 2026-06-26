"""End-to-end smoke test against a live server over Streamable HTTP.

Boots nothing itself — assumes the server is already running at $URL with
$TOKEN. Exercises the full runtime + authoring flow:
list -> register -> list -> get -> update -> get -> revert -> get.
"""

from __future__ import annotations

import asyncio
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = os.environ.get("SMOKE_URL", "http://127.0.0.1:8080/mcp")
TOKEN = os.environ["SKILLS_MCP_BEARER_TOKEN"]


def _structured(result):
    return result.structuredContent


async def main() -> None:
    headers = {"Authorization": f"Bearer {TOKEN}"}
    async with streamablehttp_client(URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("tools:", sorted(t.name for t in tools.tools))

            print("list (empty):", _structured(await session.call_tool("list_skills", {})))

            await session.call_tool(
                "register_skill",
                {"name": "deploy", "description": "How to deploy", "content": "v1 steps"},
            )
            print("list:", _structured(await session.call_tool("list_skills", {})))
            print("get v1:", _structured(await session.call_tool("get_skill", {"name": "deploy"})))

            await session.call_tool("update_skill", {"name": "deploy", "content": "v2 steps"})
            print("get v2:", _structured(await session.call_tool("get_skill", {"name": "deploy"})))

            await session.call_tool("revert_skill", {"name": "deploy"})
            print("get after revert:", _structured(await session.call_tool("get_skill", {"name": "deploy"})))

    print("SMOKE OK")


if __name__ == "__main__":
    asyncio.run(main())
