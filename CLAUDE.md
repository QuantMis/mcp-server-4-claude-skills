# Centralised Claude Skills MCP

MCP server storing reusable Claude skills as instruction text. See `README.md`
for full design and the [implementation plan](https://wiki.tasmi.cloud/home/indie/centralised-claude-mcp/implementation-plan).

## Working in this repo

- Source lives in `src/skills_mcp/` (src layout, installed editable).
- Layering: `config` → `db` → `repository` → `tools` → `server`. Only
  `repository.py` touches SQL; tools/transport depend on its interface.
- **Append-only versioning is an invariant** — every content overwrite must
  snapshot the prior version into `skill_versions` first. Never delete history.
- TDD: write the failing test first, then implement. Keep coverage ≥ 80%
  (`pytest` runs with `--cov`).

## Skill usage

At the start of any non-trivial task, call `list_skills` and load any relevant
skill with `get_skill` before proceeding.
