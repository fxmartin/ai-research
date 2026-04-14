# ai-research

A local, Claude Code-native implementation of Karpathy's [LLM-Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): an LLM incrementally builds and maintains an interconnected, Obsidian-compatible markdown vault from your raw sources so knowledge compounds instead of being re-derived.

> **Status:** pre-alpha. Requirements and backlog are defined; implementation begins at Story 01.1-001. See [`docs/STORIES.md`](docs/STORIES.md) for progress.

---

## Why this exists

Traditional RAG stacks re-derive context from raw sources on every query. `ai-research` replaces that with a persistent, human-readable wiki that an LLM maintains for you. You drop sources in; the LLM writes summaries, cross-links concepts, and flags contradictions. The resulting `wiki/` is a plain Obsidian vault — portable, diff-able, and useful even if this project disappears.

See [`REQUIREMENTS.md`](REQUIREMENTS.md) for the full PRD.

## How it works

Three layers on local disk:

```
raw/       INBOX — drop new files here
sources/   immutable archive of ingested inputs
wiki/      Obsidian-compatible markdown (wikilinks + frontmatter)
```

Two moving parts:

1. **`ai-research` Python toolkit** — deterministic file operations only. Zero LLM calls. Verbs: `extract`, `materialize`, `index-rebuild`, `search`, `scan`.
2. **Claude Code slash commands** in `.claude/commands/` — the product surface. `/ingest`, `/ingest-inbox`, `/ask`, `/status`. Claude Code is the LLM runtime. Slash commands compose the toolkit into user-visible capabilities.

A later epic ([Epic-06](docs/stories/epic-06-mcp-server.md)) adds a read-only MCP server so Claude Desktop can query the same vault.

## Prerequisites

- macOS (tested) or Linux.
- [`uv`](https://github.com/astral-sh/uv) for Python project + tool management.
- [Claude Code CLI](https://code.claude.com) on PATH, authenticated (`claude auth status`).
- `pdftotext` — `brew install poppler`.
- `rg` (ripgrep) — `brew install ripgrep`.
- Python 3.12+.
- Optional: [Obsidian](https://obsidian.md) to browse the `wiki/` vault.

## Install

```bash
git clone git@github.com:fxmartin/ai-research.git
cd ai-research
uv tool install -e .
```

Verify:

```bash
ai-research --help
claude --version
```

## Quick start

```bash
# Drop a paper into the inbox
cp ~/Downloads/some-paper.pdf raw/

# Drain the inbox (interactive — opens Claude Code in this repo first)
claude          # opens interactive session
> /ingest-inbox

# ...or headless, no session needed:
claude -p "/ingest-inbox"

# Ask the vault
claude -p "/ask 'what does this paper say about sparse attention?'"

# Ask with structured output for pipelines
claude -p "/ask 'summarize the key claim'" --output-format json | jq
```

Open `wiki/` in Obsidian to browse the graph.

## Invocation modes

Everything works three ways:

| Mode | When to use | Example |
|------|-------------|---------|
| **Interactive** | Exploring, iterating, asking follow-ups | Open `claude` and run `/ingest ./paper.pdf` |
| **Self-paced watcher** | You're working, drop files periodically | `claude` → `/loop 20m /ingest-inbox` |
| **Headless / scheduled** | Cron, launchd, CI, shell pipelines | `claude -p "/ingest-inbox"` |

## Commands

### Slash commands (product surface)

| Command | Purpose |
|---------|---------|
| `/ingest <path-or-url>` | Ingest one source → wiki page with `[[wikilinks]]` + concept stubs |
| `/ingest-inbox` | Drain `raw/` — ingest each file, move raw→sources, rebuild index |
| `/ask "<question>"` | Q&A over the wiki with citations. JSON contract under `--output-format json` |
| `/status` | Vault stats: pages, stubs, orphans, open contradictions (P1 — Epic-05) |

### Python toolkit verbs (composed by slash commands; usable directly)

| Verb | Purpose |
|------|---------|
| `ai-research extract <path-or-url>` | Extract text + metadata from PDF, URL, markdown, or YouTube (P1) |
| `ai-research materialize --source <src> --from <draft.md>` | Atomically write a wiki page + move source into archive |
| `ai-research index-rebuild` | Regenerate `.ai-research/index.md` retrieval index from `wiki/` |
| `ai-research search "<query>"` | `rg` over `wiki/` with structured JSON hits |
| `ai-research scan raw/` | List files eligible for ingest (skips too-fresh partials) |
| `ai-research vault-lint` | Obsidian smoke test — wikilinks resolve, frontmatter parses |
| `ai-research validate-citations` | Ensure `[[page-name]]` citations in an answer resolve to real pages |

All toolkit verbs support `--json` for stdout, exit non-zero on failure, and perform zero LLM calls.

## Retrieval mechanism (`/ask`)

Two stages, no vector DB in v1:

1. **Shortlist.** Claude Code reads `.ai-research/index.md` (one line per wiki page: title · tags · H1 headings · 1-line summary · outbound-link count), plus an optional `rg` lexical pre-filter for exact-term queries. Selects 3–8 candidate pages.
2. **Answer.** Reads the shortlisted pages' full markdown. Emits answer with `[[page-name]]` citations (interactive) or JSON `{answer, citations[], confidence}` (headless).

Embeddings and graph-walk expansion (traverse `[[wikilinks]]` 1–2 hops) are [P2](docs/stories/epic-06-mcp-server.md).

## Layout

```
ai-research/
├── src/ai_research/              # Python toolkit (no LLM calls)
│   ├── cli.py                    # Typer entry point
│   ├── extract/                  # pdf, web, markdown, youtube (P1)
│   ├── wiki/                     # page CRUD, frontmatter, atomic writes
│   ├── index/                    # index.md rebuild
│   ├── search/                   # rg wrapper
│   ├── materialize/              # page write + raw→sources archival
│   ├── state.py                  # state.json + source-hash registry
│   ├── contracts.py              # Pydantic models for JSON contracts
│   └── mcp_server/               # P1 — Epic-06
├── .claude/commands/             # slash commands (product surface)
├── raw/                          # INBOX (gitignored)
├── sources/                      # immutable archive (gitignored)
├── wiki/                         # Obsidian vault (gitignored scratch; treat as personal)
├── .ai-research/
│   ├── schema.toml               # wiki structure + page templates
│   ├── state.json                # source hashes + page index
│   └── index.md                  # retrieval surface for /ask
├── docs/
│   ├── STORIES.md                # epic navigation
│   └── stories/                  # epic files + NFRs
├── tests/
├── REQUIREMENTS.md
├── PROJECT-SEED.md
├── CLAUDE.md
└── pyproject.toml
```

## Privacy

- All state is local. The Python toolkit makes **no** outbound network calls except explicit `extract` fetches against user-provided URLs.
- All LLM traffic is handled by Claude Code, which sends content to Anthropic. Your `wiki/` pages (and any source text Claude needs to draft or answer) are sent to Anthropic on demand.
- No telemetry from this project. See `NFR-SEC-001` in [`docs/stories/non-functional-requirements.md`](docs/stories/non-functional-requirements.md).

## Development

```bash
uv sync                    # install dev dependencies
uv run pytest              # unit + golden-file tests
uv run pytest -m slow      # include the /ask JSON-contract harness (requires claude CLI)
uv run ruff check .
uv run pyright
```

See [`CLAUDE.md`](CLAUDE.md) for the testing strategy, CI, and story-management protocol. See [`docs/STORIES.md`](docs/STORIES.md) to pick a story.

## Troubleshooting

**`pdftotext: command not found`** — `brew install poppler`.

**`rg: command not found`** — `brew install ripgrep`.

**`claude` CLI missing from launchd agent PATH** — launchd jobs don't inherit your shell's PATH. Set `PATH` explicitly in the plist `EnvironmentVariables`.

**`/ask` JSON isn't valid** — the `/ask` slash command asks Claude for a strict schema. If you see drift, update `.claude/commands/ask.md` to re-pin the schema and re-run the harness test (`tests/test_ask_contract.py`).

**Obsidian shows broken links** — run `ai-research vault-lint`. A broken wikilink usually means a page was renamed manually and `state.json` wasn't updated — regenerate it with `ai-research index-rebuild`.

**`raw/` isn't draining** — check that Claude Code is actually running (interactive session open or a launchd agent firing `claude -p "/ingest-inbox"`). Files younger than 5 seconds are intentionally skipped; wait or adjust `--min-age-seconds`.

## Roadmap

- **MVP** (Epics 01–04, 30 stories / 69 pts): PDF + URL + markdown ingest, cross-linking, `/ask`, Obsidian-clean vault, idempotent re-ingest, CI.
- **Phase 2** (Epic-05, 6 stories / 17 pts): YouTube transcripts, contradiction detection, `/status`, launchd agent template.
- **Epic-06** (8 stories / 19 pts): read-only MCP server for Claude Desktop.
- **Backlog**: embeddings upgrade behind same `/ask` interface, FastAPI surface, OpenAI/Ollama provider fallback.

Full detail in [`docs/STORIES.md`](docs/STORIES.md) and [`REQUIREMENTS.md`](REQUIREMENTS.md).

## License

[MIT](LICENSE) © 2026 FX Martin.

## Acknowledgements

- [Andrej Karpathy's LLM-Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — the seed idea.
- Vannevar Bush's 1945 [Memex](https://en.wikipedia.org/wiki/Memex) — the pattern, 80 years early.
- [Obsidian](https://obsidian.md) — the vault format that made this architecture obvious.
