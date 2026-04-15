# MCP Server Threat Model

Scope: `ai-research-mcp` — the local stdio MCP server shipped by this repo.
Audience: operators (FX, or anyone installing the server into Claude Desktop
or another MCP-aware client).

This document is deliberately short. The server is small, local, and
read-only by construction; the threats worth thinking about are small too.

## What the server exposes

The server speaks the Model Context Protocol over **stdio only**. It
advertises exactly four tools, all read-only:

- `ask` — two-stage Q&A; shells out to `claude -p "/ask ..." --output-format json`.
- `search` — ripgrep over `wiki/`; returns `{page, line, snippet}`.
- `list_pages` — structured view of `.ai-research/index.md`.
- `get_page` — full markdown of a page by slug.

Vault content reachable through the tools is whatever lives under
`wiki/` plus `.ai-research/index.md`.

## What the server does NOT expose

- No state mutation. No tool writes to the filesystem. This is enforced
  by `tests/test_mcp_readonly_guarantee.py` (hash every file before/after
  every tool call; assert byte-identical).
- No access to `sources/` through MCP. Raw sources remain a local-only
  concern of the ingestion pipeline.
- No `ingest`, no `materialize`, no `index-rebuild` — mutating verbs stay
  in the CLI + Claude Code surface, not MCP.
- No network socket. Transport is stdio; the server is spawned as a
  subprocess by the MCP client and exits with it.
- No authentication or authorization layer. The server trusts its parent
  process, period.

## Known limits and mitigations

### Path traversal via `get_page`
A naive `slug → wiki_dir/slug.md` join could read arbitrary files
(`../../etc/passwd`, `~/.ssh/config`). The tool rejects any slug that
does not match `^[a-z0-9][a-z0-9-]*$` and verifies the resolved path
sits inside the configured `wiki_dir` (defence-in-depth against symlink
shenanigans). Tests in `tests/test_mcp_tool_get_page.py` cover traversal
attempts.

### Ripgrep behaviour in `search`
`search` is a read-only ripgrep invocation rooted at `wiki_dir`. The
query is passed as a pattern argument, not interpolated into a shell,
so there is no command-injection surface. Ripgrep honours `.gitignore`
by default in the current config; nothing under `wiki/` should be
ignored, but operators should not place secrets under `wiki/` anyway.

### Subprocess boundary in `ask`
`ask` spawns `claude -p` with the question as an argv element (never
shell-interpolated). Claude Code is the LLM runtime; the MCP server
itself holds no API keys and makes no network calls. The subprocess
runs with the same user/environment as the MCP server. If `claude` is
absent from `PATH`, the tool returns a clean MCP error rather than
crashing.

### Prompt injection from vault content
Because wiki pages flow into the LLM context (via `ask` and any client
that reads `get_page`/`search` results), a page whose content says
"ignore previous instructions..." will reach the model. This is
accepted risk: FX curates the sources that become wiki pages, and the
server is single-user / local. Do not ingest untrusted content into
the wiki if this matters.

### Secrets in the vault
The server has no concept of access control — anything readable under
`wiki/` is readable to any MCP client spawned against this vault. Do
not commit secrets to the wiki.

## Operator guidance

- **Stdio only, never bind to a port.** The server has no network
  transport; do not wrap it in one. Remote access is a separate design
  problem out of scope for v1.
- **Pin the vault root explicitly.** Set `AI_RESEARCH_ROOT` in the
  Claude Desktop config snippet so the server cannot accidentally serve
  the wrong directory from the client's cwd.
- **Lock down `sources/` at the filesystem layer.** The MCP server does
  not touch `sources/`, but the directory holds immutable archives of
  raw material; permissions there are the operator's responsibility.
- **Trust the parent process.** Treat the MCP server's privileges as
  equal to whatever spawned it (Claude Desktop, a test harness, etc.).
- **Rebuild `.ai-research/index.md` via the CLI, not MCP.** Index
  regeneration is a mutating verb and intentionally absent from the MCP
  surface.

## Related

- NFR-SEC-001 — read-only MCP invariant.
- Story 06.2-004 — path-traversal defence in `get_page`.
- Story 06.3-002 — this document and the enforcing test.
