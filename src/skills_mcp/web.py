"""Read-only browser UI for viewing skills.

Mounted *outside* bearer auth (see ``server.build_app``) so a plain browser can
load it without an ``Authorization`` header. It exposes only the repository's
read paths — :meth:`SkillRepository.list` and :meth:`SkillRepository.get` — and
never any write path. Markdown is rendered and sanitised client-side.

Routes:
* ``GET /ui``                  — the single-page viewer (HTML shell).
* ``GET /api/skills``          — lightweight catalogue (name, description, tags).
* ``GET /api/skills/{name}``   — full skill (name, description, content, timestamp, tags).
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from .repository import SkillNotFoundError, SkillRepository


def create_web_app(repo: SkillRepository) -> Starlette:
    """Build the read-only viewer app backed by ``repo``."""

    async def index(_request: Request) -> Response:
        return HTMLResponse(_PAGE)

    async def api_list(_request: Request) -> Response:
        return JSONResponse(
            [
                {"name": s.name, "description": s.description, "tags": list(s.tags)}
                for s in repo.list()
            ]
        )

    async def api_get(request: Request) -> Response:
        name = request.path_params["name"]
        try:
            skill = repo.get(name)
        except SkillNotFoundError:
            return JSONResponse(
                {"error": f"No skill named {name!r}"}, status_code=404
            )
        return JSONResponse(
            {
                "name": skill.name,
                "description": skill.description,
                "content": skill.content,
                "updated_at": skill.updated_at,
                "tags": list(skill.tags),
            }
        )

    return Starlette(
        routes=[
            Route("/ui", index, methods=["GET"]),
            Route("/api/skills", api_list, methods=["GET"]),
            Route("/api/skills/{name:path}", api_get, methods=["GET"]),
        ]
    )


# --------------------------------------------------------------------------- UI
# Self-contained single page. Markdown is rendered with marked and sanitised
# with DOMPurify (both from a pinned CDN) before insertion, so untrusted skill
# content cannot inject active markup.
_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Skills</title>
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.1.6/dist/purify.min.js"></script>
<style>
  :root {
    --bg: #0f1115; --panel: #171a21; --border: #262b36; --text: #e6e9ef;
    --muted: #9aa4b2; --accent: #6ea8fe; --code-bg: #1e232c;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI",
    Roboto, Helvetica, Arial, sans-serif; color: var(--text);
    background: var(--bg); display: flex; height: 100vh; overflow: hidden;
  }
  aside {
    width: 320px; flex: 0 0 320px; border-right: 1px solid var(--border);
    background: var(--panel); display: flex; flex-direction: column;
  }
  aside header { padding: 18px 20px 12px; border-bottom: 1px solid var(--border); }
  aside header h1 { margin: 0; font-size: 18px; }
  aside header p { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
  #search {
    margin: 12px 16px; padding: 8px 10px; width: calc(100% - 32px);
    background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
    color: var(--text); font-size: 13px;
  }
  #tagbar { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 16px 10px; }
  .tag {
    display: inline-block; padding: 1px 8px; border-radius: 999px;
    border: 1px solid var(--border); background: var(--code-bg);
    color: var(--muted); font-size: 11px; cursor: pointer; user-select: none;
  }
  .tag.active { border-color: var(--accent); color: var(--accent); }
  #list { list-style: none; margin: 0; padding: 0 8px 16px; overflow-y: auto; }
  #list li {
    padding: 10px 12px; border-radius: 8px; cursor: pointer; margin-bottom: 2px;
  }
  #list li:hover { background: var(--code-bg); }
  #list li.active { background: #223052; }
  #list li .name { font-weight: 600; }
  #list li .desc {
    color: var(--muted); font-size: 12px; margin-top: 2px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  #list li .tags { margin-top: 4px; display: flex; flex-wrap: wrap; gap: 4px; }
  #list li .tags .tag { cursor: default; }
  main { flex: 1; overflow-y: auto; padding: 32px 40px; }
  main .meta { color: var(--muted); font-size: 12px; margin-bottom: 20px; }
  #content { max-width: 820px; }
  #content h1, #content h2, #content h3 { line-height: 1.3; }
  #content pre {
    background: var(--code-bg); padding: 14px 16px; border-radius: 8px;
    overflow-x: auto; border: 1px solid var(--border);
  }
  #content code { background: var(--code-bg); padding: 1px 5px; border-radius: 4px; }
  #content pre code { background: none; padding: 0; }
  #content table { border-collapse: collapse; }
  #content th, #content td { border: 1px solid var(--border); padding: 6px 10px; }
  #content a { color: var(--accent); }
  .placeholder { color: var(--muted); margin-top: 15vh; text-align: center; }
</style>
</head>
<body>
<aside>
  <header>
    <h1>Skills</h1>
    <p>Read-only viewer</p>
  </header>
  <input id="search" type="search" placeholder="Filter skills…" autocomplete="off">
  <div id="tagbar"></div>
  <ul id="list"></ul>
</aside>
<main>
  <div class="meta" id="meta"></div>
  <div id="content"><p class="placeholder">Select a skill to view its instructions.</p></div>
</main>
<script>
  const listEl = document.getElementById('list');
  const searchEl = document.getElementById('search');
  const tagbarEl = document.getElementById('tagbar');
  const contentEl = document.getElementById('content');
  const metaEl = document.getElementById('meta');
  let skills = [];
  let active = null;
  let activeTag = null;

  function renderTagbar() {
    tagbarEl.innerHTML = '';
    const tags = [...new Set(skills.flatMap(s => s.tags || []))].sort();
    for (const tag of tags) {
      const el = document.createElement('span');
      el.className = 'tag' + (tag === activeTag ? ' active' : '');
      el.textContent = tag;
      el.addEventListener('click', () => {
        activeTag = tag === activeTag ? null : tag;
        renderTagbar();
        render(filtered());
      });
      tagbarEl.appendChild(el);
    }
  }

  function render(items) {
    listEl.innerHTML = '';
    if (!items.length) {
      const li = document.createElement('li');
      li.textContent = 'No skills found';
      li.style.color = 'var(--muted)';
      listEl.appendChild(li);
      return;
    }
    for (const s of items) {
      const li = document.createElement('li');
      li.dataset.name = s.name;
      if (s.name === active) li.classList.add('active');
      const name = document.createElement('div');
      name.className = 'name';
      name.textContent = s.name;
      const desc = document.createElement('div');
      desc.className = 'desc';
      desc.textContent = s.description || '';
      li.append(name, desc);
      if ((s.tags || []).length) {
        const tags = document.createElement('div');
        tags.className = 'tags';
        for (const tag of s.tags) {
          const chip = document.createElement('span');
          chip.className = 'tag';
          chip.textContent = tag;
          tags.appendChild(chip);
        }
        li.appendChild(tags);
      }
      li.addEventListener('click', () => open(s.name));
      listEl.appendChild(li);
    }
  }

  async function open(name) {
    active = name;
    render(filtered());
    metaEl.textContent = 'Loading…';
    contentEl.innerHTML = '';
    try {
      const resp = await fetch('/api/skills/' + encodeURIComponent(name));
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const skill = await resp.json();
      const tagSuffix = (skill.tags || []).length ? '  ·  ' + skill.tags.join(', ') : '';
      metaEl.textContent = skill.description + tagSuffix + '  ·  updated ' + skill.updated_at;
      const html = marked.parse(skill.content || '');
      contentEl.innerHTML = DOMPurify.sanitize(html);
    } catch (err) {
      metaEl.textContent = '';
      contentEl.innerHTML = '<p class="placeholder">Failed to load: ' + err.message + '</p>';
    }
  }

  function filtered() {
    const q = searchEl.value.trim().toLowerCase();
    let items = skills;
    if (activeTag) items = items.filter(s => (s.tags || []).includes(activeTag));
    if (!q) return items;
    return items.filter(s =>
      s.name.toLowerCase().includes(q) ||
      (s.description || '').toLowerCase().includes(q) ||
      (s.tags || []).some(t => t.includes(q)));
  }

  searchEl.addEventListener('input', () => render(filtered()));

  async function load() {
    try {
      const resp = await fetch('/api/skills');
      skills = await resp.json();
      renderTagbar();
      render(skills);
    } catch (err) {
      listEl.innerHTML = '<li style="color:var(--muted)">Failed to load skills</li>';
    }
  }
  load();
</script>
</body>
</html>
"""
