# Centralised Claude Skills MCP

A single, always-on MCP server that stores reusable Claude skills as plain
instruction text. Every Claude Code instance connects to it and reuses the
skills with **no local files, no sync step, and no client-side git
operations**. Skill authoring, updating, and registration all happen
server-side — and can be driven conversationally from inside Claude Code.

See the [implementation plan](https://wiki.tasmi.cloud/home/indie/centralised-claude-mcp/implementation-plan)
for the full design rationale.

## How it works

Progressive disclosure is reconstructed with two read tools:

1. At the start of a task, Claude calls `list_skills` → gets a lightweight
   index (name + one-line summary only).
2. On a match, Claude calls `get_skill(name)` → the full instruction text
   loads on demand.

Only the index is ever resident. Writes (`register_skill`, `update_skill`,
`revert_skill`) are append-only: every overwrite snapshots the prior version,
so mistakes are always recoverable.

## Tools

| Tool | Signature | Caller | Behaviour |
|---|---|---|---|
| `list_skills` | `() -> [{name, description}]` | Claude, at task start | Lightweight catalogue index. |
| `get_skill` | `(name) -> {name, content}` | Claude, on match | Full instruction text for one skill. |
| `register_skill` | `(name, description, content) -> {ok}` | You, conversationally | Creates a new skill; refuses on name collision. |
| `update_skill` | `(name, content) -> {ok}` | You, conversationally | Snapshots prior version, then overwrites. |
| `revert_skill` | `(name) -> {ok}` | You | Restores the most recent prior version. |

## Architecture

```
config (env, fail-fast)  ->  SQLite (skills + skill_versions, append-only)
        ->  SkillRepository  ->  FastMCP tools  ->  Streamable HTTP app
        ->  BearerAuthMiddleware  ->  ASGI (uvicorn)
```

- **Language:** Python 3.11+, official `mcp` SDK (no build step).
- **Transport:** Streamable HTTP (remote multi-machine access).
- **Storage:** SQLite single file (no DB server process; zero idle cost).
- **Auth:** shared bearer token, constant-time comparison.

## Browser viewer

A read-only web page for browsing skills and reading their markdown
instructions is served alongside the MCP endpoint:

- `GET /ui` — single-page viewer: a searchable list of skills; click one to
  read its instruction text rendered as markdown.
- `GET /api/skills` — JSON catalogue (`name` + `description`).
- `GET /api/skills/{name}` — JSON for one skill (includes full `content`).

The viewer is **read-only** (it exposes only `list`/`get`) and is served
**outside** bearer auth, so it opens in a browser with no token — while the
`/mcp` endpoint stays token-protected. Markdown is rendered and sanitised
client-side. Do not expose the deployment publicly if the skill content is
sensitive.

## Run locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env        # then edit SKILLS_MCP_BEARER_TOKEN
export $(grep -v '^#' .env | xargs)
python -m skills_mcp        # MCP on http://0.0.0.0:8765/mcp, viewer on /ui
```

### Configuration

| Env var | Required | Default | Notes |
|---|---|---|---|
| `SKILLS_MCP_BEARER_TOKEN` | **yes** | — | Server refuses to start without it. |
| `SKILLS_MCP_DB_PATH` | no | `./skills.db` | SQLite file path. |
| `SKILLS_MCP_HOST` | no | `0.0.0.0` | Bind address. |
| `SKILLS_MCP_PORT` | no | `8765` | Bind port. |

## Tests

```bash
pip install -e ".[dev]"
pytest            # unit + integration, coverage gate
```

A live end-to-end check (boot the server first, then):

```bash
SMOKE_URL=http://127.0.0.1:8765/mcp python scripts/smoke_test.py
```

## Deploy

### One-click: Docker Compose (recommended)

```bash
cp .env.example .env
# set SKILLS_MCP_BEARER_TOKEN in .env  (generate one: openssl rand -hex 32)

docker compose up -d --build
```

That's it. Compose builds the image, creates the `skills-data` volume, and
starts the server (with a healthcheck and `restart: unless-stopped`). It
listens on `http://localhost:8765/mcp` — change the published port with
`HOST_PORT` in `.env`.

```bash
docker compose logs -f        # follow logs
docker compose ps             # status (shows healthy)
docker compose down           # stop (keeps the volume / data)
docker compose down -v        # stop and delete the data volume
```

### Manual docker run

```bash
docker build -t skills-mcp .
docker run -d --name skills-mcp \
  -e SKILLS_MCP_BEARER_TOKEN=... \
  -v skills-data:/data \
  -p 8765:8765 \
  skills-mcp
```

Either way the SQLite file lives on the `skills-data` volume, so it survives
redeploys. Put this behind your reverse proxy / OAuth proxy to terminate TLS
for `https://skills.codedancoffee.com/mcp`; the container itself speaks plain
HTTP on 8765.

## Client setup (per machine, once)

1. Register the MCP server with the URL and bearer token:

   ```bash
   claude mcp add --transport http skills \
     https://skills.codedancoffee.com/mcp \
     --header "Authorization: Bearer <token>"
   ```

2. Add one standing line to `CLAUDE.md`:

   > At the start of any non-trivial task, call `list_skills` and load any
   > relevant skill with `get_skill` before proceeding.

No local skills directory. No pull. No git. Adding a new machine = repeat
these two steps.

## Authoring flow (the closed loop)

1. You and Claude work through a problem.
2. You land on a reusable procedure worth keeping.
3. Claude drafts the skill and presents the full text.
4. On your explicit confirmation, Claude calls `register_skill` (or
   `update_skill`).
5. Every other instance sees it on its next `list_skills` call. No redeploy,
   no file copy.
