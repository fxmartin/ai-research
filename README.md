# ai-research

[![CI](https://github.com/fxmartin/ai-research/actions/workflows/ci.yml/badge.svg)](https://github.com/fxmartin/ai-research/actions/workflows/ci.yml)

A local, Claude Code-native implementation of Karpathy's [LLM-Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): an LLM incrementally builds and maintains an interconnected, Obsidian-compatible markdown vault from your raw sources so knowledge compounds instead of being re-derived.

> **Status:** pre-alpha. See [`docs/STORIES.md`](docs/STORIES.md) for the full roadmap and progress tracker.

---

## Why this exists

Traditional RAG stacks re-derive context from raw sources on every query. `ai-research` replaces that with a persistent, human-readable wiki that an LLM maintains for you. You drop sources in; the LLM writes summaries, cross-links concepts, and flags contradictions. The resulting `wiki/` is a plain Obsidian vault — portable, diff-able, and useful even if this project disappears.

See [`REQUIREMENTS.md`](REQUIREMENTS.md) for the full PRD.

## How it works

Three layers on local disk:

```
wiki/raw/  INBOX — drop new files here (Obsidian Web Clipper-compatible)
sources/   immutable archive of ingested inputs
wiki/      Obsidian-compatible markdown (wikilinks + frontmatter)
```

Two moving parts:

1. **`ai-research` Python toolkit** — deterministic file operations only. Zero LLM calls.
2. **Claude Code slash commands** in `.claude/commands/` — the product surface. Claude Code is the LLM runtime; slash commands compose the toolkit into user-visible capabilities.

## Prerequisites

- macOS (tested) or Linux.
- [`uv`](https://github.com/astral-sh/uv) for Python project + tool management.
- [Claude Code CLI](https://code.claude.com) on PATH, authenticated (`claude auth status`).
- `pdftotext` — `brew install poppler`.
- `rg` (ripgrep) — `brew install ripgrep`.
- Python 3.12+.
- Optional: [Obsidian](https://obsidian.md) to browse the `wiki/` vault.

## Install

Install the CLI globally as a `uv` tool:

```bash
git clone git@github.com:fxmartin/ai-research.git
cd ai-research
uv tool install .
```

Verify:

```bash
ai-research --help
claude --version
```

For development checkouts, use `uv tool install -e .` to install editable, or `uv sync` to manage an in-repo venv (see [Development](#development)).

## Quick start

Basic usage flow: **ingest → materialize → query**.

```bash
# 1. Drop a paper into the inbox
cp ~/Downloads/some-paper.pdf wiki/raw/

# 2. Ingest (interactive — /ingest-inbox runs extract → LLM draft → materialize)
claude                   # opens interactive Claude Code session
> /ingest-inbox

# ...or headless:
claude -p "/ingest-inbox"

# 3. Query the vault
claude -p "/ask 'what does this paper say about sparse attention?'"

# 4. Structured output for pipelines
claude -p "/ask 'summarize the key claim'" --output-format json | jq
```

Open `wiki/` in Obsidian to browse the graph.

## Capturing sources — Obsidian Web Clipper

The inbox lives **inside** the vault at `wiki/raw/` so that the [Obsidian Web Clipper](https://obsidian.md/clipper) (and any other Obsidian plugin or mobile-vault workflow that writes into the vault) can drop new sources straight into the ingest queue.

### Setup

1. Install Obsidian Web Clipper in your browser.
2. Open its settings and set **Vault** to the Obsidian vault for this project (the `wiki/` directory).
3. Under **Default folder** (or per-template), set the destination to `raw/` — relative to the vault root, so clippings land at `wiki/raw/`.
4. Clip a page. It appears as `wiki/raw/<title>.md`.
5. Drain the inbox:

   ```bash
   claude -p "/ingest-inbox"
   ```

Alternative capture paths — all land in the same inbox:

```bash
# Manual copy (any file: PDF, HTML, markdown, transcript)
cp ~/Downloads/paper.pdf wiki/raw/

# Drag-and-drop inside Obsidian (save into wiki/raw/)
# Mobile Obsidian with sync → writes into wiki/raw/ too
```

`wiki/raw/` is excluded from `vault-lint` and `index-rebuild`, so inbox clippings never pollute the published graph until `/ingest-inbox` promotes them. Inbox contents are git-ignored (see `.gitignore`); only `wiki/raw/.gitkeep` is tracked.

> **Migrating from an earlier checkout?** The inbox used to live at the repo-root `raw/`. If you have files there, move them: `mv raw/* wiki/raw/ && rmdir raw`. See [#27](https://github.com/fxmartin/ai-research/issues/27) for rationale.

## Invocation modes

Everything works three equivalent ways:

| Mode | When to use | Example |
|------|-------------|---------|
| **Interactive** | Exploring, iterating, asking follow-ups | Open `claude` and run `/ingest ./paper.pdf` |
| **Self-paced watcher** | Long session, drop files periodically | `claude` → `/loop 20m /ingest-inbox` |
| **Headless / scheduled** | Cron, launchd, CI, shell pipelines | `claude -p "/ingest-inbox"` |

## Slash commands

The product surface lives in `.claude/commands/`:

| Command | Purpose |
|---------|---------|
| `/ingest <path-or-url>` | Ingest one source → wiki page with `[[wikilinks]]` + concept stubs |
| `/ingest-inbox` | Drain `wiki/raw/` — ingest every eligible file, move raw→sources, rebuild index. Loop-safe |
| `/ask "<question>"` | Q&A over the wiki with citations. Returns `{answer, citations[], confidence}` JSON under `--output-format json` |

## Python toolkit verbs

The `ai-research` CLI is a deterministic, LLM-free file-ops toolkit. Slash commands compose these; you can also call them directly.

| Verb | Purpose | Example |
|------|---------|---------|
| `extract` | Extract text + metadata from PDF, URL, or markdown | `ai-research extract ./paper.pdf --json` |
| `archive` | Move an ingested source from `wiki/raw/` into the immutable `sources/<yyyy>/<mm>/` archive | `ai-research archive wiki/raw/paper.pdf` |
| `materialize` | Atomically write a wiki page from a draft + archive its source | `ai-research materialize --source sources/2026/04/abc-paper.pdf --from draft.md` |
| `index-rebuild` | Regenerate `.ai-research/index.md` retrieval surface from `wiki/` | `ai-research index-rebuild` |
| `scan` | List files in `wiki/raw/` eligible for ingest (skips too-fresh partials) | `ai-research scan wiki/raw/ --json` |
| `search` | `rg` over `wiki/` with structured JSON hits | `ai-research search "sparse attention" --json` |
| `vault-lint` | Obsidian smoke test — all wikilinks resolve, frontmatter parses | `ai-research vault-lint` |
| `ask-check` | Validate that `[[page-name]]` citations in an answer resolve to real pages | `ai-research ask-check answer.json` |
| `source lookup` | Reverse-lookup a wiki slug to its archived source bytes via `state.json` | `ai-research source lookup dario-amodei --json` |

All verbs support `--json` for stdout, exit non-zero on failure, and perform zero LLM calls.

## MCP server for Claude Desktop

`uv tool install .` exposes two console scripts on your `PATH`: the `ai-research` CLI and `ai-research-mcp`, a **read-only** [Model Context Protocol](https://modelcontextprotocol.io) server that speaks stdio. Claude Desktop (and any MCP-aware client) can spawn it as a subprocess to query the wiki directly from chat.

### Available tools

| Tool | Purpose |
|------|---------|
| `ask` | Answer a question from the wiki with `[[page-name]]` citations |
| `search` | Lexical `rg` search over `wiki/` — structured hits |
| `list_pages` | Enumerate wiki pages with title, tags, and 1-line summary |
| `get_page` | Fetch the full markdown of a single page by slug |

All four tools are read-only — the server cannot mutate the vault. Ingestion and edits stay in Claude Code + the CLI.

### Claude Desktop setup (≈60 seconds)

1. `uv tool install .` from the repo so `ai-research-mcp` is on your `PATH`.
2. Open `~/Library/Application Support/Claude/claude_desktop_config.json` (create the file if missing) and merge in:

   ```json
   {
     "mcpServers": {
       "ai-research": {
         "command": "ai-research-mcp",
         "env": {
           "AI_RESEARCH_ROOT": "/absolute/path/to/your/ai-research/repo"
         }
       }
     }
   }
   ```

3. Restart Claude Desktop. The four tools above should appear in the tool picker.

`AI_RESEARCH_ROOT` is an absolute path to the repo root (the directory containing `wiki/` and `.ai-research/`). Set it explicitly — Claude Desktop does not inherit a useful `cwd`.

For troubleshooting, env-var reference, and how to confirm the server is wired up, see [`docs/mcp-setup.md`](docs/mcp-setup.md). Full design: [Epic-06](docs/stories/epic-06-mcp-server.md).

## Retrieval mechanism (`/ask`)

Two stages, no vector DB in v1:

1. **Shortlist.** Claude Code reads `.ai-research/index.md` (one line per page: title · tags · H1 headings · 1-line summary · outbound-link count), plus an optional `ai-research search` lexical pre-filter for exact-term queries. Selects 3–8 candidates.
2. **Answer.** Reads the shortlisted pages' full markdown. Emits answer with `[[page-name]]` citations (interactive) or `{answer, citations[], confidence}` JSON (headless). `ai-research ask-check` validates the citations post-hoc.

Embeddings and graph-walk expansion are Phase-2.

## `/loop` compatibility smoke test

`/ingest-inbox` is designed to be driven by Claude Code's `/loop` harness at a
fixed interval, so a session can drain `wiki/raw/` itself. Use this manual
checklist after any change to `.claude/commands/ingest-inbox.md` or a verb it
composes.

Invocation:

```text
/loop 20m /ingest-inbox
```

Checklist (interactive `claude` session inside the repo):

- [ ] **Empty-inbox tick is clean.** With `wiki/raw/` empty, one tick reports
      `nothing to ingest` and does NOT mark the loop as failed.
- [ ] **Drop-and-drain.** Copy a PDF into `wiki/raw/`. Within the interval, the
      file appears under `sources/<yyyy>/<mm>/…` and a page in `wiki/`.
- [ ] **Idempotent repeat.** Next tick reports `nothing to ingest` (no
      duplicates — `--skip-known` is working).
- [ ] **Structured status each tick.** Stdout contains the
      `scanned:` / `ingested:` / `index:` block (or the `nothing to ingest`
      sentinel).
- [ ] **Partial failure doesn't abort the loop.** One good + one unsupported
      file: good ingests, bad is listed under `failures:`, loop continues.

If any step fails, re-run
`uv run pytest tests/test_slash_commands.py::TestLoopCompat` and inspect
`.claude/commands/ingest-inbox.md` for drift.

## Development

```bash
uv sync                    # install dev dependencies
uv run pytest              # unit + golden-file tests
uv run pytest --cov        # run tests with coverage reporting (threshold: 80%)
uv run pytest -m slow      # include the /ask JSON-contract harness (requires claude CLI)
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

All four gates (`ruff check`, `ruff format`, `pyright`, `pytest --cov`) run in GitHub Actions on every push and PR. See [![CI](https://github.com/fxmartin/ai-research/actions/workflows/ci.yml/badge.svg)](https://github.com/fxmartin/ai-research/actions/workflows/ci.yml) for live status.

See [`CLAUDE.md`](CLAUDE.md) for the testing strategy and story-management protocol. See [`docs/STORIES.md`](docs/STORIES.md) for the roadmap and to pick a story.

## Troubleshooting

**`pdftotext: command not found`** — `brew install poppler`.

**`rg: command not found`** — `brew install ripgrep`.

**`claude` CLI missing from launchd PATH** — launchd jobs don't inherit your shell's PATH. Set `PATH` explicitly in the plist `EnvironmentVariables`.

**`/ask` JSON drift** — re-pin the schema in `.claude/commands/ask.md` and re-run `tests/test_ask_contract.py`.

**Obsidian shows broken links** — run `ai-research vault-lint`, then `ai-research index-rebuild`.

**`wiki/raw/` isn't draining** — confirm Claude Code is running (interactive or via launchd/`claude -p`). Files younger than 5 seconds are skipped by design.

## Privacy

- All state is local. The Python toolkit makes **no** outbound network calls except explicit `extract` fetches against user-provided URLs.
- All LLM traffic is handled by Claude Code, which sends content to Anthropic.
- No telemetry from this project. See `NFR-SEC-001` in [`docs/stories/non-functional-requirements.md`](docs/stories/non-functional-requirements.md).

## Roadmap

Full detail in [`docs/STORIES.md`](docs/STORIES.md) and [`REQUIREMENTS.md`](REQUIREMENTS.md).

- **MVP** (Epics 01–04): PDF + URL + markdown ingest, cross-linking, `/ask`, Obsidian-clean vault, idempotent re-ingest, CI.
- **Phase 2** (Epic-05): YouTube transcripts, contradiction detection, `/status`, launchd agent template.
- **Epic-06**: read-only MCP server for Claude Desktop. See [`docs/mcp-threat-model.md`](docs/mcp-threat-model.md) for the read-only guarantee and threat model.

## License

[MIT](LICENSE) © 2026 FX Martin.

## Acknowledgements

- [Andrej Karpathy's LLM-Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — the seed idea.
- Vannevar Bush's 1945 [Memex](https://en.wikipedia.org/wiki/Memex) — the pattern, 80 years early.
- [Obsidian](https://obsidian.md) — the vault format that made this architecture obvious.
