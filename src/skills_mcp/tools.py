"""MCP tool definitions, layered over :class:`SkillRepository`.

The tool *descriptions* are a primary reliability lever (plan section 5):

* ``list_skills`` nudges Claude to consult the catalogue at task start — this
  reconstructs progressive disclosure that the native runtime gives to
  ``SKILL.md`` files.
* ``register_skill`` / ``update_skill`` instruct Claude to show the full draft
  and obtain explicit user confirmation before committing (write safety).
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

from .repository import (
    DuplicateSkillError,
    NoPriorVersionError,
    SkillNotFoundError,
    SkillRepository,
)

SERVER_NAME = "centralised-claude-skills"

_LIST_DESC = (
    "Returns the catalogue of available reusable skills (name + one-line "
    "summary only). Call this at the start of any non-trivial task to check "
    "for relevant guidance before proceeding."
)
_GET_DESC = (
    "Returns the full instruction text for one skill by name. Call this after "
    "list_skills when a catalogue entry matches the task at hand."
)
_REGISTER_DESC = (
    "Creates a NEW reusable skill from instruction text. Before calling, show "
    "the user the full proposed skill (name, description, and content) and "
    "obtain their explicit confirmation. Refuses if a skill with the same "
    "name already exists — use update_skill to change an existing skill."
)
_UPDATE_DESC = (
    "Overwrites the instruction text of an EXISTING skill, snapshotting the "
    "prior version to history first. Before calling, show the user the full "
    "proposed new content and obtain their explicit confirmation."
)
_REVERT_DESC = (
    "Restores the most recent prior version of a skill (undoes the last "
    "update). Confirm with the user before calling."
)


def create_mcp(
    repo: SkillRepository,
    transport_security: TransportSecuritySettings | None = None,
) -> FastMCP:
    """Build a FastMCP server exposing the five skill tools over ``repo``.

    ``transport_security`` configures DNS-rebinding (Host/Origin) protection.
    When omitted it defaults to *disabled*: this overrides FastMCP's implicit
    localhost-only default, which would otherwise reject the proxied public
    Host header with ``421 Misdirected Request`` behind nginx. Pass an explicit
    settings object (see ``server.build_app``) to allow-list specific hosts.
    """

    if transport_security is None:
        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        )
    mcp = FastMCP(SERVER_NAME, transport_security=transport_security)

    @mcp.tool(name="list_skills", description=_LIST_DESC)
    def list_skills() -> list[dict[str, str]]:
        return [
            {"name": s.name, "description": s.description} for s in repo.list()
        ]

    @mcp.tool(name="get_skill", description=_GET_DESC)
    def get_skill(name: str) -> dict[str, str]:
        try:
            skill = repo.get(name)
        except SkillNotFoundError:
            raise ToolError(f"No skill named {name!r}. Call list_skills to see options.")
        return {"name": skill.name, "content": skill.content}

    @mcp.tool(name="register_skill", description=_REGISTER_DESC)
    def register_skill(name: str, description: str, content: str) -> dict[str, bool]:
        try:
            repo.register(name, description, content)
        except DuplicateSkillError:
            raise ToolError(
                f"A skill named {name!r} already exists. Use update_skill to change it."
            )
        except ValueError as exc:
            raise ToolError(str(exc))
        return {"ok": True}

    @mcp.tool(name="update_skill", description=_UPDATE_DESC)
    def update_skill(name: str, content: str) -> dict[str, bool]:
        try:
            repo.update(name, content)
        except SkillNotFoundError:
            raise ToolError(
                f"No skill named {name!r}. Use register_skill to create it first."
            )
        except ValueError as exc:
            raise ToolError(str(exc))
        return {"ok": True}

    @mcp.tool(name="revert_skill", description=_REVERT_DESC)
    def revert_skill(name: str) -> dict[str, bool]:
        try:
            repo.revert(name)
        except SkillNotFoundError:
            raise ToolError(f"No skill named {name!r}.")
        except NoPriorVersionError:
            raise ToolError(f"Skill {name!r} has no prior version to revert to.")
        return {"ok": True}

    return mcp
