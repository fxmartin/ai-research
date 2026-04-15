# Epic 6: MCP Server for Claude Desktop

## Epic Overview
**Epic ID**: Epic-06
**Description**: A local **read-only** Model Context Protocol server (`ai-research-mcp`) that exposes the vault to Claude Desktop (and any MCP-aware client) via stdio. Ships four tools — `ask`, `search`, `list_pages`, `get_page` — implemented in Python using the official `mcp` SDK or FastMCP, composing the existing `ai-research` toolkit in-process. No mutations; `ingest`/edit stay in Claude Code + CLI.
**Business Value**: FX can query the wiki from Claude Desktop (richer chat UX, attachments, context packing) without switching to Claude Code. The vault becomes a first-class tool in any MCP-aware client, extending the Karpathy-premise test to another surface.
**Success Metrics**:
- Claude Desktop, after one JSON config edit, can answer a question using `ai-research-mcp` with citations.
- `list_pages` + `get_page` let Claude Desktop follow citations into page content without file-system access.
- Zero vault mutations possible from the MCP surface (enforced by design, verified by test).

## Epic Scope
**Total Stories**: 8 | **Total Points**: 19 | **MVP Stories**: 0 (P1 — ships after Epics 01–04)

---

## Features in This Epic

### Feature 06.1: MCP Server Skeleton

#### Stories

##### Story 06.1-001: Add `ai-research-mcp` entry point + MCP SDK dependency
**User Story**: As FX, I want a second console script `ai-research-mcp` in the same `uv` project that launches a stdio MCP server so Claude Desktop can spawn it as a subprocess.
**Priority**: Should Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** the repo **When** I run `uv tool install -e .` **Then** both `ai-research` and `ai-research-mcp` are on PATH.
- **Given** `ai-research-mcp` invoked with no args **When** it starts **Then** it speaks MCP over stdio (advertises server info, capabilities).
- **Given** MCP `initialize` handshake **When** client connects **Then** the server responds with the four tool definitions from this epic.

**Technical Notes**: Prefer the official `mcp` SDK; FastMCP acceptable if it simplifies. Package: `src/ai_research/mcp_server/`. No FastAPI. Stdio only.

**Definition of Done**:
- [ ] `[project.scripts]` declares `ai-research-mcp`.
- [ ] `mcp` added as dependency.
- [ ] Smoke test: spawn the binary, send `initialize`, assert response.

**Dependencies**: Epic-01 (Foundation)
**Risk Level**: Low

---

##### Story 06.1-002: Shared server bootstrap — schema, state, vault root
**User Story**: As FX, I want the MCP server to resolve the vault root from an env var (`AI_RESEARCH_ROOT`) or the current working directory and load `schema.toml` + `state.json` once at startup so every tool call is fast.
**Priority**: Should Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** `AI_RESEARCH_ROOT=/path/to/vault` **When** the server starts **Then** it resolves paths relative to that root.
- **Given** no env var and no vault at cwd **When** it starts **Then** it emits a clear MCP error on the first tool call (not a crash).
- **Given** a reload signal (SIGHUP) **When** received **Then** `state.json` + `index.md` are re-read.

**Technical Notes**: Keep state-handles pooled; tool handlers share them. No per-call disk re-read except for `index.md` when stale.

**Definition of Done**:
- [x] Bootstrap module + tests.

**Dependencies**: 06.1-001, 01.1-002
**Risk Level**: Low

---

### Feature 06.2: Read-Only Tools

#### Stories

##### Story 06.2-001: `ask` tool — Q&A with citations
**User Story**: As FX using Claude Desktop, I want an `ask` MCP tool that takes `{question: str}` and returns `{answer, citations[], confidence}` so I can query the wiki from any MCP-aware client.
**Priority**: Should Have
**Story Points**: 5

**Acceptance Criteria**:
- **Given** a populated vault **When** Claude Desktop calls `ask("what does paper X say about Y?")` **Then** the response matches the `AskResponse` contract from `src/ai_research/contracts.py` (reused from `/ask`).
- **Given** the server runs `ask` **When** it does retrieval **Then** it uses the SAME two-stage logic as `/ask` (index.md shortlist → read pages → answer) to keep behavior consistent across surfaces.
- **Given** a question with zero good matches **When** `ask` runs **Then** confidence ≤ 0.2 and answer explicitly says the vault is insufficient.
- **Given** the answer **When** returned **Then** every `[[page-name]]` citation resolves via `ai-research validate-citations`.

**Technical Notes**: Key architectural question — **how does the MCP server do the LLM call?** Two options: (A) the MCP process itself calls Anthropic SDK (breaks the "no SDK in toolkit" rule but scoped to this binary only); (B) the server shells out to `claude -p "/ask ..." --output-format json`. Option B keeps the vendor-lock-in story coherent. Pick B for v1; document the per-call subprocess cost trade in the README. If latency hurts, revisit.

**Definition of Done**:
- [x] `ask` tool registered; schema exposed via MCP `tools/list`.
- [x] Contract-level test against a fixture vault (slow, nightly).
- [x] Citation-integrity test.

**Dependencies**: 06.1-001, 06.1-002, 03.3-001 (`/ask` slash command), NFR-SCR-001
**Risk Level**: High — latency via `claude -p` subprocess; drift risk if slash command evolves.

---

##### Story 06.2-002: `search` tool — lexical hits
**User Story**: As FX using Claude Desktop, I want a `search` MCP tool that takes `{query: str, limit?: int}` and returns a list of `{page, line, snippet}` so Claude can do its own retrieval when helpful.
**Priority**: Should Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** a populated vault **When** `search("foo")` is called **Then** response is a JSON list of hits (default limit 20).
- **Given** `rg` missing from PATH **When** `search` runs **Then** it returns an MCP error with a clear message.
- **Given** `limit: 5` **When** `search` runs **Then** at most 5 hits are returned.

**Technical Notes**: Thin wrapper around `ai-research search --json`. No LLM call. Instant.

**Definition of Done**:
- [ ] Tool + unit test.

**Dependencies**: 01.3-002, 06.1-001
**Risk Level**: Low

---

##### Story 06.2-003: `list_pages` tool — index summary
**User Story**: As FX using Claude Desktop, I want a `list_pages` MCP tool that returns a compact list of `{slug, title, tags, summary}` (from `index.md`) so Claude can decide what to read without re-deriving the index.
**Priority**: Should Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** a populated vault **When** `list_pages()` is called **Then** the response mirrors `.ai-research/index.md` rows as JSON.
- **Given** `list_pages({tag: "arxiv"})` **When** called **Then** only pages tagged `arxiv` are returned.
- **Given** `list_pages({prefix: "concepts/"})` **When** called **Then** only pages under that path prefix are returned.

**Technical Notes**: Parse `index.md` once per start, cache; invalidate when mtime changes.

**Definition of Done**:
- [x] Tool + unit test with fixture index.

**Dependencies**: 02.2-001, 06.1-002
**Risk Level**: Low

---

##### Story 06.2-004: `get_page` tool — full-page fetch
**User Story**: As FX using Claude Desktop, I want a `get_page` MCP tool that takes `{slug: str}` and returns `{frontmatter, body, outbound_links}` so Claude can follow a citation into the actual page content.
**Priority**: Should Have
**Story Points**: 3

**Acceptance Criteria**:
- **Given** an existing slug **When** `get_page("paper-x")` is called **Then** response is `{frontmatter, body, outbound_links[]}`.
- **Given** a missing slug **When** called **Then** an MCP error is returned, not an empty success.
- **Given** a slug with `..` or an absolute path **When** called **Then** it is rejected as invalid (path-traversal defence).
- **Given** a stub page **When** fetched **Then** frontmatter `stub: true` is surfaced so Claude knows the page is skeletal.

**Technical Notes**: Path-traversal check is critical — read-only status does not protect you from reading `~/.ssh/config` if slug joining is naive. Enforce slug regex `^[a-z0-9][a-z0-9-/]*$` and that the resolved path is within `wiki/`.

**Definition of Done**:
- [x] Tool + unit tests including path-traversal attempts.

**Dependencies**: 06.1-002
**Risk Level**: Medium — path traversal is the one place read-only can still leak data.

---

### Feature 06.3: Integration & Docs

#### Stories

##### Story 06.3-001: Claude Desktop config recipe + README section
**User Story**: As FX, I want a copy-pasteable `claude_desktop_config.json` snippet and a README section so installing the MCP into Claude Desktop takes under 2 minutes.
**Priority**: Should Have
**Story Points**: 1

**Acceptance Criteria**:
- **Given** the README "MCP for Claude Desktop" section **When** I follow the steps **Then** restarting Claude Desktop surfaces `ai-research-mcp` tools in the tool picker.
- **Given** the snippet **When** I copy it **Then** it sets `AI_RESEARCH_ROOT` explicitly so the server always knows which vault to serve.
- **Given** a troubleshooting subsection **When** I hit "server not appearing" **Then** the debug steps (check logs at `~/Library/Logs/Claude/mcp-server-ai-research.log`) are documented.

**Technical Notes**: Snippet format:
```json
{
  "mcpServers": {
    "ai-research": {
      "command": "ai-research-mcp",
      "env": { "AI_RESEARCH_ROOT": "/Users/fxmartin/dev/ai-research" }
    }
  }
}
```

**Definition of Done**:
- [ ] README updated.
- [ ] One successful manual end-to-end test with Claude Desktop.

**Dependencies**: 06.1-001, 06.2-001..004
**Risk Level**: Low

---

##### Story 06.3-002: Read-only guarantee — test + documented threat model
**User Story**: As FX, I want a test that asserts NO tool can write anywhere under `wiki/`, `sources/`, `wiki/raw/`, or `.ai-research/`, and a short threat-model note in the README, so "read-only" is a guarantee, not a habit.
**Priority**: Should Have
**Story Points**: 2

**Acceptance Criteria**:
- **Given** the server **When** the test suite exercises every tool **Then** no file under the vault has its mtime modified afterwards.
- **Given** a fuzzed input for `get_page` (path traversal, nulls, symlink attempts) **When** sent **Then** the server rejects and emits no writes.
- **Given** the README threat model **When** I read it **Then** it calls out: read-only scope, path-traversal defence, prompt-injection risk from wiki content reaching Claude Desktop (and that this is acceptable because FX curates sources).

**Technical Notes**: Use a read-only bind-mount or mtime snapshot in the test harness; cross-reference NFR-SEC-001.

**Definition of Done**:
- [ ] Read-only test passes in CI.
- [ ] Threat-model section in README.

**Dependencies**: All Feature 06.2 stories
**Risk Level**: Medium

---

## Out of Scope for Epic-06

- `ingest` / mutation tools from Claude Desktop. Reconsider only after a confirmation-UX story.
- HTTP / SSE transport. Stdio is sufficient for Claude Desktop; remote access is a separate design problem.
- Multi-vault support (serving several vault roots from one server). Env var picks one.
- Authentication / authorization. The server is local, single-user, spawned by Claude Desktop.
- Pushing resources (MCP `resources/` concept). Tools-only v1.

---

## Epic Progress

- [ ] Story 06.1-001 (2 pts)
- [x] Story 06.1-002 (2 pts)
- [x] Story 06.2-001 (5 pts)
- [x] Story 06.2-002 (2 pts)
- [ ] Story 06.2-003 (2 pts)
- [x] Story 06.2-004 (3 pts)
- [ ] Story 06.3-001 (1 pt)
- [ ] Story 06.3-002 (2 pts)

**Completed**: 1 / 8 stories · 5 / 19 pts.
